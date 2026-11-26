"""领域流程异常：服务层用它携带建议的 HTTP 状态码，路由层统一转换。"""
from __future__ import annotations


class FlowError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)
