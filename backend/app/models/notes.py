from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_note_id, utc_now_iso


class Note(Base):
    __tablename__ = "note"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_note_id)
    title: Mapped[str] = mapped_column(String(256), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")  # 对《03》§3 的补充
    source_doc_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)


class NoteCitation(Base):
    __tablename__ = "note_citation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(ForeignKey("note.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_id: Mapped[str] = mapped_column(String(40), index=True)
    block_id: Mapped[str] = mapped_column(String(16))
    broken: Mapped[bool] = mapped_column(Boolean, default=False)
