"""发布包中的 React SPA 静态文件适配。"""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """为生产前端提供静态文件和客户端路由回退。"""

    async def get_response(self, path: str, scope: dict):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith(("api/", "health")):
                raise
            if Path(path).name and "." in Path(path).name:
                raise
            index_path = Path(self.directory) / "index.html"
            if not index_path.is_file():
                raise
            return FileResponse(index_path, media_type="text/html")
