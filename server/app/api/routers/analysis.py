"""分析方案 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /datasets/{dataset_id}/analysis/generate
  GET  /analysis
  GET  /analysis/{plan_id}
  PUT  /analysis/{plan_id}
  POST /analysis/{plan_id}/confirm
  POST /analysis/{plan_id}/reject
  POST /analysis/complete
"""

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.analysis import service as analysis_service
from app.modules.analysis.contracts import (
    UpdateAnalysisPlanRequest,
    AnalysisPlanResponse,
    AnalysisPlanListResponse,
    CompleteAnalysisResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _field_from_validation(exc: ValidationError) -> str | None:
    if not exc.errors():
        return None
    loc = exc.errors()[0].get("loc", ())
    return str(loc[0]) if loc else None


# --- 触发生成分析方案 ---


@router.post("/datasets/{dataset_id}/analysis/generate", status_code=201)
def generate_analysis_plan(project_id: str, dataset_id: str,
                            db: Session = Depends(_db)):
    job_id = analysis_service.generate_analysis_plan(
        db, project_id, dataset_id)
    return {"job_id": job_id}


# --- 分析方案列表 ---


@router.get("/analysis", response_model=AnalysisPlanListResponse)
def list_analysis_plans(project_id: str,
                        dataset_id: str | None = None,
                        status: str | None = None,
                        db: Session = Depends(_db)):
    plans = analysis_service.list_analysis_plans(
        db, project_id, dataset_id=dataset_id, status=status)
    return analysis_service.plan_list_to_response(plans)


# --- 分析方案详情 ---


@router.get("/analysis/{plan_id}", response_model=AnalysisPlanResponse)
def get_analysis_plan(project_id: str, plan_id: str,
                      db: Session = Depends(_db)):
    plan = analysis_service.get_analysis_plan_by_project(
        db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 编辑分析方案 ---


@router.put("/analysis/{plan_id}", response_model=AnalysisPlanResponse)
def update_analysis_plan(project_id: str, plan_id: str, body: dict,
                          db: Session = Depends(_db)):
    try:
        req = UpdateAnalysisPlanRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    plan = analysis_service.update_analysis_plan(
        db, project_id, plan_id, req)
    return analysis_service.plan_to_response(plan)


# --- 确认分析方案 ---


@router.post("/analysis/{plan_id}/confirm",
              response_model=AnalysisPlanResponse)
def confirm_analysis_plan(project_id: str, plan_id: str,
                           db: Session = Depends(_db)):
    plan = analysis_service.confirm_analysis_plan(db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 拒绝分析方案 ---


@router.post("/analysis/{plan_id}/reject",
              response_model=AnalysisPlanResponse)
def reject_analysis_plan(project_id: str, plan_id: str,
                          db: Session = Depends(_db)):
    plan = analysis_service.reject_analysis_plan(db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 完成分析方案确认 ---


@router.post("/analysis/complete", response_model=CompleteAnalysisResponse)
def complete_analysis(project_id: str, db: Session = Depends(_db)):
    project = analysis_service.complete_analysis(db, project_id)
    return analysis_service.complete_analysis_to_response(project)
