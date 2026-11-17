"""TTS 合成（edge-tts）：逐轮合成双主播语音，按轮拼接为单个 MP3。

edge-tts 输出为 CBR 48kbps / 24kHz mono MP3（audio-24khz-48kbitrate-mono-mp3），
同参数分片直接字节拼接后播放器可无缝顺序解码，无需 ffmpeg 转封装；
时长按 48kbps 码率从字节数估算（误差 <5%，仅用于展示）。
"""

import asyncio
import io
import logging

import edge_tts

logger = logging.getLogger("kb.podcast")

# 可选音色（前端主播选择器的数据来源，经 /api/podcasts/voices 下发）
VOICES: dict[str, str] = {
    "zh-CN-XiaoxiaoNeural": "晓晓 · 女声 · 温暖",
    "zh-CN-XiaoyiNeural": "晓伊 · 女声 · 活泼",
    "zh-CN-YunjianNeural": "云健 · 男声 · 沉稳",
    "zh-CN-YunxiNeural": "云希 · 男声 · 阳光",
    "zh-CN-YunxiaNeural": "云夏 · 男声 · 少年",
}

STYLES = ("轻松闲聊", "深度讲解", "快讯速览")

DEFAULT_VOICE_A = "zh-CN-XiaoxiaoNeural"
DEFAULT_VOICE_B = "zh-CN-YunxiNeural"

MP3_BYTES_PER_SECOND = 6000  # 48kbps CBR → 6000 字节/秒
SYNTH_RETRY_DELAYS = [1, 3]


def estimate_duration_s(total_bytes: int) -> float:
    return round(total_bytes / MP3_BYTES_PER_SECOND, 1)


async def synthesize(text: str, voice: str) -> bytes:
    """单轮合成；网络抖动按网关同款退避重试。"""

    last_err: Exception | None = None
    for attempt in range(1 + len(SYNTH_RETRY_DELAYS)):
        try:
            buf = io.BytesIO()
            comm = edge_tts.Communicate(text, voice)
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            data = buf.getvalue()
            if data:
                return data
            last_err = RuntimeError("TTS 返回空音频")
        except Exception as e:  # noqa: BLE001 — edge-tts 异常类型不稳定，统一按可重试处理
            last_err = e
        logger.warning("TTS 合成失败（第 %s 次）：%s", attempt + 1, last_err)
        await asyncio.sleep(SYNTH_RETRY_DELAYS[min(attempt, len(SYNTH_RETRY_DELAYS) - 1)])
    raise RuntimeError(f"TTS 合成失败（voice={voice}）：{last_err}")


async def synth_dialogue(turns: list[dict], voice_a: str, voice_b: str, should_stop=None):
    """逐轮合成并拼接。should_stop 为空返回（部分音频, 是否被中断）。"""

    voices = {"A": voice_a, "B": voice_b}
    parts: list[bytes] = []
    for turn in turns:
        if should_stop is not None and should_stop():
            return b"".join(parts), True
        data = await synthesize(turn["text"], voices.get(turn["speaker"], voice_a))
        parts.append(data)
    return b"".join(parts), False
