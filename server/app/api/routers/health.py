"""健康检查 API 路由。"""

from fastapi import APIRouter

from app.modules.projects.contracts import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="lab-report-assistant-api")
