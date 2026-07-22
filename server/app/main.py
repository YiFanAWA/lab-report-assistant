"""FastAPI 应用入口。

数据库表由 Alembic 迁移管理，不在应用启动时自动创建。
启动前请先运行：python -m alembic upgrade head
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.api.routers import (
    health, projects, requirements, sources, evidence, jobs,
    datasets, analysis, code_tasks, execution_runs,
)

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
app.include_router(evidence.router)
app.include_router(jobs.router)
app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(code_tasks.router)
app.include_router(execution_runs.router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    from app.core.errors import ErrorResponse
    not_found_codes = {
        "PROJECT_NOT_FOUND",
        "REQUIREMENT_SOURCE_NOT_FOUND",
        "REQUIREMENT_PLAN_NOT_FOUND",
        "SOURCE_NOT_FOUND",
        "EVIDENCE_CARD_NOT_FOUND",
        "JOB_NOT_FOUND",
        "DATASET_NOT_FOUND",
        "DATASET_VERSION_NOT_FOUND",
        "ANALYSIS_PLAN_NOT_FOUND",
        "CODE_TASK_NOT_FOUND",
        "EXECUTION_RUN_NOT_FOUND",
        "EXECUTION_ARTIFACT_NOT_FOUND",
    }
    forbidden_codes = {
        "SOURCE_ACCESS_RESTRICTED",
        "DATASET_ACCESS_RESTRICTED",
        "CODE_EXECUTION_DISABLED",
    }
    too_large_codes = {
        "REQUIREMENT_FILE_TOO_LARGE",
        "SOURCE_FILE_TOO_LARGE",
        "DATASET_FILE_TOO_LARGE",
    }
    if exc.code in not_found_codes:
        status = 404
    elif exc.code in forbidden_codes:
        status = 403
    elif exc.code in too_large_codes:
        status = 413
    else:
        status = 400
    return JSONResponse(
        status_code=status,
        content=ErrorResponse.from_app_error(exc).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    from app.core.errors import ErrorResponse

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
