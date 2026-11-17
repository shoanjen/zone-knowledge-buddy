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
            # 幂等重跑：先清旧块（重试/中断残留），避免 UNIQUE(doc_id, block_id) 冲突
            db.query(Block).filter(Block.doc_id == doc.id).delete()
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
            # 存储文件名统一为 original{ext}，解析器拿不到用户原始文件名；
            # Excel 等无标题格式会回退成 "original"，此处保留上传时的原始标题。
            if meta.title and meta.title != "original":
                doc.title = meta.title
            doc.parse_quality = meta.parse_quality
            doc.low_reason = meta.low_reason
            doc.block_count = len(parsed.blocks)
            doc.error = None
            # 仍保持 parsing：分块/向量化完成后才置 ready，避免客户端看到
            # "ready 但 chunk_count=0" 的中间态（§6.2）。
            db.commit()
        except AppError as e:
            db.rollback()  # 清理 flush 失败后的 session 状态，否则后续 commit 抛 PendingRollbackError
            doc.status = "failed"
            doc.error = e.message
            db.commit()
            return
        except Exception as e:  # noqa: BLE001
            db.rollback()  # 同上：必须先 rollback 才能把 failed 状态落库
            doc.status = "failed"
            doc.error = f"{type(e).__name__}: {e}"[:500]
            db.commit()
            return

        # 链式触发分块向量化；pipeline 成功后才把 ready 落库。
        # 任何异常都必须落 failed，否则文档会停在 parsing/ready 且无法重试。
        try:
            from app.rag.pipeline import build_chunks_for_document

            build_chunks_for_document(doc_id)
        except ImportError:
            logger.warning("rag 模块不可用，跳过分块向量化：%s", doc_id)
            db.refresh(doc)
            doc.status = "ready"
            db.commit()
        except Exception as e:  # noqa: BLE001
            logger.exception("分块向量化失败：%s", doc_id)
            db.rollback()
            db.refresh(doc)
            if doc.status != "failed":
                doc.status = "failed"
                doc.error = f"分块向量化失败：{type(e).__name__}: {e}"[:500]
                db.commit()
    finally:
        db.close()


def mark_imported(doc: Document) -> None:  # pragma: no cover - 辅助函数
    doc.imported_at = utc_now_iso()
