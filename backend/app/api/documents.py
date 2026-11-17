"""M3 文档接入 API（规格 §6.1）。"""

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import (
    DocStateError,
    NotFoundError,
    UploadFormatError,
    UploadTooLargeError,
    UrlInvalidError,
    ValidationError,
)
from app.core.ids import new_doc_id, utc_now_iso
from app.models.documents import Block, Chunk, Document
from app.models.user import User
from app.parsing.dispatcher import run_document_pipeline
from app.parsing.storage import remove_doc_dir, save_original
from app.tasks.runner import submit

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXT = {".pdf", ".docx", ".md", ".xlsx"}
EXT_TO_TYPE = {".pdf": "pdf", ".docx": "word", ".md": "md", ".xlsx": "excel"}
_MAGIC = {
    b"%PDF": ".pdf",
    b"PK\x03\x04": {".docx", ".xlsx"},  # zip 头二选一，按扩展名为准
}


def _check_upload(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadFormatError(f"不支持的格式 {ext}（白名单：{' '.join(sorted(ALLOWED_EXT))}）")
    s = get_settings()
    if len(content) > s.kb_max_upload_mb * 1024 * 1024:
        raise UploadTooLargeError(f"文件超过 {s.kb_max_upload_mb}MB 上限")
    # magic bytes 二次校验（规格 §14）
    if ext == ".pdf" and not content.startswith(b"%PDF"):
        raise UploadFormatError("文件内容不是有效 PDF")
    if ext in (".docx", ".xlsx") and not content.startswith(b"PK"):
        raise UploadFormatError("文件内容不是有效的 Office 文档")
    return ext


def _create_doc(db: Session, source_type: str, origin: str, title: str | None) -> Document:
    doc = Document(
        id=new_doc_id(),
        source_type=source_type,
        origin=origin,
        title=title,
        status="pending",
        imported_at=utc_now_iso(),
    )
    db.add(doc)
    db.commit()
    return doc


@router.post("/upload", status_code=202)
def upload(
    files: list[UploadFile],
    background: BackgroundTasks,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """多文件上传：逐文件校验，成功入库、失败计入 errors（规格 §6.1）。

    先读入并校验全部文件再落库，避免“后一个文件非法导致前一个已建文档
    永久停在 pending”的孤儿；单文件非法仍返回 413/415。
    """
    s = get_settings()
    if len(files) > s.kb_max_upload_files:
        raise ValidationError(f"单次最多上传 {s.kb_max_upload_files} 个文件")
    prepared: list[tuple[str, str, bytes]] = []
    errors: list[dict] = []
    for f in files:
        content = f.file.read()
        try:
            ext = _check_upload(f.filename or "file", content)
            prepared.append((ext, f.filename or "file", content))
        except (UploadFormatError, UploadTooLargeError) as e:
            if len(files) == 1:
                raise
            errors.append({"filename": f.filename, "code": e.code, "message": e.message})

    items = []
    for ext, filename, content in prepared:
        doc = _create_doc(db, EXT_TO_TYPE[ext], filename, Path(filename).stem)
        save_original(doc.id, filename, content)
        items.append({"doc_id": doc.id, "filename": filename, "status": doc.status})
        background.add_task(submit, run_document_pipeline, doc.id)
    return {"items": items, "errors": errors}


@router.post("/url", status_code=202)
def import_url(
    body: dict,
    background: BackgroundTasks,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    url = (body or {}).get("url", "")
    if not url.startswith(("http://", "https://")):
        raise UrlInvalidError("URL 必须以 http(s):// 开头")
    doc = _create_doc(db, "web", url, None)
    background.add_task(submit, run_document_pipeline, doc.id)
    return {"doc_id": doc.id, "status": doc.status}


def _doc_out(d: Document) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "source_type": d.source_type,
        "origin": d.origin,
        "status": d.status,
        "parse_quality": d.parse_quality,
        "low_reason": d.low_reason,
        "error": d.error,
        "block_count": d.block_count,
        "chunk_count": d.chunk_count,
        "imported_at": d.imported_at,
    }


@router.get("")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_type: str = "",
    q: str = "",
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Document).order_by(Document.imported_at.desc())
    if source_type:
        stmt = stmt.where(Document.source_type == source_type)
    if q:
        stmt = stmt.where((Document.title.like(f"%{q}%")) | (Document.origin.like(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_doc_out(d) for d in rows]}


@router.get("/{doc_id}")
def get_document(
    doc_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    blocks = db.scalars(
        select(Block).where(Block.doc_id == doc_id).order_by(Block.seq).limit(5001)
    ).all()
    out = _doc_out(doc)
    truncated = False
    if len(blocks) > 5000:
        blocks = blocks[:5000]
        truncated = True
    out["blocks_truncated"] = truncated
    out["blocks"] = [
        {
            "block_id": b.block_id,
            "type": b.type,
            "level": b.level,
            "text": b.text,
            "caption": b.caption,
            "data": json.loads(b.data_json) if b.data_json else None,
            "ref": b.ref,
        }
        for b in blocks
    ]
    return out


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    if doc.status == "parsing":
        raise DocStateError("文档解析中，请等待完成后再删除")
    db.query(Block).filter(Block.doc_id == doc_id).delete()
    db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
    db.delete(doc)
    db.commit()
    remove_doc_dir(doc_id)
    # 向量删除联动（rag 模块提供；缺席时跳过）
    try:
        from app.rag.store import delete_vectors_for_doc

        delete_vectors_for_doc(doc_id)
    except ImportError:
        pass


@router.post("/{doc_id}/retry", status_code=202)
def retry_document(
    doc_id: str,
    background: BackgroundTasks,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    if doc.status != "failed":
        raise DocStateError("仅 failed 状态可重试")
    doc.status = "pending"
    db.commit()
    background.add_task(submit, run_document_pipeline, doc.id)
    return {"doc_id": doc.id, "status": doc.status}
