"""把来源字节写入已存在项目的受控工作区。"""

import re
import uuid
from pathlib import Path


def save_source_bytes(
    workspace_root: str,
    original_name: str,
    content: bytes,
) -> Path:
    """将来源字节保存到项目受控工作区内，返回绝对路径。"""
    root = Path(workspace_root).resolve()
    source_dir = (root / "sources").resolve()
    source_dir.mkdir(parents=True, exist_ok=True)

    raw_name = original_name.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    safe_name = safe_name or "source.bin"

    destination = (source_dir / f"{uuid.uuid4().hex}_{safe_name}").resolve()

    # 路径逃逸检查
    if source_dir not in destination.parents:
        raise ValueError("source path escaped project workspace")

    destination.write_bytes(content)
    return destination
