"""引用校验反思（规格 §8.5）：格式查 → 存在查 → 支撑查（批量单次 LLM）。"""

from sqlalchemy import select

from app.agent.citations import parse_citations
from app.models.documents import Block

SUPPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"claim_id": {"type": "integer"}, "supported": {"type": "boolean"}},
                "required": ["claim_id", "supported"],
            },
        }
    },
    "required": ["results"],
}


def _block_text(db, doc_id: str, block_id: str) -> str | None:
    b = db.scalar(select(Block).where(Block.doc_id == doc_id, Block.block_id == block_id))
    if b is None:
        return None
    if b.type == "table" and b.data_json:
        import json

        return json.dumps(json.loads(b.data_json), ensure_ascii=False)[:1500]
    return (b.text or "")[:1500]


def _drop_lines(content: str, tokens: set[str]) -> str:
    return "\n".join(
        ln for ln in content.splitlines()
        if not any(t in ln for t in tokens)
    ).strip()


def reflect(ctx, content_md: str, *, require_citations: bool = True) -> tuple[str, dict]:
    """返回 (修订后内容, 反思报告)。报告结构供 agent_task_step 留痕。"""
    report: dict = {"citations": [], "dropped_invalid": [], "dropped_unsupported": [],
                    "needs_rewrite": False}
    citations = parse_citations(content_md)
    if require_citations and not citations:
        report["needs_rewrite"] = True
        return content_md, report

    # 1) 存在查：不存在的标记整行删除
    invalid_tokens: set[str] = set()
    valid: list[dict] = []
    for c in citations:
        token = f"[{c['doc_id']}:{c['block_id']}]"
        if _block_text(ctx.db, c["doc_id"], c["block_id"]) is None:
            invalid_tokens.add(token)
            report["dropped_invalid"].append(token)
        else:
            valid.append(c)
    if invalid_tokens:
        content_md = _drop_lines(content_md, invalid_tokens)

    if not valid:
        return content_md, report

    # 2) 支撑查：所有有效引用的行 → 一次批量 LLM 判定
    claims = []
    for i, c in enumerate(valid):
        token = f"[{c['doc_id']}:{c['block_id']}"
        line = next(
            (ln for ln in content_md.splitlines() if f"{token}]" in ln), ""
        )
        if not line.strip():
            continue
        evidence = _block_text(ctx.db, c["doc_id"], c["block_id"]) or ""
        claims.append({"claim_id": i, "claim": line.strip()[:400], "evidence": evidence[:1500]})
    if not claims:
        return content_md, report

    prompt = (
        "逐条判断 claim 是否被 evidence 支撑（语义包含或可合理推出）。"
        '输出 {"results":[{"claim_id":0,"supported":true},...]}\n\n'
        + "\n\n".join(
            f"### claim {c['claim_id']}\n{c['claim']}\n### evidence {c['claim_id']}\n{c['evidence']}"
            for c in claims
        )
    )
    try:
        out = ctx.llm_json([{"role": "user", "content": prompt}], SUPPORT_SCHEMA,
                           task_type="reflect")
        verdicts = {r["claim_id"]: r["supported"] for r in out.get("results", [])}
    except Exception:  # noqa: BLE001 — 支撑查失败保守放行（存在查已兜底）
        verdicts = {}

    unsupported_tokens: set[str] = set()
    for c in claims:
        if verdicts.get(c["claim_id"]) is False:
            token = f"[{valid[c['claim_id']]['doc_id']}:{valid[c['claim_id']]['block_id']}]"
            unsupported_tokens.add(token)
            report["dropped_unsupported"].append(token)
    if unsupported_tokens:
        content_md = _drop_lines(content_md, unsupported_tokens)

    report["citations"] = valid
    return content_md, report
