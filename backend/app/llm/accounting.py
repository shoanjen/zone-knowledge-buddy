"""记账（规格 §2.5 / §5.3）：每次调用一行，成功失败都写。

网关可能运行在任务线程中（无请求级 Session），因此用独立短会话。
"""

from app.core.db import SessionLocal
from app.core.ids import utc_now_iso
from app.models.llm import LLMCallLog


def log_call(
    *,
    provider_id: int | None,
    model: str,
    task_type: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    ok: bool,
    error: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            LLMCallLog(
                provider_id=provider_id,
                model=model,
                task_type=task_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ok=ok,
                error=(error or "")[:500] or None,
                created_at=utc_now_iso(),
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — 记账失败不影响主链路
        db.rollback()
    finally:
        db.close()
