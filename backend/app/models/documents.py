from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_chunk_id, new_doc_id, utc_now_iso

DOC_STATUS = ("pending", "parsing", "ready", "failed")
SOURCE_TYPES = ("pdf", "word", "md", "excel", "web")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_doc_id)
    source_type: Mapped[str] = mapped_column(String(16))
    origin: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    parse_quality: Mapped[str | None] = mapped_column(String(8), nullable=True)  # high / low
    low_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)


class Block(Base):
    __tablename__ = "block"
    __table_args__ = (UniqueConstraint("doc_id", "block_id", name="uq_block_doc_block"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    block_id: Mapped[str] = mapped_column(String(16))  # b1, b2, ...
    type: Mapped[str] = mapped_column(String(16))  # heading / paragraph / table / image
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(String(256), nullable=True)
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 表格 [[...]]
    ref: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 图片相对路径
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_chunk_id)
    doc_id: Mapped[str] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    block_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    text: Mapped[str] = mapped_column(Text)
    vector_id: Mapped[str] = mapped_column(String(40), default="")
