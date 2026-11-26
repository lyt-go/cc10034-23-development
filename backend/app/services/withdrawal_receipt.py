"""撤回影响回执只读领域服务。

回执只能由同意撤回确认流程（consent_flow 路由）生成，本服务只提供
通用列表/详情/导出骨架，不开放登记与动作入口。
"""
from __future__ import annotations

from typing import Any

from app.errors import FlowError
from app.services.base import BaseModuleService


class WithdrawalReceiptService(BaseModuleService):
    MODULE = "withdrawal_receipt"
    ENTITY = "撤回影响回执"
    OPERATION_TERM = "校验"
    LIST_FIELDS = [
        "回执编号", "数据主体", "撤回同意记录", "撤回处理目的", "撤回时间",
        "停用交付数", "停用交付明细", "继续授权用途", "历史依据保留",
    ]
    REQUIRED_FIELDS: list[str] = []
    STATUS_ORDER = ["已生效"]
    ACTION_RULES: dict[str, str] = {}
    NEGATIVE_ACTIONS: list[str] = []

    def create_entry(self, values: dict[str, Any]):  # type: ignore[override]
        raise FlowError(405, "撤回影响回执只能由撤回确认流程生成，不支持手工登记")

    def run_action(self, entry_id: int, action: str):  # type: ignore[override]
        raise FlowError(405, "撤回影响回执为留存凭证，不支持状态动作")

