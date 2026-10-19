from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_task_id, utc_now_iso

TASK_STATUS = ("pending", "planning", "running", "reflecting", "paused", "done", "failed", "cancelled")
TASK_TYPES = ("note.generate", "report.generate")
STEP_TYPES = ("thought", "tool", "observation", "reflection")


class AgentTask(Base):
    __tablename__ = "agent_task"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_task_id)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    draft_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # paused 时的草稿产出
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)
    finished_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AgentTaskStep(Base):
    __tablename__ = "agent_task_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("agent_task.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(16))  # thought / tool / observation / reflection
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now_iso)
