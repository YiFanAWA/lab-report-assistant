"""SPEC 0021 浏览器验收测试数据准备脚本。

创建一个 DATASET_READY 状态的项目 + READY 数据集 + PARSED 数据集版本（含 profile_json），
供浏览器验收流式分析方案生成使用。

运行后输出 project_id 和 dataset_id，供 browser_use agent 导航使用。

注意：本脚本直接通过 ORM 写入数据库，绕过业务层校验，仅用于验收测试环境
构造测试数据。正常业务路径必须通过 API 调用推进项目状态。
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

# 确保导入 server 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.engine import SessionLocal, engine, Base
from app.core.config import settings
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.infrastructure.parsers.dataset_parser import DatasetProfile, FieldProfile


def _make_profile() -> DatasetProfile:
    """构造有效的 DatasetProfile（胃病数据集示例）。"""
    return DatasetProfile(
        row_count=100,
        column_count=3,
        complete_row_count=85,
        incomplete_row_count=15,
        duplicate_row_count=2,
        field_profiles=[
            FieldProfile(
                name="age",
                inferred_type="int",
                non_null_count=95,
                null_count=5,
                null_rate=0.05,
                unique_count=63,
                sample_values=["25", "30", "45"],
                min_value=18.0,
                max_value=80.0,
                mean_value=45.0,
            ),
            FieldProfile(
                name="gender",
                inferred_type="string",
                non_null_count=98,
                null_count=2,
                null_rate=0.02,
                unique_count=2,
                sample_values=["男", "女"],
            ),
            FieldProfile(
                name="diagnosis",
                inferred_type="string",
                non_null_count=100,
                null_count=0,
                null_rate=0.0,
                unique_count=5,
                sample_values=["胃炎", "胃溃疡"],
            ),
        ],
        quality_score=85.0,
    )


def main() -> None:
    # 确保表存在
    Base.metadata.create_all(bind=engine)

    project_id = "proj_spec0021_e2e"
    workspace_root = settings.project_data_root / project_id
    workspace_root.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        # 幂等：若已存在先删除
        existing = db.get(Project, project_id)
        if existing is not None:
            # 清理关联的 dataset version + dataset
            db.query(DatasetVersion).filter(
                DatasetVersion.project_id == project_id
            ).delete(synchronize_session=False)
            db.query(Dataset).filter(
                Dataset.project_id == project_id
            ).delete(synchronize_session=False)
            db.delete(existing)
            db.commit()

        project = Project(
            id=project_id,
            name="SPEC0021 流式分析方案验收项目",
            topic="胃病数据分析",
            status=ProjectStatus.DATASET_READY.value,
            workspace_root=str(workspace_root),
        )
        db.add(project)

        dataset_id = "ds_spec0021_e2e_001"
        dataset = Dataset(
            id=dataset_id,
            project_id=project.id,
            dataset_kind="FILE",
            title="胃病数据集（验收用）",
            description="SPEC0021 流式分析方案生成验收用数据集，含 age/gender/diagnosis 三个字段",
            status=DatasetStatus.READY.value,
        )
        db.add(dataset)

        version_id = "dv_spec0021_e2e_001"
        profile_json = json.dumps(asdict(_make_profile()), ensure_ascii=False)
        version = DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            project_id=project.id,
            version=1,
            status=DatasetVersionStatus.PARSED.value,
            file_path=str(workspace_root / "test.csv"),
            file_size_bytes=1024,
            row_count=100,
            column_count=3,
            profile_json=profile_json,
        )
        db.add(version)
        db.commit()

        print(f"PROJECT_ID={project.id}")
        print(f"DATASET_ID={dataset_id}")
        print(f"DATASET_VERSION_ID={version_id}")
        print(f"PROJECT_STATUS={project.status}")
        print(f"DATASET_STATUS={dataset.status}")
        print(f"VERSION_STATUS={version.status}")
        print(f"PROFILE_JSON_LENGTH={len(profile_json)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
