"""API 层公共依赖注入。"""

from sqlalchemy.orm import Session

from app.core.errors import AppError


def require_confirmed_plan(db: Session, project_id: str) -> None:
    """校验项目任务单已确认，否则抛出 AppError。"""
    from app.modules.requirements.service import get_current_plan
    plan = get_current_plan(db, project_id)
    if not plan or plan.status != "CONFIRMED":
        raise AppError(
            code="REQUIREMENT_PLAN_NOT_CONFIRMED",
            message="请先确认实验任务单",
        )
