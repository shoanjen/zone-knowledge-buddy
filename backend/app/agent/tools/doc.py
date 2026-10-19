"""文档清单与 Map-Reduce 摘要工具（规格 §8.3 / §8.6）。"""

from sqlalchemy import select

from app.agent.tools.registry import register
from app.models.documents import Chunk, Document

MAP_REDUCE_THRESHOLD_CHARS = 6000
CHUNK_SUMMARY_PROMPT = "用不超过 100 字概括以下资料片段的要点，只输出要点本身：\n\n{text}"
MERGE_PROMPT = (
    "以下是同一文档各片段的要点，请合并为结构化摘要（背景/方法/结论 三段，"
    "共不超过 300 字），只输出摘要：\n\n{points}"
)
SINGLE_PROMPT = "用不超过 200 字概括以下文档要点，只输出摘要：\n\n{text}"


@register("doc.list", {"type": "object", "properties": {}}, "知识库文档清单")
def doc_list(ctx, args: dict) -> dict:
    stmt = select(Document).where(Document.status == "ready").order_by(Document.imported_at.desc())
    if ctx.doc_scope:
        stmt = stmt.where(Document.id.in_(ctx.doc_scope))
    docs = ctx.db.scalars(stmt).all()
    return {"docs": [
        {"doc_id": d.id, "title": d.title, "source_type": d.source_type, "chunk_count": d.chunk_count}
        for d in docs
    ]}


def summarize_doc(ctx, doc_id: str) -> dict:
    doc = ctx.db.get(Document, doc_id)
    if doc is None:
        return {"error": f"NOT_FOUND: doc {doc_id}"}
    chunks = ctx.db.scalars(
        select(Chunk).where(Chunk.doc_id == doc_id).order_by(Chunk.id)
    ).all()
    texts = [c.text for c in chunks] or [doc.title or doc.origin or ""]
    total = sum(len(t) for t in texts)
    if total > MAP_REDUCE_THRESHOLD_CHARS and len(texts) > 1:
        # Map：逐块要点（顺序执行，批 ≤4 的串行化实现）
        points = []
        for t in texts:
            out = ctx.llm_chat(
                [{"role": "user", "content": CHUNK_SUMMARY_PROMPT.format(text=t[:4000])}],
                task_type="tool",
            )
            points.append(out.strip())
        summary = ctx.llm_chat(
            [{"role": "user", "content": MERGE_PROMPT.format(points="\n".join(f"- {p}" for p in points))}],
            task_type="tool",
        ).strip()
    else:
        summary = ctx.llm_chat(
            [{"role": "user", "content": SINGLE_PROMPT.format(text="\n".join(texts)[:8000])}],
            task_type="tool",
        ).strip()
    return {"summary": summary, "block_count": doc.block_count}


@register(
    "doc.summary",
    {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
    "单文档摘要（长文自动 Map-Reduce）",
)
def doc_summary(ctx, args: dict) -> dict:
    return summarize_doc(ctx, args["doc_id"])
