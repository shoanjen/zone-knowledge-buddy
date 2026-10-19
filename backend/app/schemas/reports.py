from pydantic import BaseModel, Field


class ReportGenerateIn(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    intent: str = Field(min_length=2, max_length=2000)
    title: str | None = Field(default=None, max_length=256)
