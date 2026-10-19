"""三类端点差异适配（规格 §5.2）：本模块是供应商差异的唯一分支点。"""

import re
from dataclasses import dataclass
from typing import Any

from app.core.errors import GatewayError
from app.models.llm import PROVIDER_TYPES, LLMProvider

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
LOCAL_PLACEHOLDER_KEYS = {"local-ollama": "ollama", "local-lmstudio": "lmstudio"}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def strip_think(text: str) -> str:
    return THINK_RE.sub("", text).strip()


@dataclass
class ProviderSnapshot:
    """网关持有的供应商快照（任务发起时定格，规格 §5.3）。"""

    provider_id: int | None
    ptype: str
    name: str
    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_row(cls, row: LLMProvider) -> "ProviderSnapshot":
        from app.core.security import decrypt_secret

        if row.type == "cloud":
            if not row.api_key_enc:
                raise GatewayError(
                    f"云端供应商 {row.name} 未配置 api_key", retryable=False
                )
            key = decrypt_secret(row.api_key_enc)
        else:
            key = LOCAL_PLACEHOLDER_KEYS.get(row.type, "local")
        return cls(
            provider_id=row.id,
            ptype=row.type,
            name=row.name,
            base_url=row.base_url.rstrip("/"),
            model=row.model,
            api_key=key,
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def chat_payload(
        self, messages: list[dict], params: dict[str, Any], *, json_schema: dict | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, **params}
        if json_schema is not None:
            if self.ptype == "local-ollama":
                payload["format"] = json_schema
            else:
                # cloud 与 local-lmstudio 走 OpenAI 风格 response_format
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "out", "schema": json_schema, "strict": False},
                }
        return payload

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    @property
    def embed_url(self) -> str:
        return f"{self.base_url}/embeddings"

    @property
    def models_url(self) -> str:
        return f"{self.base_url}/models"


def validate_provider_type(ptype: str) -> str:
    if ptype not in PROVIDER_TYPES:
        raise GatewayError(f"未知供应商类型：{ptype}（可选 {PROVIDER_TYPES}）", retryable=False)
    return ptype


def classify_http_error(status: int) -> bool:
    """返回该 HTTP 状态是否可重试（规格 §5.3）。"""
    return status in RETRYABLE_STATUS
