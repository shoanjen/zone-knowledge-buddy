"""M6 笔记模块（规格 §9）。"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.citations import rebuild_note_citations
from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utc_now_iso
from app.models.documents import Block, Document
from app.models.notes import Note, NoteCitation
from app.models.tasks import AgentTask
from app.models.user import User
from app.schemas.notes import NoteGenerateIn, NoteUpdateIn
from app.tasks.runner import submit

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.post("/generate", status_code=202)
def generate_note(
    body: NoteGenerateIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    docs = db.scalars(select(Document).where(Document.id.in_(body.doc_ids))).all()
    found = {d.id for d in docs}
    missing = [i for i in body.doc_ids if i not in found]
    not_ready = [d.id for d in docs if d.status != "ready"]
    if missing or not_ready:
        raise ValidationError(
            "文档不可用",
            detail={"missing": missing, "not_ready": not_ready},
        )
    from app.api.settings import get_active_provider

    provider = get_active_provider(db)
    task = AgentTask(
        type="note.generate",
        status="pending",
        provider_id=provider.id,
        input_json=json.dumps(
            {
                "doc_ids": body.doc_ids,
                "intent": body.intent,
                "confirm_required": body.confirm_required,
            },
            ensure_ascii=False,
        ),
    )
    db.add(task)
    db.commit()
    from app.agent.orchestrator import run_agent_task

    submit(run_agent_task, task.id)
    return {"task_id": task.id}


def _note_out(db: Session, n: Note, detail: bool = False) -> dict:
    out = {
        "id": n.id,
        "title": n.title,
        "tags": json.loads(n.tags_json or "[]"),
        "source_doc_ids": json.loads(n.source_doc_ids_json or "[]"),
        "task_id": n.task_id,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
    }
    if detail:
        out["content_md"] = n.content_md
        cits = []
        for c in db.scalars(select(NoteCitation).where(NoteCitation.note_id == n.id)).all():
            block = db.scalar(
                select(Block).where(Block.doc_id == c.doc_id, Block.block_id == c.block_id)
            )
            cits.append(
                {
                    "doc_id": c.doc_id,
                    "block_id": c.block_id,
                    "claim_text": c.claim_text,
                    "broken": c.broken or block is None,
                    "block_text": (block.text if block else None)
                    or (block.data_json if block else None),
                }
            )
        out["citations"] = cits
    return out


@router.get("")
def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = "",
    tag: str = "",
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Note).order_by(Note.updated_at.desc())
    if q:
        stmt = stmt.where((Note.title.like(f"%{q}%")) | (Note.content_md.like(f"%{q}%")))
    if tag:
        stmt = stmt.where(Note.tags_json.like(f'%"{tag}"%'))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_note_out(db, n) for n in rows]}


@router.get("/{note_id}")
def get_note(
    note_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    n = db.get(Note, note_id)
    if n is None:
        raise NotFoundError(f"笔记 {note_id} 不存在")
    return _note_out(db, n, detail=True)


@router.put("/{note_id}")
def update_note(
    note_id: str,
    body: NoteUpdateIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    n = db.get(Note, note_id)
    if n is None:
        raise NotFoundError(f"笔记 {note_id} 不存在")
    if body.title is not None:
        n.title = body.title
    if body.content_md is not None:
        n.content_md = body.content_md
    if body.tags is not None:
        n.tags_json = json.dumps(body.tags, ensure_ascii=False)
    n.updated_at = utc_now_iso()
    db.commit()
    rebuild_note_citations(db, n)
    return _note_out(db, n, detail=True)


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    n = db.get(Note, note_id)
    if n is None:
        raise NotFoundError(f"笔记 {note_id} 不存在")
    db.query(NoteCitation).filter(NoteCitation.note_id == note_id).delete()
    db.delete(n)
    db.commit()
