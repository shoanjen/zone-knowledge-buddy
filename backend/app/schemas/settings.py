from pydantic import BaseModel, Field


class ProviderIn(BaseModel):
    type: str = Field(pattern="^(cloud|local-ollama|local-lmstudio)$")
    name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=256)
    model: str = Field(min_length=1, max_length=128)
    api_key: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=256)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    api_key: str | None = None


class ProviderOut(BaseModel):
    id: int
    type: str
    name: str
    base_url: str
    model: str
    is_active: bool
    has_api_key: bool
    # 掩码提示（前 3 + 末 4），用于编辑框确认存的是哪把 Key；未配置为 null
    api_key_hint: str | None = None
