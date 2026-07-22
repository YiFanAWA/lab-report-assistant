"""测试全局 fixture 与 ORM 模型注册。

集中导入所有 ORM 模型，使 Base.metadata 在测试 create_all 时创建全部表。
新增切片时只需在此文件追加导入，避免每个测试文件分别维护。
"""

from app.infrastructure.database.engine import Base  # noqa: F401
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import (  # noqa: F401
    RequirementSource,
    RequirementPlan,
    ChangeRecord,
)
from app.modules.sources.models import (  # noqa: F401
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.jobs.models import BackgroundJob  # noqa: F401
from app.modules.datasets.models import Dataset, DatasetVersion  # noqa: F401
from app.modules.analysis.models import AnalysisPlan  # noqa: F401
from app.modules.execution.models import (  # noqa: F401
    CodeTask,
    ExecutionRun,
    ExecutionArtifact,
)
