"""检索服务（规格 §7.3）。"""

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.documents import Document


def search_sync(
    query: str, *, top_k: int = 5, doc_ids: list[str] | None = None
) -> list[dict]:
    from app.llm.gateway import embed_texts
    from app.rag.store import query as chroma_query

    vectors = asyncio.run(embed_texts([query]))
    hits = chroma_query(vectors[0], top_k=top_k, doc_ids=doc_ids)
    if not hits:
        return []
    # 补充来源标题/origin
    db = SessionLocal()
    try:
        docs = {
            d.id: d
            for d in db.scalars(
                select(Document).where(Document.id.in_([h["doc_id"] for h in hits]))
            ).all()
        }
        for h in hits:
            d = docs.get(h["doc_id"])
            h["title"] = d.title if d else None
            h["origin"] = d.origin if d else None
        return hits
    finally:
        db.close()


async def search(
    query: str, *, top_k: int = 5, doc_ids: list[str] | None = None
) -> list[dict]:
    return await asyncio.to_thread(search_sync, query, top_k=top_k, doc_ids=doc_ids)
