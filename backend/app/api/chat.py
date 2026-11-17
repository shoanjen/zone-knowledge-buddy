"""M7 知识问答（规格 §10）：SSE 事件协议 + 会话留痕 + RAG 引用。"""

import json
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.citations import parse_citations
from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import AppError, NotFoundError
from app.core.ids import new_message_id, new_session_id
from app.llm.gateway import GenerationParams
from app.models.chat import ChatMessage, ChatSession
from app.models.documents import Block
from app.models.user import User
from app.schemas.chat import ChatIn, SessionBatchDeleteIn

router = APIRouter(prefix="/api/chat", tags=["chat"])

REFUSAL = "知识库中未找到依据。"

SYSTEM_PROMPT = (
    "仅依据下面的资料片段回答问题；每条结论尾部标注 [doc_id:block_id]；"
    "资料不足以支撑时，只回答：知识库中未找到依据。禁止编造。\n\n资料片段：\n{snippets}"
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(
    body: ChatIn,
    request: Request,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.agent.context import build_gateway
    from app.rag.service import search

    gateway = build_gateway(db, None)
    provider_info = {
        "type": gateway.p.ptype,
        "name": gateway.p.name,
        "model": gateway.p.model,
    }

    # 会话：无则新建（title = 首条消息前 20 字）
    session_id = body.session_id
    if session_id:
        if db.get(ChatSession, session_id) is None:
            raise NotFoundError(f"会话 {session_id} 不存在")
    else:
        session_id = new_session_id()
        db.add(ChatSession(id=session_id, title=body.message[:20]))
        db.commit()
    db.add(
        ChatMessage(
            id=new_message_id(), session_id=session_id, role="user", content=body.message
        )
    )
    db.commit()

    hits = await search(body.message, top_k=body.top_k)
    snippets = "\n\n".join(
        f"[{h['doc_id']} 块 {','.join(h['block_ids']) or '-'}]\n{h['text'][:1200]}" for h in hits
    ) or "（无检索结果）"

    async def gen():
        started = time.monotonic()
        assistant_text = ""
        message_id = new_message_id()
        try:
            yield _sse("meta", {
                "session_id": session_id,
                "message_id": message_id,
                "provider": provider_info,
                "retrieved": [
                    {"chunk_id": h["chunk_id"], "doc_id": h["doc_id"], "score": h["score"]}
                    for h in hits
                ],
            })
            stream = await gateway.chat(
                [{"role": "system", "content": SYSTEM_PROMPT.format(snippets=snippets)},
                 {"role": "user", "content": body.message}],
                task_type="chat",
                params=GenerationParams(),
                stream=True,
            )
            async for delta in stream:
                if await request.is_disconnected():
                    # 客户端已断开：停止消费上游流，且不落库半截回答（§14）
                    return
                assistant_text += delta
                yield _sse("token", {"delta": delta})

            citations = _build_citations(db, assistant_text, hits)
            yield _sse("citations", {"citations": citations})
            yield _sse("done", {
                "usage": {"latency_ms": int((time.monotonic() - started) * 1000)},
                "message_id": message_id,
            })
            db.add(
                ChatMessage(
                    id=message_id, session_id=session_id, role="assistant",
                    content=assistant_text,
                    citations_json=json.dumps(citations, ensure_ascii=False),
                )
            )
            db.commit()
        except AppError as e:
            yield _sse("error", {"code": e.code, "message": e.message})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _build_citations(db: Session, text: str, hits: list[dict]) -> list[dict]:
    by_key = {(h["doc_id"], bid): h for h in hits for bid in h["block_ids"]}
    out = []
    for c in parse_citations(text):
        key = (c["doc_id"], c["block_id"])
        hit = by_key.get(key)
        block = db.scalar(
            select(Block).where(Block.doc_id == c["doc_id"], Block.block_id == c["block_id"])
        )
        out.append({
            "doc_id": c["doc_id"],
            "block_id": c["block_id"],
            "text": (hit["text"][:600] if hit else (block.text if block else None)),
            "origin": hit.get("origin") if hit else None,
            "title": hit.get("title") if hit else None,
        })
    return out


@router.get("/sessions")
def list_sessions(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    rows = db.scalars(select(ChatSession).order_by(ChatSession.created_at.desc())).all()
    return {"items": [{"id": r.id, "title": r.title, "created_at": r.created_at} for r in rows]}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    if db.get(ChatSession, session_id) is None:
        raise NotFoundError(f"会话 {session_id} 不存在")
    rows = (
        db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        .all()
    )
    return {
        "id": session_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": json.loads(m.citations_json) if m.citations_json else [],
                "created_at": m.created_at,
            }
            for m in rows
        ],
    }


def _delete_session(db: Session, session_id: str) -> None:
    # 消息显式删除：SQLite 默认不强制 FK，CASCADE 不可依赖（§14）
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    session = db.get(ChatSession, session_id)
    if session is not None:
        db.delete(session)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if db.get(ChatSession, session_id) is None:
        raise NotFoundError(f"会话 {session_id} 不存在")
    _delete_session(db, session_id)
    db.commit()


@router.post("/sessions/batch-delete")
def batch_delete_sessions(
    body: SessionBatchDeleteIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    deleted = 0
    for sid in body.ids:
        if db.get(ChatSession, sid) is not None:
            _delete_session(db, sid)
            deleted += 1
    db.commit()
    return {"deleted": deleted}
