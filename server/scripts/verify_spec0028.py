"""SPEC 0028 真实图表 + PPT 视觉验证脚本。

验证内容：
1. LocalRuleCodeTaskProvider 生成的代码包含 nature-figure rcParams（无 scienceplots）
2. 沙箱执行成功（scienceplots 已卸载，代码不依赖它）
3. 图表 PNG 产物生成成功
4. PPT 渲染成功（6 种预设色）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider, _HEADER
from app.infrastructure.sandbox.python_executor import execute_code
from app.infrastructure.renderers.ppt_renderer import PptRenderer


def make_sample_dataset(csv_path: Path):
    """生成教学数据集。"""
    np.random.seed(42)
    n = 200
    data = {
        "patient_id": range(1, n + 1),
        "age": np.random.normal(50, 15, n).astype(int),
        "sex": np.random.choice(["男", "女"], n),
        "bmi": np.random.normal(24, 4, n).round(1),
        "diagnosis": np.random.choice(["胃炎", "溃疡", "正常"], n),
        "symptom_score": np.random.randint(0, 10, n),
        "blood_pressure": np.random.normal(120, 20, n).astype(int),
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return df


def make_analysis_plan():
    """构造 AnalysisPlan。"""
    return {
        "cleaning_plan": [
            {"step": "去除缺失值", "action": "dropna"},
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE",
                "target_fields": ["age", "bmi", "symptom_score"],
                "reason": "描述性统计",
            },
            {
                "analysis_type": "CORRELATION",
                "target_fields": ["age", "bmi", "symptom_score", "blood_pressure"],
                "reason": "相关性分析",
            },
        ],
        "chart_plan": [
            {"chart_type": "HISTOGRAM", "target_field": "age", "title": "年龄分布"},
            {"chart_type": "BAR", "target_field": "diagnosis", "title": "诊断分布"},
            {"chart_type": "BOXPLOT", "target_field": "symptom_score", "title": "症状评分"},
            {"chart_type": "SCATTER", "target_fields": ["age", "bmi"], "title": "年龄与BMI"},
        ],
    }


def main():
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / "dev-docs" / "e2e-screenshots" / "spec0028"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SPEC 0028 真实图表 + PPT 视觉验证")
    print("=" * 60)

    # 1. 验证 _HEADER 不含 scienceplots
    print("\n1. 验证 _HEADER 内容...")
    checks = [
        ("不含 import scienceplots", "import scienceplots" not in _HEADER),
        ("不含 plt.style.use", "plt.style.use" not in _HEADER),
        ("含 matplotlib.rcParams", "matplotlib.rcParams" in _HEADER),
        ("含 axes.spines.right", "axes.spines.right" in _HEADER),
        ("含 axes.spines.top", "axes.spines.top" in _HEADER),
        ("含 axes.linewidth", "axes.linewidth" in _HEADER),
        ("含 2.5 (轴线宽度)", "2.5" in _HEADER),
        ("含 Microsoft YaHei", "Microsoft YaHei" in _HEADER),
        ("含 savefig.dpi 300", "300" in _HEADER),
        ("含 import seaborn", "import seaborn" in _HEADER),
    ]
    all_pass = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        if not passed:
            all_pass = False
        print(f"   {status} {name}")

    # 2. 生成代码并执行
    print("\n2. 生成代码并在沙箱中执行...")
    csv_path = output_dir / "sample_data.csv"
    make_sample_dataset(csv_path)

    provider = LocalRuleCodeTaskProvider()
    plan = make_analysis_plan()
    draft = provider.generate(plan)
    code = draft.code

    work_dir = output_dir / "work"
    work_dir.mkdir(exist_ok=True)

    result = execute_code(
        code=code,
        work_dir=str(work_dir),
        data_path=str(csv_path),
        timeout_seconds=60,
        memory_limit_mb=2048,
    )

    if result.exit_code == 0 and result.sandbox_error_code is None:
        print(f"   ✅ 沙箱执行成功")
        print(f"   图表产物: {len(result.artifacts)} 个")
        for a in result.artifacts:
            print(f"   - {a.name} ({a.artifact_type})")
    else:
        print(f"   ❌ 沙箱执行失败: exit_code={result.exit_code}, error={result.sandbox_error_code}")
        print(f"   stderr: {result.stderr[:500] if result.stderr else 'N/A'}")
        return

    # 3. 渲染 6 种预设色 PPT
    print("\n3. 渲染 6 种预设色 PPT...")
    chart_artifacts = [
        {"name": a.name, "file_path": a.file_path, "artifact_type": "CHART_PNG"}
        for a in result.artifacts
        if a.artifact_type == "CHART_PNG"
    ]

    colors = {
        "blue": "2563EB",
        "purple": "7C3AED",
        "green": "059669",
        "red": "DC2626",
        "orange": "EA580C",
        "gray": "4B5563",
    }

    for color_name, color_hex in colors.items():
        ppt_path = str(output_dir / f"spec0028_{color_name}.pptx")
        renderer = PptRenderer()
        renderer.render(
            project_name=f"SPEC 0028 {color_name}",
            project_topic="胃病数据分析报告",
            outline_sections=[
                {
                    "title": "数据分析概述",
                    "source_type": "REQUIREMENT",
                    "content": "本实验对胃病数据进行分析。",
                },
                {
                    "title": "总结",
                    "source_type": "SUMMARY",
                    "content": "通过数据分析发现年龄与BMI存在相关性。",
                },
            ],
            execution_artifacts=chart_artifacts,
            output_path=ppt_path,
            config={"theme_color": color_hex, "include_charts": True},
        )
        print(f"   ✅ {color_name}: {ppt_path}")

    # 4. 总结
    print(f"\n{'=' * 60}")
    if all_pass and result.exit_code == 0:
        print("✅ SPEC 0028 视觉验证全部通过！")
        print(f"   - _HEADER 包含 nature-figure rcParams，不含 scienceplots")
        print(f"   - 沙箱执行成功（scienceplots 已卸载）")
        print(f"   - {len(chart_artifacts)} 张图表生成成功")
        print(f"   - 6 种预设色 PPT 渲染成功")
    else:
        print("❌ 验证失败，请检查上述输出")
    print(f"   输出目录: {output_dir}")


if __name__ == "__main__":
    main()
