"""原始文件与图片落盘（规格 §6.4）：文件名全部系统生成，杜绝用户输入进路径。"""

import re

from app.core.config import get_settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe(name: str) -> str:
    return _SAFE.sub("_", name)[:80] or "file"


def save_original(doc_id: str, filename: str, content: bytes) -> str:
    ext = _safe("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    rel = f"storage/{doc_id}/original{ext}"
    path = get_settings().data_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return rel


def save_image(doc_id: str, name: str, content: bytes) -> str:
    rel = f"storage/{doc_id}/{_safe(name)}"
    path = get_settings().data_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return rel


def abs_path(rel: str) -> "object":
    """相对路径 → 绝对路径；校验仍在 data 目录内（防穿越，规格 §14）。"""

    p = (get_settings().data_dir / rel).resolve()
    data_root = get_settings().data_dir.resolve()
    if data_root not in p.parents:
        raise ValueError(f"非法路径：{rel}")
    return p


def remove_doc_dir(doc_id: str) -> None:
    import shutil

    d = get_settings().storage_dir / doc_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
