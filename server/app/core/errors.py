"""统一错误模型。

业务层抛出 AppError，API 层统一转换为结构化 HTTP 响应。
"""

from pydantic import BaseModel


class AppError(Exception):
    """可向 API 层公开的结构化错误。"""

    def __init__(self, code: str, message: str, field: str | None = None):
        self.code = code
        self.message = message
        self.field = field


class ErrorResponse(BaseModel):
    """返回给前端的结构化错误体。"""

    error: dict[str, str | None]

    @staticmethod
    def from_app_error(err: AppError) -> "ErrorResponse":
        return ErrorResponse(
            error={
                "code": err.code,
                "message": err.message,
                "field": err.field,
            }
        )
