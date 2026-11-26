"""撤回影响确认与假名化交付资格的领域测试。

覆盖题述场景：同一主体登记研究/教学两条同意 → 提交两用途交付 →
在另一页撤回研究 → 核对可确认范围、撤回回执与教学批次的后续下载。
"""
from __future__ import annotations

import pytest

from app.errors import FlowError
from app.services.consent_registry import ConsentRegistryService
from app.services.pseudonym_delivery import (
    PseudonymDeliveryService,
    eligibility_for_purposes,
    split_purposes,
)
from app.store import store

SUBJECT = "user_withdraw_case"


@pytest.fixture()
def services():
    """每个用例在空仓库上运行，结束后恢复种子数据，避免污染其他测试模块。"""
    from app.seed import SEED_ROWS

    saved = {name: [dict(row) for row in rows] for name, rows in store._tables.items()}
    store._tables = {name: [] for name in SEED_ROWS}
    consent = ConsentRegistryService()
    delivery = PseudonymDeliveryService()
    yield consent, delivery
    store._tables = saved


def _register_two_consents(consent: ConsentRegistryService):
    research, _ = consent.create_entry({
        "记录编号": "CONS-R-1", "数据主体": SUBJECT, "处理目的": "科学研究",
        "同意范围": "研究集", "同意时间": "2026-11-01", "撤回时间": "未撤回",
        "法律依据": "个保法第13条", "生效状态": "生效中",
    })
    teaching, _ = consent.create_entry({
        "记录编号": "CONS-T-1", "数据主体": SUBJECT, "处理目的": "教学使用",
        "同意范围": "教学库", "同意时间": "2026-11-01", "撤回时间": "未撤回",
        "法律依据": "个保法第13条", "生效状态": "生效中",
    })
    return research, teaching


class TestPurposeParsing:
    def test_split_purposes_handles_multiple_separators(self):
        assert split_purposes("科学研究，教学使用、营销;统计；分析") == [
            "科学研究", "教学使用", "营销", "统计", "分析",
        ]

    def test_split_purposes_deduplicates(self):
        assert split_purposes("研究,研究,教学") == ["研究", "教学"]


class TestDeliveryEligibility:
    def test_submit_requires_active_consent_for_every_purpose(self, services):
        consent, delivery = services
        _register_two_consents(consent)
        entry, message = delivery.submit_delivery({
            "交付编号": "DELV-1", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h1", "交付批次": "b1",
        })
        assert entry is not None
        assert "CONS-R-1/科学研究/已同意" in entry["资格依据"]
        assert "CONS-T-1/教学使用/已同意" in entry["资格依据"]
        assert entry["用途依据快照"][0]["eligible"] is True

    def test_submit_rejected_when_one_purpose_lacks_consent(self, services):
        consent, delivery = services
        _register_two_consents(consent)
        entry, message = delivery.submit_delivery({
            "交付编号": "DELV-2", "数据主体": SUBJECT,
            "用途清单": "科学研究，商业营销", "假名标识": "h2", "交付批次": "b2",
        })
        assert entry is None
        assert "商业营销" in message

    def test_submit_rejected_with_empty_purposes(self, services):
        _, delivery = services
        entry, message = delivery.submit_delivery({
            "交付编号": "DELV-3", "数据主体": SUBJECT,
            "用途清单": " , ", "假名标识": "h3", "交付批次": "b3",
        })
        assert entry is None
        assert "用途清单" in message

    def test_other_subject_consent_does_not_grant_eligibility(self, services):
        consent, _ = services
        consent.create_entry({
            "记录编号": "CONS-X", "数据主体": "somebody_else", "处理目的": "科学研究",
        })
        result = eligibility_for_purposes(SUBJECT, ["科学研究"])
        assert result[0]["eligible"] is False


class TestWithdrawalPreview:
    def test_preview_scopes_to_single_purpose(self, services):
        consent, delivery = services
        research, teaching = _register_two_consents(consent)
        delivery.submit_delivery({
            "交付编号": "DELV-MIX", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h", "交付批次": "b",
        })
        preview = consent.withdrawal_preview(research["id"])
        # 可确认范围只针对研究这一段同意
        assert preview["撤回处理目的"] == "科学研究"
        assert "不连带取消" in preview["可确认范围"]
        other = {(row["处理目的"], row["status"]) for row in preview["同主体其他有效同意"]}
        assert ("教学使用", "已同意") in other
        affected = preview["受影响交付"]
        assert len(affected) == 1
        assert affected[0]["撤回后剩余授权用途"] == ["教学使用"]

    def test_preview_rejects_non_active_consent(self, services):
        consent, _ = services
        research, _ = _register_two_consents(consent)
        consent.confirm_withdrawal(research["id"])
        with pytest.raises(FlowError) as exc:
            consent.withdrawal_preview(research["id"])
        assert exc.value.status_code == 409
        assert "只有生效中的同意可以撤回" in str(exc.value)

    def test_preview_unknown_id(self, services):
        consent, _ = services
        with pytest.raises(FlowError) as exc:
            consent.withdrawal_preview(999)
        assert exc.value.status_code == 404
        assert "不存在" in str(exc.value)

    def test_generic_action_blocks_direct_withdrawal(self, services):
        consent, _ = services
        research, _ = _register_two_consents(consent)
        entry, message = consent.run_action(research["id"], "撤回同意")
        assert entry is None
        assert "撤回影响预览" in message


class TestWithdrawalConfirm:
    def test_confirm_generates_receipt_and_preserves_other_consent(self, services):
        consent, delivery = services
        research, teaching = _register_two_consents(consent)
        entry, _ = delivery.submit_delivery({
            "交付编号": "DELV-MIX", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h", "交付批次": "b",
        })

        receipt = consent.confirm_withdrawal(research["id"])
        assert receipt["回执编号"] == "RCPT-0001"
        assert receipt["撤回处理目的"] == "科学研究"
        assert receipt["停用交付数"] == 1
        assert "教学使用" in receipt["继续授权用途"]
        assert receipt["历史依据保留"]

        # 研究撤回不连带教学
        assert store.find("consent_registry", research["id"])["status"] == "已撤回"
        assert store.find("consent_registry", teaching["id"])["status"] == "已同意"

        # 交付批次被标记为部分停用
        row = store.find("pseudonym_delivery", entry["id"])
        assert "科学研究" in row["交付状态"]
        assert row["status"] == "已交付"  # 仍有教学用途授权，批次未整体停用

    def test_confirm_twice_is_rejected(self, services):
        consent, _ = services
        research, _ = _register_two_consents(consent)
        first = consent.confirm_withdrawal(research["id"])
        assert first is not None
        with pytest.raises(FlowError) as exc:
            consent.confirm_withdrawal(research["id"])
        assert exc.value.status_code == 409
        assert "不能重复撤回" in str(exc.value)
        assert len(consent.list_receipts()) == 1

    def test_receipt_records_full_stop_when_all_purposes_withdrawn(self, services):
        consent, delivery = services
        research, teaching = _register_two_consents(consent)
        entry, _ = delivery.submit_delivery({
            "交付编号": "DELV-MIX", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h", "交付批次": "b",
        })
        consent.confirm_withdrawal(research["id"])
        receipt2 = consent.confirm_withdrawal(teaching["id"])
        assert receipt2["回执编号"] == "RCPT-0002"
        row = store.find("pseudonym_delivery", entry["id"])
        assert row["交付状态"] == "停止下载"
        assert row["status"] == "已停用"


class TestDownloadAfterWithdrawal:
    def test_research_cannot_reacquire_download_teaching_continues(self, services):
        consent, delivery = services
        research, _ = _register_two_consents(consent)
        mixed, _ = delivery.submit_delivery({
            "交付编号": "DELV-MIX", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h", "交付批次": "b",
        })
        # 撤回前先下载一次，形成已交付记录
        before, msg = delivery.download_delivery(mixed["id"])
        assert before is not None
        assert before["下载次数"] == 1

        consent.confirm_withdrawal(research["id"])

        # 混合批次仍可下载，但范围裁剪到教学；研究不能凭旧资格重新取得
        after, msg = delivery.download_delivery(mixed["id"])
        assert after is not None
        assert after["下载次数"] == 2
        assert after["本次下载限定用途"] == "教学使用"
        assert "科学研究" in msg and "停止" in msg
        # 历史依据保留当时快照
        assert "CONS-R-1/科学研究/已同意" in after["资格依据"]

    def test_fully_withdrawn_batch_download_rejected_but_record_kept(self, services):
        consent, delivery = services
        research, teaching = _register_two_consents(consent)
        mixed, _ = delivery.submit_delivery({
            "交付编号": "DELV-MIX", "数据主体": SUBJECT,
            "用途清单": "科学研究，教学使用", "假名标识": "h", "交付批次": "b",
        })
        consent.confirm_withdrawal(research["id"])
        consent.confirm_withdrawal(teaching["id"])
        result, message = delivery.download_delivery(mixed["id"])
        assert result is None
        assert "全部用途同意均已失效" in message
        # 记录与冻结依据仍在
        row = store.find("pseudonym_delivery", mixed["id"])
        assert row is not None
        assert "CONS-R-1/科学研究/已同意" in row["资格依据"]

    def test_teaching_only_batch_remains_downloadable(self, services):
        consent, delivery = services
        research, _ = _register_two_consents(consent)
        teach_batch, _ = delivery.submit_delivery({
            "交付编号": "DELV-T", "数据主体": SUBJECT,
            "用途清单": "教学使用", "假名标识": "h2", "交付批次": "b2",
        })
        consent.confirm_withdrawal(research["id"])
        result, message = delivery.download_delivery(teach_batch["id"])
        assert result is not None
        assert result["交付状态"] == "可下载"
        assert result["本次下载限定用途"] == "教学使用"

    def test_research_only_delivery_blocked_after_withdrawal(self, services):
        consent, delivery = services
        research, _ = _register_two_consents(consent)
        consent.confirm_withdrawal(research["id"])
        entry, message = delivery.submit_delivery({
            "交付编号": "DELV-R", "数据主体": SUBJECT,
            "用途清单": "科学研究", "假名标识": "h3", "交付批次": "b3",
        })
        assert entry is None
        assert "没有生效中的同意" in message

    def test_unrelated_delivery_not_touched_by_withdrawal(self, services):
        consent, delivery = services
        research, _ = _register_two_consents(consent)
        # 另一个主体的教学交付（先具备该主体自己的有效同意）
        consent.create_entry({
            "记录编号": "CONS-OTHER", "数据主体": "user_other", "处理目的": "教学使用",
        })
        other, msg = delivery.submit_delivery({
            "交付编号": "DELV-OTHER", "数据主体": "user_other",
            "用途清单": "教学使用", "假名标识": "hx", "交付批次": "bx",
        })
        assert other is not None, msg
        consent.confirm_withdrawal(research["id"])
        row = store.find("pseudonym_delivery", other["id"])
        assert row["交付状态"] == "可下载"


class TestReceiptReadOnly:
    """回执只能由撤回确认流程生成，通用登记/动作入口必须拒绝。"""

    def test_manual_creation_raises_flow_error(self, services):
        from app.services.withdrawal_receipt import WithdrawalReceiptService

        with pytest.raises(FlowError) as exc:
            WithdrawalReceiptService().create_entry({"回执编号": "FAKE"})
        assert exc.value.status_code == 405

    def test_action_raises_flow_error(self, services):
        from app.services.withdrawal_receipt import WithdrawalReceiptService

        with pytest.raises(FlowError) as exc:
            WithdrawalReceiptService().run_action(1, "任意动作")
        assert exc.value.status_code == 405

    def test_receipts_listed_through_service(self, services):
        from app.services.withdrawal_receipt import WithdrawalReceiptService

        consent, _ = services
        research, _ = _register_two_consents(consent)
        consent.confirm_withdrawal(research["id"])
        items, total = WithdrawalReceiptService().list_entries()
        assert total == 1
        assert items[0]["回执编号"] == "RCPT-0001"
