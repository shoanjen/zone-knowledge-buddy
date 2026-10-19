"""知识库检索/读取工具（规格 §8.3）。"""

from sqlalchemy import select

from app.agent.tools.registry import register
from app.models.documents import Block, Document


@register(
    "kb.search",
    {"type": "object",
     "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
     "required": ["query"]},
    "语义检索知识库，返回 chunk + 来源",
)
def kb_search(ctx, args: dict) -> dict:
    from app.rag.service import search_sync

    top_k = int(args.get("top_k", 5))
    results = search_sync(
        args["query"], top_k=min(max(top_k, 1), 10), doc_ids=ctx.doc_scope or None
    )
    return {"results": [
        {k: h[k] for k in ("chunk_id", "doc_id", "block_ids", "text", "score")} for h in results
    ]}


@register(
    "kb.read",
    {"type": "object",
     "properties": {"doc_id": {"type": "string"},
                    "block_ids": {"type": "array", "items": {"type": "string"}}},
     "required": ["doc_id", "block_ids"]},
    "读取指定文档的原文块（供引用核对）",
)
def kb_read(ctx, args: dict) -> dict:
    import json

    doc = ctx.db.get(Document, args["doc_id"])
    if doc is None or doc.status != "ready":
        return {"error": f"NOT_FOUND: doc {args['doc_id']}"}
    ids = args.get("block_ids", [])
    rows = ctx.db.scalars(
        select(Block).where(Block.doc_id == args["doc_id"], Block.block_id.in_(ids))
    ).all()
    found = {r.block_id: r for r in rows}
    out = []
    for bid in ids:
        r = found.get(bid)
        if r is None:
            out.append({"block_id": bid, "error": "NOT_FOUND"})
        else:
            out.append({
                "block_id": bid,
                "type": r.type,
                "text": r.text,
                "data": json.loads(r.data_json) if r.data_json else None,
            })
    return {"blocks": out}
