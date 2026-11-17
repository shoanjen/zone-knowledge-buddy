"""分块向量化流水线（规格 §7.2）：解析 ready 后链式触发；重试幂等（先清旧）。"""

import asyncio
import json
import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.errors import GatewayError
from app.core.ids import new_chunk_id, utc_now_iso
from app.models.documents import Block, Chunk, Document
from app.models.settings import Setting
from app.rag.chunking import chunk_blocks
from app.rag.store import add_chunks, delete_vectors_for_doc

logger = logging.getLogger("kb.rag")


def _ensure_embedding_lock(db) -> None:
    """首条向量写入后锁定 embedding 配置（规格 §12.3）。"""
    row = db.get(Setting, "embedding")
    if row is None:
        cfg = {"provider_type": "local-ollama", "locked_at": utc_now_iso()}
        db.add(Setting(key="embedding", value_json=json.dumps(cfg)))
    else:
        try:
            cfg = json.loads(row.value_json)
        except Exception:  # noqa: BLE001
            cfg = {}
        if not cfg.get("locked_at"):
            cfg["locked_at"] = utc_now_iso()
            row.value_json = json.dumps(cfg, ensure_ascii=False)
    db.commit()


def build_chunks_for_document(doc_id: str) -> None:
    """解析完成后同步执行：分块 → embedding → Chroma → ready。

    调用方（dispatcher）在解析阶段保持 status=parsing；本函数成功后才置
    ready，任何失败都置 failed，保证前端看到的 ready 一定带可用 chunk。
    """
    from app.llm.gateway import embed_texts

    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None or doc.status not in ("parsing", "ready"):
            return
        blocks = db.scalars(
            select(Block).where(Block.doc_id == doc_id).order_by(Block.seq)
        ).all()
        dicts = [
            {
                "block_id": b.block_id,
                "type": b.type,
                "level": b.level,
                "text": b.text,
                "caption": b.caption,
                "data": json.loads(b.data_json) if b.data_json else None,
                "ocr_text": b.ocr_text,
            }
            for b in blocks
        ]
        chunks = chunk_blocks(dicts)

        # 幂等：清旧 chunk 与向量
        db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        db.commit()
        delete_vectors_for_doc(doc_id)

        if not chunks:
            doc.chunk_count = 0
            doc.status = "ready"
            doc.error = None
            db.commit()
            return

        try:
            vectors = asyncio.run(embed_texts([c["text"] for c in chunks]))
        except GatewayError as e:
            doc.status = "failed"
            doc.error = f"embedding: {e}"[:500]
            db.commit()
            return

        try:
            items = []
            for c, vec in zip(chunks, vectors, strict=True):
                cid = new_chunk_id()
                db.add(
                    Chunk(
                        id=cid,
                        doc_id=doc_id,
                        block_ids_json=json.dumps(c["block_ids"]),
                        text=c["text"],
                        vector_id=cid,
                    )
                )
                items.append(
                    {
                        "id": cid,
                        "vector": vec,
                        "text": c["text"],
                        "doc_id": doc_id,
                        "block_ids": c["block_ids"],
                        "section": c.get("section", ""),
                    }
                )
            # 规格 §7.2：首条向量写入前锁定 embedding 配置
            _ensure_embedding_lock(db)
            add_chunks(items)
            doc.chunk_count = len(items)
            doc.status = "ready"
            doc.error = None
            db.commit()
        except Exception as e:  # noqa: BLE001
            logger.exception("写入向量库失败：%s", doc_id)
            db.rollback()
            db.refresh(doc)
            doc.status = "failed"
            doc.error = f"向量写入失败：{type(e).__name__}: {e}"[:500]
            db.commit()
    finally:
        db.close()
