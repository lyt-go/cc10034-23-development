"""同意登记领域服务。

同一数据主体可以按处理目的登记多条独立同意；撤回必须精确到「哪一条同意
（主体 + 处理目的）」，不能连带取消该主体仍然有效的其他用途同意。

撤回分两步：
1. ``withdrawal_preview``：服务端核对撤回片段，列出受影响/不受影响的交付；
2. ``confirm_withdrawal``：确认后才写入撤回状态并生成撤回影响回执，
   假名化交付侧据此停用受影响用途、继续处理仍获授权的交付。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.errors import FlowError
from app.services.base import BaseModuleService
from app.services.pseudonym_delivery import (
    PseudonymDeliveryService,
    split_purposes,
)
from app.store import store

RECEIPT_MODULE = "withdrawal_receipt"


class ConsentRegistryService(BaseModuleService):
    MODULE = "consent_registry"
    ENTITY = "同意记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["记录编号", "数据主体", "处理目的", "同意范围", "同意时间", "撤回时间", "法律依据", "生效状态"]
    REQUIRED_FIELDS = ["记录编号", "数据主体", "处理目的"]
    STATUS_ORDER = ["已同意", "已撤回", "已过期"]
    ACTION_RULES = {"撤回同意": "已撤回", "标记过期": "已过期"}
    NEGATIVE_ACTIONS: list[str] = []

    # ——————————— 撤回影响预览（服务端核对撤回的是哪段同意） ———————————

    def withdrawal_preview(self, entry_id: int) -> dict[str, Any]:
        """返回撤回影响核对结果；记录不存在抛 404，状态不允许撤回抛 409。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            raise FlowError(404, f"{self.ENTITY} {entry_id} 不存在或已归档")
        if entry.get("status") != "已同意":
            raise FlowError(
                409,
                f"同意记录 {entry.get('记录编号')} 当前状态为「{entry.get('status')}」，"
                "只有生效中的同意可以撤回",
            )

        subject = str(entry.get("数据主体", ""))
        purpose = str(entry.get("处理目的", ""))
        impact = self._impact_scope(subject, purpose)
        return {
            "consent": entry,
            "数据主体": subject,
            "撤回处理目的": purpose,
            "同主体其他有效同意": impact["other_consents"],
            "受影响交付": impact["affected_deliveries"],
            "不受影响交付": impact["unaffected_deliveries"],
            "可确认范围": impact["confirm_scope"],
        }

    def _impact_scope(self, subject: str, purpose: str) -> dict[str, Any]:
        """服务端核对：同主体的其他同意、引用该用途的交付批次。"""
        other_consents = [
            {
                "id": row.get("id"),
                "记录编号": row.get("记录编号"),
                "处理目的": row.get("处理目的"),
                "status": row.get("status"),
            }
            for row in store.rows(self.MODULE)
            if str(row.get("数据主体", "")).casefold() == subject.casefold()
            and str(row.get("处理目的", "")).casefold() != purpose.casefold()
        ]

        affected: list[dict[str, Any]] = []
        unaffected: list[dict[str, Any]] = []
        for delivery in store.rows(PseudonymDeliveryService.MODULE):
            if str(delivery.get("数据主体", "")).casefold() != subject.casefold():
                continue
            purposes = split_purposes(delivery.get("用途清单"))
            touched = purpose.casefold() in [item.casefold() for item in purposes]
            payload = {
                "id": delivery.get("id"),
                "交付编号": delivery.get("交付编号"),
                "交付批次": delivery.get("交付批次"),
                "用途清单": delivery.get("用途清单"),
                "交付状态": delivery.get("交付状态"),
                "资格依据": delivery.get("资格依据"),
            }
            if touched:
                remaining = [
                    item for item in purposes
                    if item.casefold() != purpose.casefold()
                ]
                payload["撤回后剩余授权用途"] = remaining
                affected.append(payload)
            else:
                unaffected.append(payload)

        active_others = [row for row in other_consents if row.get("status") == "已同意"]
        confirm_scope = (
            f"仅撤回数据主体 {subject} 就「{purpose}」作出的同意；"
            f"同主体其余 {len(other_consents)} 条同意中 {len(active_others)} 条仍生效、"
            "继续有效，本次撤回不连带取消"
        )
        return {
            "other_consents": other_consents,
            "affected_deliveries": affected,
            "unaffected_deliveries": unaffected,
            "confirm_scope": confirm_scope,
        }

    # ——————————— 确认撤回：写入状态、联动交付、生成回执 ———————————

    def confirm_withdrawal(self, entry_id: int) -> dict[str, Any]:
        """确认撤回并生成回执；记录不存在抛 404，状态不允许撤回抛 409。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            raise FlowError(404, f"{self.ENTITY} {entry_id} 不存在或已归档")
        if entry.get("status") != "已同意":
            raise FlowError(
                409,
                f"同意记录 {entry.get('记录编号')} 当前状态为「{entry.get('status')}」，"
                "不能重复撤回",
            )

        subject = str(entry.get("数据主体", ""))
        purpose = str(entry.get("处理目的", ""))
        impact = self._impact_scope(subject, purpose)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["status"] = "已撤回"
        entry["pending"] = True
        entry["abnormal"] = True
        entry["撤回时间"] = now
        entry["生效状态"] = "已撤回"

        delivery_service = PseudonymDeliveryService()
        stopped_deliveries = delivery_service.apply_withdrawal(subject, purpose)

        return self._write_receipt(
            consent=entry,
            subject=subject,
            purpose=purpose,
            impact=impact,
            stopped=stopped_deliveries,
            now=now,
        )

    def _write_receipt(
        self,
        *,
        consent: dict[str, Any],
        subject: str,
        purpose: str,
        impact: dict[str, Any],
        stopped: list[dict[str, Any]],
        now: str,
    ) -> dict[str, Any]:
        rows = store.rows(RECEIPT_MODULE)
        receipt_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        receipt_no = f"RCPT-{receipt_id:04d}"
        retained_purposes = [
            f"{item['记录编号']}/{item['处理目的']}"
            for item in impact["other_consents"]
            if item.get("status") == "已同意"
        ]
        receipt = {
            "id": receipt_id,
            "status": "已生效",
            "pending": False,
            "abnormal": False,
            "回执编号": receipt_no,
            "数据主体": subject,
            "撤回同意记录": str(consent.get("记录编号", "")),
            "撤回处理目的": purpose,
            "撤回时间": now,
            "可确认范围": impact["confirm_scope"],
            "停用交付数": len(stopped),
            "停用交付明细": "；".join(
                f"{item['交付编号']}→{item['变更后交付状态']}" for item in stopped
            ) or "无在途交付受影响",
            "继续授权用途": "；".join(retained_purposes) or "无",
            "历史依据保留": "已交付记录的资格依据快照保持不变",
        }
        rows.append(receipt)
        return receipt

    def list_receipts(self) -> list[dict[str, Any]]:
        return list(store.rows(RECEIPT_MODULE))

    # ——————————— 通用动作入口：撤回统一引导到影响确认流程 ———————————

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        if action == "撤回同意":
            return None, (
                "撤回同意必须先核对影响范围：请调用撤回影响预览并在确认页确认，"
                "服务端会生成撤回影响回执"
            )
        return super().run_action(entry_id, action)
