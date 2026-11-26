"""业务路由汇总：跨模块链接/专用流程路由必须先于通用资源路由注册。"""
from __future__ import annotations

from app.routers import consent_flow, cross_links, resource

ROUTERS = [cross_links, consent_flow, resource]
