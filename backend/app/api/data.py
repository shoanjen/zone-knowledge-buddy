"""M9 数据导出（规格 §12.4）：zip 备份（sqlite 在线备份 + chroma + storage）。"""

import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ids import utc_now_iso
from app.models.user import User

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/export")
def export(
    _: User = Depends(get_current_user),
    __db: Session = Depends(get_db),
) -> FileResponse:
    s = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="kb-export-"))
    zip_path = tmp / f"zone-kb-backup-{utc_now_iso()[:10].replace('-', '')}.zip"

    # sqlite 在线备份到临时文件
    db_copy = tmp / "kb.sqlite3"
    src = sqlite3.connect(str(s.sqlite_path))
    dst = sqlite3.connect(str(db_copy))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_copy, "kb.sqlite3")
        for base, name in ((s.chroma_dir, "chroma"), (s.storage_dir, "storage")):
            if base.exists():
                for p in base.rglob("*"):
                    if p.is_file():
                        zf.write(p, f"{name}/{p.relative_to(base)}")

    def _cleanup() -> None:
        shutil.rmtree(tmp, ignore_errors=True)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
        # 响应发送完毕后清理临时目录，避免每次导出都残留一份全量备份
        background=BackgroundTask(_cleanup),
    )
