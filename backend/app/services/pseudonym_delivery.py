"""假名化交付领域服务。

交付批次按「数据主体 + 用途清单」管理，资格判断的唯一依据是同意登记中
仍然生效（status == 已同意）的同主体、同用途同意记录：

- 提交交付时逐用途核对同意，任一用途没有有效同意即拒绝整批；
- 同意被撤回后，相关用途立即失去下载资格，失效资格不能重新取得下载；
- 已经生成的交付记录保留创建时冻结的资格依据快照，撤回不追溯改写历史。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.base import BaseModuleService
from app.store import store

CONSENT_MODULE = "consent_registry"
ACTIVE_CONSENT_STATUS = "已同意"


def split_purposes(raw: Any) -> list[str]:
    """把逗号/顿号/分号分隔的用途清单规整成去重后的有序列表。"""
    if isinstance(raw, (list, tuple)):
        tokens = [str(item).strip() for item in raw]
    else:
        text = str(raw or "")
        for separator in ("，", "、", ";", "；", "\n"):
            text = text.replace(separator, ",")
        tokens = text.split(",")
    purposes: list[str] = []
    for token in tokens:
        purpose = token.strip()
        if purpose and purpose not in purposes:
            purposes.append(purpose)
    return purposes


def active_consent_purposes(subject: str) -> list[dict[str, Any]]:
    """返回某数据主体当前仍然有效的同意记录（按处理目的逐条）。"""
    rows = store.rows(CONSENT_MODULE)
    return [
        row for row in rows
        if str(row.get("数据主体", "")).casefold() == str(subject).casefold()
        and row.get("status") == ACTIVE_CONSENT_STATUS
    ]


def has_active_consent(subject: str, purpose: str) -> bool:
    """单个用途的实时资格判断；撤回/过期后该用途即失去资格。"""
    target = purpose.casefold()
    return any(
        str(row.get("处理目的", "")).casefold() == target
        for row in active_consent_purposes(subject)
    )


def eligibility_for_purposes(subject: str, purposes: list[str]) -> list[dict[str, Any]]:
    """逐用途给出当前资格与所依据的同意记录，供预览和下载共同复用。"""
    active_rows = active_consent_purposes(subject)
    result: list[dict[str, Any]] = []
    for purpose in purposes:
        basis = next(
            (row for row in active_rows
             if str(row.get("处理目的", "")).casefold() == purpose.casefold()),
            None,
        )
        result.append({
            "处理目的": purpose,
            "eligible": basis is not None,
            "consent_id": basis.get("id") if basis else None,
            "记录编号": basis.get("记录编号") if basis else None,
            "生效状态": basis.get("生效状态") if basis else "无有效同意",
        })
    return result


class PseudonymDeliveryService(BaseModuleService):
    MODULE = "pseudonym_delivery"
    ENTITY = "假名化交付批次"
    OPERATION_TERM = "校验"
    LIST_FIELDS = [
        "交付编号", "数据主体", "用途清单", "假名标识", "交付批次", "交付状态",
        "交付时间", "资格依据", "下载次数", "最近下载时间",
    ]
    REQUIRED_FIELDS = ["交付编号", "数据主体", "用途清单", "假名标识", "交付批次"]
    STATUS_ORDER = ["待提交", "已交付", "已停用"]
    ACTION_RULES: dict[str, str] = {}
    NEGATIVE_ACTIONS: list[str] = []

    # ——————————— 提交交付：按用途核对同意，冻结当时依据 ———————————

    def submit_delivery(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"

        subject = str(values.get("数据主体", "")).strip()
        purposes = split_purposes(values.get("用途清单"))
        if not purposes:
            return None, "用途清单不能为空，至少填写一个处理目的"

        eligibility = eligibility_for_purposes(subject, purposes)
        blocked = [item["处理目的"] for item in eligibility if not item["eligible"]]
        if blocked:
            return None, (
                f"数据主体 {subject} 对用途「{'、'.join(blocked)}」没有生效中的同意，"
                "假名化交付不能提交；失效资格不得用于交付"
            )

        rows = store.rows(self.MODULE)
        basis_parts = [
            f"{item['记录编号']}/{item['处理目的']}/已同意" for item in eligibility
        ]
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "status": "已交付",
            "pending": False,
            "abnormal": False,
            "交付编号": str(values.get("交付编号", "")).strip(),
            "数据主体": subject,
            "用途清单": "，".join(purposes),
            "假名标识": str(values.get("假名标识", "")).strip(),
            "交付批次": str(values.get("交付批次", "")).strip(),
            "交付状态": "可下载",
            "交付时间": now,
            # 冻结创建时刻的资格依据；后续撤回不修改该快照
            "资格依据": "；".join(basis_parts),
            "下载次数": 0,
            "最近下载时间": "未下载",
            "用途依据快照": eligibility,
        }
        rows.append(entry)
        return entry, f"交付批次 {entry['交付编号']} 已按用途授权提交，资格依据已冻结"

    # ——————————— 下载：实时复核每个用途的当前资格 ———————————

    def download_delivery(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        purposes = split_purposes(entry.get("用途清单"))
        eligibility = eligibility_for_purposes(entry.get("数据主体", ""), purposes)
        stopped = [item["处理目的"] for item in eligibility if not item["eligible"]]
        active = [item["处理目的"] for item in eligibility if item["eligible"]]

        if not active:
            entry["交付状态"] = "停止下载"
            return None, (
                f"交付批次 {entry.get('交付编号')} 的全部用途同意均已失效，"
                "下载被拒绝；已交付记录与原始依据仍予保留"
            )

        # 部分用途撤回：受影响用途停止交付，下载范围裁剪到仍获授权的用途，
        # 失效用途不能借批次里其他有效用途重新取得下载。
        entry["下载次数"] = int(entry.get("下载次数", 0)) + 1
        entry["最近下载时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if stopped:
            entry["交付状态"] = f"部分停用：{'、'.join(stopped)}"
            entry["本次下载限定用途"] = "、".join(active)
            message = (
                f"用途「{'、'.join(stopped)}」同意已撤回、停止交付；"
                f"本次下载仅包含仍获授权用途「{'、'.join(active)}」的数据，"
                f"历史资格依据保留：{entry.get('资格依据')}"
            )
        else:
            entry["交付状态"] = "可下载"
            entry["本次下载限定用途"] = "、".join(active)
            message = (
                f"交付批次 {entry.get('交付编号')} 下载成功，"
                f"授权用途：{'、'.join(active)}；历史依据：{entry.get('资格依据')}"
            )
        return entry, message

    # ——————————— 撤回联动：停用引用了指定同意用途的在途批次 ———————————

    def apply_withdrawal(self, subject: str, purpose: str) -> list[dict[str, Any]]:
        """同意撤回后，把同主体同用途、仍可下载的批次标记为部分/全部停用。"""
        affected: list[dict[str, Any]] = []
        for row in store.rows(self.MODULE):
            if str(row.get("数据主体", "")).casefold() != str(subject).casefold():
                continue
            purposes = split_purposes(row.get("用途清单"))
            if not any(item.casefold() == purpose.casefold() for item in purposes):
                continue
            active = [
                item for item in purposes
                if has_active_consent(row.get("数据主体", ""), item)
            ]
            before = row.get("交付状态")
            if active:
                stopped = [item for item in purposes if item not in active]
                row["交付状态"] = f"部分停用：{'、'.join(stopped)}"
            else:
                row["交付状态"] = "停止下载"
            row["status"] = "已停用" if not active else "已交付"
            if before != row["交付状态"]:
                affected.append({
                    "id": row.get("id"),
                    "交付编号": row.get("交付编号"),
                    "交付批次": row.get("交付批次"),
                    "用途清单": row.get("用途清单"),
                    "变更后交付状态": row["交付状态"],
                    "仍授权用途": active,
                })
        return affected
