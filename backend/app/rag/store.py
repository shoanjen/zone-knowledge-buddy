"""Chroma 向量库封装（规格 §7.2）：collection kb_chunks、cosine、id=chunk_id。"""

import logging
from typing import Any

logger = logging.getLogger("kb.rag")

COLLECTION = "kb_chunks"
_client: Any = None


def _get_client():
    global _client
    if _client is None:
        import chromadb

        from app.core.config import get_settings

        get_settings().chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(get_settings().chroma_dir))
    return _client


def _col():
    return _get_client().get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def add_chunks(items: list[dict[str, Any]]) -> None:
    """items: [{id, vector, text, doc_id, block_ids: [..], section}]"""
    if not items:
        return
    _col().add(
        ids=[i["id"] for i in items],
        embeddings=[i["vector"] for i in items],
        documents=[i["text"] for i in items],
        metadatas=[
            {
                "doc_id": i["doc_id"],
                "block_ids": ",".join(i["block_ids"]),
                "section": i.get("section", ""),
            }
            for i in items
        ],
    )


def delete_vectors_for_doc(doc_id: str) -> None:
    try:
        _col().delete(where={"doc_id": doc_id})
    except Exception:  # noqa: BLE001 — 空库/无该 doc 时静默
        logger.debug("delete vectors skipped for %s", doc_id)


def query(
    vector: list[float],
    *,
    top_k: int = 5,
    doc_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
    res = _col().query(
        query_embeddings=[vector],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for cid, text, meta, dist in zip(ids, docs, metas, dists, strict=False):
        hits.append(
            {
                "chunk_id": cid,
                "doc_id": meta.get("doc_id", ""),
                "block_ids": [b for b in str(meta.get("block_ids", "")).split(",") if b],
                "text": text,
                "section": meta.get("section", ""),
                "score": round(1 - float(dist), 4),
            }
        )
    return hits
