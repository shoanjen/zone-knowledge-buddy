"""笔记写入工具（规格 §8.3，仅 note 任务可用）。"""

import json

from app.agent.citations import rebuild_note_citations
from app.agent.tools.registry import register
from app.core.ids import utc_now_iso
from app.models.notes import Note


@register(
    "note.write",
    {"type": "object",
     "properties": {"title": {"type": "string"}, "content_md": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}}},
     "required": ["title", "content_md"]},
    "保存/更新本次任务的笔记草稿",
    task_types={"note.generate"},
)
def note_write(ctx, args: dict) -> dict:
    title = (args.get("title") or "").strip()
    content = (args.get("content_md") or "").strip()
    if not title or not content:
        return {"error": "title 与 content_md 不能为空"}
    tags = args.get("tags") or []
    if ctx.created_note_id:
        note = ctx.db.get(Note, ctx.created_note_id)
        note.title = title
        note.content_md = content
        note.tags_json = json.dumps(tags, ensure_ascii=False)
        note.updated_at = utc_now_iso()
    else:
        note = Note(
            title=title,
            content_md=content,
            tags_json=json.dumps(tags, ensure_ascii=False),
            source_doc_ids_json=json.dumps(ctx.doc_scope),
            task_id=ctx.task_id,
        )
        ctx.db.add(note)
        ctx.db.flush()
        ctx.created_note_id = note.id
    ctx.db.commit()
    rebuild_note_citations(ctx.db, note)
    return {"note_id": ctx.created_note_id}
