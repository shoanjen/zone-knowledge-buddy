"""M9 任务面板 API（规格 §12.1）。"""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import NotFoundError, TaskStateError
from app.models.llm import LLMProvider
from app.models.tasks import AgentTask, AgentTaskStep
from app.models.user import User

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_out(db: Session, t: AgentTask, detail: bool = False) -> dict:
    provider = db.get(LLMProvider, t.provider_id) if t.provider_id else None
    out = {
        "id": t.id,
        "type": t.type,
        "status": t.status,
        "provider_id": t.provider_id,
        "provider_name": provider.name if provider else None,
        "error": t.error,
        "created_at": t.created_at,
        "finished_at": t.finished_at,
    }
    if detail:
        out["input"] = json.loads(t.input_json or "{}")
        out["steps"] = [
            {
                "seq": s.seq,
                "step_type": s.step_type,
                "content": json.loads(s.content_json or "{}"),
                "created_at": s.created_at,
            }
            for s in db.scalars(
                select(AgentTaskStep).where(AgentTaskStep.task_id == t.id).order_by(AgentTaskStep.seq)
            ).all()
        ]
        if t.status == "paused":
            # 待确认任务附上草稿，供前端确认页展示/人工修订（规格 §12.1 confirm 可带修订稿）
            out["draft"] = json.loads(t.draft_json or "{}")
    return out


@router.get("")
def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    type: str = "",
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AgentTask).order_by(AgentTask.created_at.desc())
    if status:
        stmt = stmt.where(AgentTask.status == status)
    if type:
        stmt = stmt.where(AgentTask.type == type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_task_out(db, t) for t in rows]}


@router.get("/{task_id}")
def get_task(
    task_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    t = db.get(AgentTask, task_id)
    if t is None:
        raise NotFoundError(f"任务 {task_id} 不存在")
    return _task_out(db, t, detail=True)


class ConfirmIn(BaseModel):
    approve: bool
    content_md: str | None = None


@router.post("/{task_id}/confirm")
def confirm_task(
    task_id: str,
    body: ConfirmIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    t = db.get(AgentTask, task_id)
    if t is None:
        raise NotFoundError(f"任务 {task_id} 不存在")
    if t.status != "paused":
        raise TaskStateError(f"任务状态为 {t.status}，仅 paused 可确认")
    draft = json.loads(t.draft_json or "{}")
    if not body.approve:
        from app.core.ids import utc_now_iso

        t.error = "user_rejected"
        t.finished_at = utc_now_iso()
        t.status = "failed"
        db.commit()
        return {"ok": True, "status": "failed"}

    content = (body.content_md if body.content_md is not None else draft.get("content_md")) or ""
    from app.agent.orchestrator import finalize_task

    finalize_task(db, t, content, charts=draft.get("charts", []))
    return {"ok": True, "status": t.status}


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    t = db.get(AgentTask, task_id)
    if t is None:
        raise NotFoundError(f"任务 {task_id} 不存在")
    if t.status not in ("pending", "running", "planning", "reflecting", "paused"):
        raise TaskStateError(f"任务状态为 {t.status}，不可取消")
    from app.core.ids import utc_now_iso

    t.status = "cancelled"
    t.finished_at = utc_now_iso()
    db.commit()
    return {"ok": True, "status": "cancelled"}
