"""Agent 编排主循环（规格 §8.1/§8.4）：状态机 + 步骤留痕 + 护栏 + 人工确认。"""

import json
import logging

from sqlalchemy import select

from app.agent.context import TaskContext, build_gateway
from app.agent.executor import build_system, run_step
from app.agent.planner import make_plan
from app.agent.reflection import reflect
from app.core.db import SessionLocal
from app.core.ids import utc_now_iso
from app.models.documents import Document
from app.models.tasks import AgentTask, AgentTaskStep

logger = logging.getLogger("kb.agent")

MAX_STEPS = 12
MAX_DUPL = 3
OBS_TRUNCATE = 4000

FINAL_HINTS = {
    "note.generate": (
        "最终笔记格式：# 标题 / ## 摘要 / ## 要点（每条一行，行尾引用标记）/ ## 开放问题。"
        "完成后调用 note.write 工具保存，再输出 final。"
    ),
    "report.generate": "按大纲逐节产出内容，每节结论带引用标记。",
}


def _log_step(db, task_id: str, seq: list[int], step_type: str, content: dict) -> None:
    db.add(
        AgentTaskStep(
            task_id=task_id,
            seq=seq[0],
            step_type=step_type,
            content_json=json.dumps(content, ensure_ascii=False),
        )
    )
    db.commit()
    seq[0] += 1


def _set_status(db, task: AgentTask, status: str, error: str | None = None) -> None:
    task.status = status
    if error is not None:
        task.error = error[:500]
    if status in ("done", "failed", "cancelled"):
        task.finished_at = utc_now_iso()
    db.commit()


def _shrink_strings(value, limit: int):
    """递归截短字符串，保留结构（用于观测结果超长时）。"""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, list):
        return [_shrink_strings(v, limit) for v in value]
    if isinstance(value, dict):
        return {k: _shrink_strings(v, limit) for k, v in value.items()}
    return value


def truncate_observation(result) -> tuple[str, dict]:
    """把工具结果压到 OBS_TRUNCATE 以内，且保证返回的字符串仍是合法 JSON。

    直接对 json.dumps 结果切片会截断字符串/括号，随后 json.loads 必失败；
    这里优先按字段截短，仍超限则退化为带 preview 的合法结构。
    """
    raw = json.dumps(result, ensure_ascii=False)
    if len(raw) <= OBS_TRUNCATE:
        return raw, result
    for limit in (1200, 800, 500, 300, 150, 80, 40):
        trimmed = _shrink_strings(result, limit)
        candidate = json.dumps(trimmed, ensure_ascii=False)
        if len(candidate) <= OBS_TRUNCATE:
            return candidate, trimmed
    fallback = {
        "truncated": True,
        "preview": raw[: max(OBS_TRUNCATE - 80, 0)],
    }
    return json.dumps(fallback, ensure_ascii=False), fallback


def run_agent_task(task_id: str) -> None:
    """线程池入口：planning → running(ReAct) → reflecting → done/paused/failed。"""
    import app.agent.tools.chart  # noqa: F401 注册
    import app.agent.tools.doc  # noqa: F401
    import app.agent.tools.kb  # noqa: F401
    import app.agent.tools.note  # noqa: F401

    db = SessionLocal()
    try:
        task = db.get(AgentTask, task_id)
        if task is None or task.status != "pending":
            return
        try:
            gateway = build_gateway(db, task.provider_id)
        except Exception as e:  # noqa: BLE001
            _set_status(db, task, "failed", f"{e}")
            return
        input_data = json.loads(task.input_json or "{}")
        ctx = TaskContext(
            db=db, gateway=gateway, task_id=task_id, task_type=task.type,
            doc_scope=input_data.get("doc_ids") or [],
        )
        seq = [1]
        _set_status(db, task, "planning")

        # ---- 规划 ----
        docs_brief = [
            {"doc_id": d.id, "title": d.title or d.origin}
            for d in (
                db.scalars(select(Document).where(Document.id.in_(ctx.doc_scope))).all()
                if ctx.doc_scope else []
            )
        ]
        try:
            steps = make_plan(ctx, input_data.get("intent", ""), docs_brief)
        except Exception as e:  # noqa: BLE001
            _set_status(db, task, "failed", f"规划失败：{e}")
            return
        _log_step(db, task_id, seq, "thought", {"phase": "plan", "steps": steps})

        # ---- ReAct 循环 ----
        _set_status(db, task, "running")
        system = build_system(ctx, json.dumps(steps, ensure_ascii=False),
                              FINAL_HINTS.get(task.type, ""))
        history: list[dict] = [{"role": "user", "content": input_data.get("intent", "")}]
        dup_counter: dict[str, int] = {}
        final_content = ""
        try:
            for _ in range(MAX_STEPS):
                if ctx.is_cancelled():
                    _set_status(db, task, "cancelled")
                    return
                step_out = run_step(ctx, system, history)
                thought = step_out.get("thought") or ""
                if thought:
                    _log_step(db, task_id, seq, "thought", {"thought": thought[:1000]})
                if step_out.get("type") == "final":
                    final_content = step_out.get("content") or ""
                    history.append({"role": "assistant", "content": json.dumps(step_out, ensure_ascii=False)})
                    break
                tool_name, args = step_out.get("tool", ""), step_out.get("args") or {}
                if not tool_name:
                    history.append({"role": "assistant", "content": json.dumps(step_out, ensure_ascii=False)})
                    history.append({"role": "user",
                                    "content": '输出无效：type 只能是 "tool"（需带 tool/args）或 "final"。'})
                    continue
                dup_key = f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
                dup_counter[dup_key] = dup_counter.get(dup_key, 0) + 1
                if dup_counter[dup_key] >= MAX_DUPL:
                    _set_status(db, task, "failed", f"loop_detected: {tool_name} 重复调用")
                    return
                _log_step(db, task_id, seq, "tool", {"tool": tool_name, "args": args})
                from app.agent.tools.registry import call_tool

                result = call_tool(ctx, tool_name, args)
                obs, obs_obj = truncate_observation(result)
                _log_step(db, task_id, seq, "observation",
                          {"tool": tool_name, "result": obs_obj})
                history.append({"role": "assistant", "content": json.dumps(step_out, ensure_ascii=False)})
                history.append({"role": "user", "content": f"工具结果：{obs}"})
            else:
                _set_status(db, task, "failed", f"达到最大步数 {MAX_STEPS} 仍未产出 final")
                return
        except Exception as e:  # noqa: BLE001
            _set_status(db, task, "failed", f"{type(e).__name__}: {e}")
            return

        if not final_content.strip():
            _set_status(db, task, "failed", "final 内容为空")
            return

        # ---- 反思 ----
        _set_status(db, task, "reflecting")
        content, report = reflect(ctx, final_content)
        if report.get("needs_rewrite"):
            # 无引用：带反馈重写一次（规格 §8.5）
            retry = run_step(ctx, system, history,
                             feedback="产出缺少引用标记，请检索资料后重写，"
                                      "每条结论带 [doc_id:block_id]。")
            if retry.get("type") == "final" and retry.get("content"):
                content, report = reflect(ctx, retry["content"])
                _log_step(db, task_id, seq, "reflection",
                          {"retry": True, "report": report})
        _log_step(db, task_id, seq, "reflection", {"report": report})

        # ---- 终态化 ----
        try:
            if input_data.get("confirm_required"):
                task.draft_json = json.dumps(
                    {"content_md": content, "charts": ctx.scratch.get("charts", [])},
                    ensure_ascii=False,
                )
                _set_status(db, task, "paused")
                return
            finalize_task(db, task, content, charts=ctx.scratch.get("charts", []), note_ctx=ctx)
        except Exception as e:  # noqa: BLE001
            logger.exception("任务产出落库失败：%s", task_id)
            db.rollback()
            db.refresh(task)
            _set_status(db, task, "failed", f"产出落库失败：{type(e).__name__}: {e}")
    finally:
        db.close()


def finalize_task(db, task: AgentTask, content_md: str, *, charts: list | None = None,
                  note_ctx: TaskContext | None = None) -> None:
    """done 落库：note 生成/更新 Note；report 走渲染（B7 提供）。"""
    from app.agent.citations import rebuild_note_citations
    from app.models.notes import Note

    if task.type == "note.generate":
        title = next(
            (ln.lstrip("# ").strip() for ln in content_md.splitlines()
             if ln.startswith("# ") and ln.strip() != "#"),
            "未命名笔记",
        )
        note = None
        if note_ctx is not None and note_ctx.created_note_id:
            note = db.get(Note, note_ctx.created_note_id)
        if note is None:
            # confirm 路径没有 note_ctx：复用 note.write 在 paused 前落库的草稿，
            # 避免同一任务生成两条笔记；拒绝分支由 tasks.py 负责清理。
            note = db.scalar(select(Note).where(Note.task_id == task.id))
        if note is not None:
            note.content_md = content_md
            note.title = title
            note.updated_at = utc_now_iso()
        else:
            note = Note(
                title=title,
                content_md=content_md,
                source_doc_ids_json=json.dumps(json.loads(task.input_json or "{}").get("doc_ids", [])),
                task_id=task.id,
            )
            db.add(note)
            db.flush()
        db.commit()
        rebuild_note_citations(db, note)
    elif task.type == "report.generate":
        from app.report.builder import build_report

        build_report(db, task, content_md, charts=charts or [])
    _set_status(db, task, "done")
