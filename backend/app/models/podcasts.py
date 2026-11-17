from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_podcast_id, utc_now_iso


class Podcast(Base):
    __tablename__ = "podcast"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_podcast_id)
    title: Mapped[str] = mapped_column(String(256), default="")
    intent: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(32), default="轻松闲聊")
    # [{"speaker": "A", "text": "..."}]
    script_json: Mapped[str] = mapped_column(Text, default="[]")
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(nullable=True)  # 由码率估算的时长
    voice_a: Mapped[str] = mapped_column(String(64), default="")
    voice_b: Mapped[str] = mapped_column(String(64), default="")
    source_doc_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)
