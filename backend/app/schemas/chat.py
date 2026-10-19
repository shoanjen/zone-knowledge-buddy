from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    top_k: int = 5
