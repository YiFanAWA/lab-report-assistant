"""FastAPI 应用入口。

数据库表由 Alembic 迁移管理，不在应用启动时自动创建。
启动前请先运行：python -m alembic upgrade head
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.errors import AppError, ErrorResponse
from app.api.routers import health, projects, requirements, sources

app = FastAPI(
    title="实验报告助手 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(requirements.router)
app.include_router(sources.router)


NOT_FOUND_CODES = {
    "PROJECT_NOT_FOUND",
    "REQUIREMENT_SOURCE_NOT_FOUND",
    "REQUIREMENT_PLAN_NOT_FOUND",
    "SOURCE_RECORD_NOT_FOUND",
    "PARSED_DOCUMENT_NOT_FOUND",
    "EVIDENCE_CARD_NOT_FOUND",
}

PAYLOAD_TOO_LARGE_CODES = {
    "SOURCE_FILE_TOO_LARGE",
    "SOURCE_CONTENT_TOO_LARGE",
}


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    if exc.code in PAYLOAD_TOO_LARGE_CODES:
        status = 413
    elif exc.code in NOT_FOUND_CODES:
        status = 404
    else:
        status = 400
    return JSONResponse(
        status_code=status,
        content=ErrorResponse.from_app_error(exc).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    field = None
    if exc.errors():
        loc = exc.errors()[0].get("loc", ())
        if len(loc) >= 2 and loc[0] == "body":
            field = str(loc[1])

    if field == "name":
        err = AppError(code="PROJECT_NAME_REQUIRED", message="项目名称不能为空", field="name")
    elif field == "topic":
        err = AppError(code="PROJECT_TOPIC_REQUIRED", message="课题不能为空", field="topic")
    else:
        err = AppError(code="REQUEST_VALIDATION_ERROR", message="请求参数不符合要求", field=field)

    return JSONResponse(
        status_code=400,
        content=ErrorResponse.from_app_error(err).model_dump(),
    )
