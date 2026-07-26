"""SPEC 0020 浏览器验收测试数据准备脚本。

创建一个 REQUIREMENT_CONFIRMED 状态的项目 + 已解析来源（含多段落文本），
供浏览器验收流式证据卡片生成使用。

运行后输出 project_id 和 source_id，供 browser_use agent 导航使用。
"""

import sys
from pathlib import Path

# 确保导入 server 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.engine import SessionLocal, engine, Base
from app.core.config import settings
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.sources.models import Source, ParsedDocument
from app.modules.sources.status import SourceKind, SourceStatus


def main() -> None:
    # 确保表存在
    Base.metadata.create_all(bind=engine)

    project_id = "proj_spec0020_e2e"
    workspace_root = settings.project_data_root / project_id
    workspace_root.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        project = Project(
            id=project_id,
            name="SPEC0020 流式证据卡片验收项目",
            topic="胃病数据分析",
            status=ProjectStatus.REQUIREMENT_CONFIRMED.value,
            workspace_root=str(workspace_root),
        )
        db.add(project)

        source_id = "src_spec0020_e2e_001"
        source = Source(
            id=source_id,
            project_id=project.id,
            source_kind=SourceKind.FILE.value,
            title="胃病数据分析参考文档（验收用）",
            status=SourceStatus.PARSED.value,
        )
        db.add(source)

        # 多段落文本，每段 >= 30 字符，确保 LocalRule 生成卡片
        parsed_text = (
            "背景：本节介绍胃病数据的研究背景与意义，包含流行病学统计和疾病分类说明。\n"
            "方法：采用描述性统计方法和可视化技术分析数据，包括均值、标准差和分布检验。\n"
            "结果：分析显示关键变量之间存在显著相关，胃病发病率呈现逐年上升趋势。"
        )
        pd = ParsedDocument(
            id="pd_spec0020_e2e_001",
            source_id=source_id,
            project_id=project.id,
            title="胃病数据分析参考文档（验收用）",
            parsed_text=parsed_text,
            metadata_json='{"description": "SPEC0020 验收用解析文档"}',
        )
        db.add(pd)
        db.commit()

        print(f"PROJECT_ID={project.id}")
        print(f"SOURCE_ID={source_id}")
        print(f"PARSED_DOCUMENT_ID={pd.id}")
        print(f"PROJECT_STATUS={project.status}")
        print(f"SOURCE_STATUS={source.status}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
