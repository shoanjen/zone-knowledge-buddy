from pydantic import BaseModel, Field

from app.podcast.tts import DEFAULT_VOICE_A, DEFAULT_VOICE_B, STYLES, VOICES


def _valid_voice(v: str) -> bool:
    return v in VOICES


class PodcastGenerateIn(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    intent: str = Field(min_length=2, max_length=2000)
    title: str | None = Field(default=None, max_length=256)
    style: str = Field(default=STYLES[0])
    voice_a: str = Field(default=DEFAULT_VOICE_A)
    voice_b: str = Field(default=DEFAULT_VOICE_B)
