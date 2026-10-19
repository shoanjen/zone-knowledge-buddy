"""解析调度（规格 §6.2）：状态机推进 + 块落库 + 链式触发分块向量化。"""

import json
import logging
from pathlib import Path

from app.core.db import SessionLocal
from app.core.errors import AppError
from app.core.ids import utc_now_iso
from app.models.documents import Block, Document
from app.parsing import excel, md, pdf, web, word
from app.parsing.ir import ParsedDoc

logger = logging.getLogger("kb.parsing")

PARSERS = {"pdf": pdf.parse_pdf, "word": word.parse_word, "md": md.parse_md, "excel": excel.parse_excel}


def _parse(doc: Document) -> ParsedDoc:
    if doc.source_type == "web":
        return web.parse_web(doc.origin)
    fn = PARSERS.get(doc.source_type)
    if fn is None:
        raise AppError(f"不支持的格式：{doc.source_type}")
    # storage 约定：data/storage/{doc_id}/original{ext}
    from app.core.config import get_settings

    storage = get_settings().storage_dir / doc.id
    files = [p for p in storage.glob("original*") if p.is_file()] if storage.exists() else []
    if not files:
        raise AppError("原始文件缺失", detail={"doc_id": doc.id})
    return fn(Path(files[0]))


def run_document_pipeline(doc_id: str) -> None:
    """同步执行：parsing → 解析 → 块落库 → ready → 链式 chunk+embed。"""
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None or doc.status not in ("pending",):
            return
        doc.status = "parsing"
        doc.error = None
        db.commit()
        try:
            parsed = _parse(doc)
            for i, b in enumerate(parsed.blocks, start=1):
                db.add(
                    Block(
                        doc_id=doc.id,
                        seq=i,
                        block_id=f"b{i}",
                        type=b.type,
                        level=b.level,
                        text=b.text,
                        caption=b.caption,
                        data_json=json.dumps(b.data, ensure_ascii=False) if b.data else None,
                        ref=b.ref,
                        ocr_text=b.ocr_text,
                    )
                )
            meta = parsed.meta
            doc.title = meta.title or doc.title
            doc.parse_quality = meta.parse_quality
            doc.low_reason = meta.low_reason
            doc.block_count = len(parsed.blocks)
            doc.status = "ready"
            doc.error = None
            db.commit()
        except AppError as e:
            doc.status = "failed"
            doc.error = e.message
            db.commit()
            return
        except Exception as e:  # noqa: BLE001
            doc.status = "failed"
            doc.error = f"{type(e).__name__}: {e}"[:500]
            db.commit()
            return

        # 链式触发分块向量化（B4 提供；缺席时跳过并告警）
        try:
            from app.rag.pipeline import build_chunks_for_document

            build_chunks_for_document(doc_id)
        except ImportError:
            logger.warning("rag 模块不可用，跳过分块向量化：%s", doc_id)
    finally:
        db.close()


def mark_imported(doc: Document) -> None:  # pragma: no cover - 辅助函数
    doc.imported_at = utc_now_iso()
