"""统一异常层级与错误码（规格 §2.4）。"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("kb.api")

_HTTP_CODES = {
    401: "AUTH_INVALID",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


class AppError(Exception):
    code = "INTERNAL"
    http_status = 500

    def __init__(self, message: str = "", detail: Any = None):
        self.message = message or self.__class__.__name__
        self.detail = detail
        super().__init__(self.message)

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.http_status,
            content={"code": self.code, "message": self.message, "detail": self.detail or {}},
        )


class AuthError(AppError):
    code = "AUTH_INVALID"
    http_status = 401


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = 403


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationError(AppError):
    code = "VALIDATION"
    http_status = 422


class UploadTooLargeError(AppError):
    code = "UPLOAD_TOO_LARGE"
    http_status = 413


class UploadFormatError(AppError):
    code = "UPLOAD_FORMAT"
    http_status = 415


class UrlInvalidError(AppError):
    code = "URL_INVALID"
    http_status = 422


class ParseError(AppError):
    code = "PARSE_FAILED"
    http_status = 422


class ParseUnsupportedError(AppError):
    code = "PARSE_UNSUPPORTED"
    http_status = 415


class DocStateError(AppError):
    code = "DOC_STATE"
    http_status = 409


class TaskStateError(AppError):
    code = "TASK_STATE"
    http_status = 409


class EmbeddingLockedError(AppError):
    code = "EMBEDDING_LOCKED"
    http_status = 409


class ProviderActiveError(AppError):
    """删除生效中供应商等供应商状态冲突（对规格 §2.4 的最小补充）。"""

    code = "PROVIDER_ACTIVE"
    http_status = 409


class ProviderConfigError(AppError):
    code = "PROVIDER_CONFIG"
    http_status = 422


class GatewayError(AppError):
    code = "PROVIDER_UNREACHABLE"
    http_status = 502

    def __init__(self, message: str = "", detail: Any = None, retryable: bool = True):
        self.retryable = retryable
        super().__init__(message, detail)


class GatewayJSONError(AppError):
    code = "LLM_JSON_INVALID"
    http_status = 502


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION",
                "message": "请求参数校验失败",
                "detail": exc.errors()[:10],
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": _HTTP_CODES.get(exc.status_code, "INTERNAL"),
                     "message": str(exc.detail), "detail": {}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # 完整异常只进日志；响应不返回 SQL/路径/内部值（§14）
        logger.exception("未处理异常：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL", "message": "服务内部错误，请稍后重试", "detail": {}},
        )
