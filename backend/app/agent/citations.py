"""引用标记解析（规格 §2.5 / §9.2）：语法 [d_xxx:bN]，前后端共用正则。"""

import re

from sqlalchemy import select

CITATION_RE = re.compile(r"\[(d_[A-Za-z0-9]+:b\d+)\]")


def parse_citations(content_md: str) -> list[dict]:
    """提取正文中出现的引用（按出现顺序去重）。"""
    seen: set[str] = set()
    out: list[dict] = []
    for m in CITATION_RE.finditer(content_md or ""):
        token = m.group(1)
        if token in seen:
            continue
        seen.add(token)
        doc_id, _, block_id = token.partition(":")
        out.append({"doc_id": doc_id, "block_id": block_id})
    return out


def strip_citation_markers(content_md: str) -> str:
    return CITATION_RE.sub("", content_md or "")


def rebuild_note_citations(db, note) -> None:
    """编辑后按当前正文重建 note_citation；源块不存在标 broken（规格 §9.3）。"""
    from app.models.documents import Block
    from app.models.notes import NoteCitation

    db.query(NoteCitation).filter(NoteCitation.note_id == note.id).delete()
    for c in parse_citations(note.content_md):
        block = db.scalar(
            select(Block).where(Block.doc_id == c["doc_id"], Block.block_id == c["block_id"])
        )
        line = next(
            (
                ln
                for ln in (note.content_md or "").splitlines()
                if f"[{c['doc_id']}:{c['block_id']}]" in ln
            ),
            None,
        )
        db.add(
            NoteCitation(
                note_id=note.id,
                claim_text=(line or "").strip()[:500] or None,
                doc_id=c["doc_id"],
                block_id=c["block_id"],
                broken=block is None,
            )
        )
    db.commit()
