from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_report_id, utc_now_iso


class Report(Base):
    __tablename__ = "report"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_report_id)
    title: Mapped[str] = mapped_column(String(256), default="")
    intent: Mapped[str] = mapped_column(Text, default="")
    html_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_doc_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)
