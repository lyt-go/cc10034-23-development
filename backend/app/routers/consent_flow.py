"""同意撤回与假名化交付的专用流程接口。

通用资源路由只做登记/动作骨架；撤回影响确认、交付资格核对等带业务判断的
流程集中在本路由，且必须早于 /api/{module} 动态路由注册。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.errors import FlowError
from app.schemas import ActionResult, EntryPayload
from app.services import service_for
from app.services.consent_registry import ConsentRegistryService, RECEIPT_MODULE
from app.services.pseudonym_delivery import PseudonymDeliveryService
from app.store import store

router = APIRouter(prefix="/api", tags=["同意撤回与假名化交付"])


def consent_service() -> ConsentRegistryService:
    service = service_for("consent_registry")
    assert isinstance(service, ConsentRegistryService)
    return service


def delivery_service() -> PseudonymDeliveryService:
    service = service_for("pseudonym_delivery")
    assert isinstance(service, PseudonymDeliveryService)
    return service


# ——————————— 撤回影响确认 ———————————


@router.get("/consent/{entry_id}/withdrawal/preview")
def withdrawal_preview(entry_id: int) -> dict[str, Any]:
    """服务端核对撤回的是哪段同意，并返回前端确认页所需的影响范围。"""
    try:
        preview = consent_service().withdrawal_preview(entry_id)
    except FlowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"ok": True, "message": "ok", **preview}


@router.post("/consent/{entry_id}/withdrawal/confirm", response_model=ActionResult)
def withdrawal_confirm(entry_id: int) -> ActionResult:
    """确认撤回：写入撤回状态、联动停用受影响交付并生成撤回影响回执。"""
    try:
        receipt = consent_service().confirm_withdrawal(entry_id)
    except FlowError as exc:
        return ActionResult(ok=False, message=str(exc))
    return ActionResult(
        ok=True,
        message=f"撤回影响回执 {receipt['回执编号']} 已生成",
        entry=receipt,
    )


@router.get("/withdrawal-receipts")
def withdrawal_receipts() -> dict[str, Any]:
    """已发撤回影响回执清单。"""
    items = consent_service().list_receipts()
    return {"items": items, "total": len(items)}


# ——————————— 假名化交付 ———————————


@router.post("/pseudonym-delivery", response_model=ActionResult)
def submit_delivery(payload: EntryPayload) -> ActionResult:
    """提交包含一个或多个用途的假名化交付，逐用途核对有效同意。"""
    entry, message = delivery_service().submit_delivery(payload.values)
    return ActionResult(ok=entry is not None, message=message, entry=entry)


@router.post("/pseudonym-delivery/{entry_id}/download", response_model=ActionResult)
def download_delivery(entry_id: int) -> ActionResult:
    """下载前实时复核资格：失效用途不能重新取得下载，仍授权用途继续。"""
    entry, message = delivery_service().download_delivery(entry_id)
    return ActionResult(ok=entry is not None, message=message, entry=entry)


@router.get("/withdrawal-receipts/{receipt_id}")
def withdrawal_receipt_detail(receipt_id: int) -> dict[str, Any]:
    receipt = store.find(RECEIPT_MODULE, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail=f"撤回影响回执 {receipt_id} 不存在")
    return receipt
