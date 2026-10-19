from pydantic import BaseModel, Field


class NoteGenerateIn(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    intent: str = Field(min_length=2, max_length=2000)
    confirm_required: bool = False


class NoteUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    content_md: str | None = None
    tags: list[str] | None = None
