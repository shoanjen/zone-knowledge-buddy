"""播客 API：生成（202 异步任务）/ 列表 / 详情（含脚本）/ 音频 / 删除。"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import NotFoundError, ValidationError
from app.models.documents import Document
from app.models.podcasts import Podcast
from app.models.tasks import AgentTask
from app.models.user import User
from app.podcast.tts import STYLES, VOICES
from app.schemas.podcasts import PodcastGenerateIn
from app.tasks.runner import submit

router = APIRouter(prefix="/api/podcasts", tags=["podcasts"])


@router.get("/voices")
def list_voices(_: User = Depends(get_current_user)) -> dict:
    """主播音色与节目风格预设（生成对话框数据源）。"""

    return {
        "voices": [{"id": vid, "label": label} for vid, label in VOICES.items()],
        "styles": list(STYLES),
    }


@router.post("/generate", status_code=202)
def generate_podcast(
    body: PodcastGenerateIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.style not in STYLES:
        raise ValidationError(f"不支持的节目风格：{body.style}", detail={"styles": list(STYLES)})
    if body.voice_a not in VOICES or body.voice_b not in VOICES:
        raise ValidationError(
            "不支持的主播音色",
            detail={"voices": list(VOICES)},
        )
    if body.voice_a == body.voice_b:
        raise ValidationError("两位主播需选择不同音色")

    docs = db.scalars(select(Document).where(Document.id.in_(body.doc_ids))).all()
    found = {d.id for d in docs}
    not_ready = [d.id for d in docs if d.status != "ready"]
    missing = [i for i in body.doc_ids if i not in found]
    if missing or not_ready:
        raise ValidationError("文档不可用", detail={"missing": missing, "not_ready": not_ready})

    from app.api.settings import get_active_provider

    provider = get_active_provider(db)
    task = AgentTask(
        type="podcast.generate",
        status="pending",
        provider_id=provider.id,
        input_json=json.dumps(
            {
                "doc_ids": body.doc_ids,
                "intent": body.intent,
                "title": body.title,
                "style": body.style,
                "voice_a": body.voice_a,
                "voice_b": body.voice_b,
            },
            ensure_ascii=False,
        ),
    )
    db.add(task)
    db.commit()
    from app.podcast.runner import run_podcast_task

    submit(run_podcast_task, task.id)
    return {"task_id": task.id}


def _podcast_out(p: Podcast, *, detail: bool = False) -> dict:
    out = {
        "id": p.id,
        "title": p.title,
        "intent": p.intent,
        "style": p.style,
        "has_audio": bool(p.audio_path and Path(p.audio_path).exists()),
        "duration_s": p.duration_s,
        "voice_a": p.voice_a,
        "voice_b": p.voice_b,
        "source_doc_ids": json.loads(p.source_doc_ids_json or "[]"),
        "task_id": p.task_id,
        "created_at": p.created_at,
    }
    if detail:
        out["turns"] = json.loads(p.script_json or "[]")
    return out


@router.get("")
def list_podcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Podcast).order_by(Podcast.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_podcast_out(p) for p in rows]}


@router.get("/{podcast_id}")
def get_podcast(
    podcast_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    p = db.get(Podcast, podcast_id)
    if p is None:
        raise NotFoundError(f"播客 {podcast_id} 不存在")
    return _podcast_out(p, detail=True)


@router.get("/{podcast_id}/audio")
def get_podcast_audio(
    podcast_id: str,
    download: int = 0,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    p = db.get(Podcast, podcast_id)
    if p is None:
        raise NotFoundError(f"播客 {podcast_id} 不存在")
    if not p.audio_path or not Path(p.audio_path).exists():
        raise NotFoundError("播客音频不存在（可能生成失败）")
    headers = (
        {"Content-Disposition": f'attachment; filename="{podcast_id}.mp3"'} if download else None
    )
    return FileResponse(p.audio_path, media_type="audio/mpeg", headers=headers)


@router.delete("/{podcast_id}", status_code=204)
def delete_podcast(
    podcast_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    p = db.get(Podcast, podcast_id)
    if p is None:
        raise NotFoundError(f"播客 {podcast_id} 不存在")
    if p.audio_path:
        Path(p.audio_path).unlink(missing_ok=True)
    db.delete(p)
    db.commit()
