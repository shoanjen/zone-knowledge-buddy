"""播客生成流水线：素材汇总 → LLM 双人脚本 → 逐轮 TTS → MP3 落盘。

不走 ReAct 编排（无工具循环），但仍复用 AgentTask/AgentTaskStep 留痕，
任务中心可见进度（planning=写脚本 / running=合成音频）。
"""

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.agent.context import build_gateway
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.core.ids import new_podcast_id, utc_now_iso
from app.models.documents import Block, Document
from app.models.podcasts import Podcast
from app.models.tasks import AgentTask, AgentTaskStep
from app.podcast.tts import (
    DEFAULT_VOICE_A,
    DEFAULT_VOICE_B,
    estimate_duration_s,
    synth_dialogue,
)

logger = logging.getLogger("kb.podcast")

MAX_TURNS = 30
MIN_TURNS = 4
PER_DOC_CHARS = 7000
TOTAL_CHARS = 14000

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 2, "maxLength": 80},
        "turns": {
            "type": "array",
            "minItems": MIN_TURNS,
            "maxItems": MAX_TURNS,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["A", "B"]},
                    "text": {"type": "string", "minLength": 2, "maxLength": 500},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "turns"],
    "additionalProperties": False,
}


def build_content_pack(db, doc_ids: list[str]) -> str:
    """把所选文档的文本块压成素材包（每篇/总量截断，防止 prompt 爆长）。"""

    docs = db.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
    parts: list[str] = []
    remaining = TOTAL_CHARS
    for doc in docs:
        if remaining <= 0:
            break
        blocks = db.scalars(
            select(Block).where(Block.doc_id == doc.id).order_by(Block.seq)
        ).all()
        lines: list[str] = [f"# {doc.title or doc.origin}"]
        used = 0
        for b in blocks:
            text = (b.text or "").strip()
            if not text:
                continue
            if used + len(text) > PER_DOC_CHARS:
                text = text[: PER_DOC_CHARS - used]
            lines.append(text)
            used += len(text)
            if used >= PER_DOC_CHARS:
                break
        part = "\n".join(lines)[:remaining]
        parts.append(part)
        remaining -= len(part)
    return "\n\n".join(parts)


def make_script_messages(intent: str, style: str, content_pack: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "你是一位资深播客主编，擅长把资料改写成两位主持人自然对话的播客脚本。",
        },
        {
            "role": "user",
            "content": (
                "请把下面的资料改写成一期双人播客的完整脚本。\n\n"
                "要求：\n"
                f"- 风格：{style}\n"
                "- 两位主持人：A 负责主讲，B 负责搭话、追问与接梗；对话要像真人聊天，口语自然，不是朗读稿\n"
                "- 开头 1-2 轮自然引入话题，结尾 1-2 轮总结收束\n"
                f"- 总共 10-20 轮对话，每轮 1-3 句话、不超过 120 字\n"
                "- 只使用资料中的事实，不要编造；可口语化转述，但不要出现「根据资料」这类书面表达\n"
                "- text 内不要带动作提示、括号注释或 markdown 记号\n"
                f"- 围绕用户的关注点组织内容：{intent}\n\n"
                f"【资料】\n{content_pack}"
            ),
        },
    ]


def clean_turns(raw_turns: list) -> list[dict]:
    """模型输出兜底清洗：规范化说话人、去空轮、硬截上限。"""

    turns = []
    for t in raw_turns:
        speaker = str(t.get("speaker") or "A").strip().upper()
        if speaker not in ("A", "B"):
            speaker = "A"
        text = str(t.get("text") or "").strip()
        if len(text) >= 2:
            turns.append({"speaker": speaker, "text": text})
    return turns[:MAX_TURNS]


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


def run_podcast_task(task_id: str) -> None:
    """线程池入口：planning（脚本）→ running（TTS）→ done/failed/cancelled。"""

    db = SessionLocal()
    seq = [1]
    audio_path: Path | None = None
    try:
        task = db.get(AgentTask, task_id)
        if task is None or task.status != "pending":
            return
        input_data = json.loads(task.input_json or "{}")
        doc_ids = input_data.get("doc_ids") or []
        intent = input_data.get("intent", "")
        style = input_data.get("style", "轻松闲聊")
        voice_a = input_data.get("voice_a") or DEFAULT_VOICE_A
        voice_b = input_data.get("voice_b") or DEFAULT_VOICE_B

        try:
            gateway = build_gateway(db, task.provider_id)
        except Exception as e:  # noqa: BLE001
            _set_status(db, task, "failed", f"{e}")
            return

        def _cancelled() -> bool:
            fresh = db.get(AgentTask, task_id)
            return fresh is None or fresh.status == "cancelled"

        # ---- 阶段一：脚本 ----
        _set_status(db, task, "planning")
        content_pack = build_content_pack(db, doc_ids)
        _log_step(db, task_id, seq, "thought",
                  {"phase": "script",
                   "thought": f"汇总 {len(doc_ids)} 篇文档素材（{len(content_pack)} 字），"
                              "开始撰写双人播客脚本"})
        try:
            result = asyncio.run(
                gateway.chat_json(
                    make_script_messages(intent, style, content_pack),
                    SCRIPT_SCHEMA,
                    task_type="chat",
                )
            )
        except AppError as e:
            _set_status(db, task, "failed", f"脚本生成失败：{e}")
            return
        turns = clean_turns(result.get("turns") or [])
        if len(turns) < MIN_TURNS:
            _set_status(db, task, "failed", f"脚本轮数不足（{len(turns)} 轮），请重试")
            return
        title = (result.get("title") or input_data.get("title") or "未命名播客").strip()
        _log_step(db, task_id, seq, "thought",
                  {"phase": "script.done",
                   "thought": f"脚本完成：《{title}》共 {len(turns)} 轮对话"})

        # ---- 阶段二：TTS ----
        _set_status(db, task, "running")
        pid = new_podcast_id()
        out_dir = Path(get_settings().podcasts_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / f"{pid}.mp3"
        _log_step(db, task_id, seq, "thought",
                  {"phase": "tts",
                   "thought": f"开始逐轮合成音频（{len(turns)} 轮，双主播音色）"})
        try:
            audio, interrupted = asyncio.run(synth_dialogue(turns, voice_a, voice_b,
                                                            should_stop=_cancelled))
        except Exception as e:  # noqa: BLE001
            audio, interrupted = b"", False
            logger.exception("TTS 合成失败：%s", task_id)
            _set_status(db, task, "failed", f"音频合成失败：{e}")
            audio_path.unlink(missing_ok=True)
            return
        if interrupted:
            audio_path.unlink(missing_ok=True)
            _set_status(db, task, "cancelled")
            return
        if not audio:
            audio_path.unlink(missing_ok=True)
            _set_status(db, task, "failed", "音频合成失败：输出为空")
            return
        audio_path.write_bytes(audio)

        # ---- 落库 ----
        try:
            db.add(
                Podcast(
                    id=pid,
                    title=title,
                    intent=intent,
                    style=style,
                    script_json=json.dumps(turns, ensure_ascii=False),
                    audio_path=str(audio_path),
                    duration_s=estimate_duration_s(len(audio)),
                    voice_a=voice_a,
                    voice_b=voice_b,
                    source_doc_ids_json=json.dumps(doc_ids),
                    task_id=task.id,
                    created_at=utc_now_iso(),
                )
            )
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            audio_path.unlink(missing_ok=True)
            logger.exception("播客落库失败：%s", task_id)
            _set_status(db, task, "failed", f"播客落库失败：{type(e).__name__}: {e}")
            return
        _log_step(db, task_id, seq, "observation",
                  {"tool": "tts", "podcast_id": pid, "audio_bytes": len(audio),
                   "duration_s": estimate_duration_s(len(audio))})
        _set_status(db, task, "done")
    finally:
        db.close()
