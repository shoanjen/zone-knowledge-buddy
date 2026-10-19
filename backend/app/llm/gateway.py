"""LLMGateway 实现（规格 §5.1）。

- chat / chat_json / healthcheck 走 active provider 快照
- embed 为固定通道（EMBEDDING_* 配置），与 active provider 无关
- 全部调用经 accounting 记账；结构化输出 3 次尝试后抛 GatewayJSONError
"""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from jsonschema import Draft7Validator

from app.core.config import get_settings
from app.core.errors import GatewayError, GatewayJSONError
from app.llm.accounting import log_call
from app.llm.providers import ProviderSnapshot, classify_http_error, strip_think

STREAM_FIRST_BYTE_TIMEOUT_S = 30
RETRY_DELAYS = [1, 3]
CHAT_JSON_MAX_ATTEMPTS = 3

AppErrorLike = (GatewayError, GatewayJSONError)

_DEFAULT_TEMPERATURES: dict[str, float] = {"extract": 0.2, "chat": 0.3, "report": 0.4}
_TASK_BUCKETS = {"planner": "extract", "reflect": "extract", "tool": "extract", "embed": "extract"}


def default_temperature(task_type: str) -> float:
    bucket = _TASK_BUCKETS.get(task_type, task_type)
    return _DEFAULT_TEMPERATURES.get(bucket, 0.2)


@dataclass
class GenerationParams:
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: int = 120
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved(self, task_type: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "temperature": self.temperature
            if self.temperature is not None
            else default_temperature(task_type)
        }
        if self.max_tokens is not None:
            out["max_tokens"] = self.max_tokens
        out.update(self.extra)
        return out


class _ThinkStreamFilter:
    """流式 <think> 段过滤：跨 delta 缓冲，见到 <think> 开始丢弃直到 </think>。"""

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, delta: str) -> str:
        self._buf += delta
        out = []
        while True:
            if self._in_think:
                end = self._buf.find("</think>")
                if end == -1:
                    self._buf = ""
                    return "".join(out)
                self._buf = self._buf[end + len("</think>") :]
                self._in_think = False
                continue
            start = self._buf.find("<think>")
            if start == -1:
                # 保留可能是不完整前缀的尾部
                keep = self._buf
                if "<" in self._buf:
                    idx = self._buf.rfind("<")
                    if idx > 0 and len(self._buf) - idx < len("<think>"):
                        keep, self._buf = self._buf[:idx], self._buf[idx:]
                else:
                    self._buf = ""
                out.append(keep)
                return "".join(out)
            out.append(self._buf[:start])
            self._buf = self._buf[start + len("<think>") :]
            self._in_think = True

    def flush(self) -> str:
        """流结束时返回残余缓冲（不含未闭合的 think 段）。"""
        rest = "" if self._in_think else self._buf
        self._buf = ""
        return rest


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_json_content(content: str) -> Any:
    text = strip_think(content).strip()
    if text.startswith("```"):
        text = _CODE_FENCE_RE.sub("", text).strip()
    return json.loads(text)


class LLMGateway:
    def __init__(self, provider: ProviderSnapshot):
        self.p = provider

    # ---------- 基础请求 ----------

    async def _post(
        self, url: str, payload: dict[str, Any], *, timeout_s: int
    ) -> dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(1 + len(RETRY_DELAYS)):
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    resp = await client.post(url, json=payload, headers=self.p.headers)
                if resp.status_code >= 400:
                    err = GatewayError(
                        f"LLM 端点 HTTP {resp.status_code}: {resp.text[:200]}",
                        retryable=classify_http_error(resp.status_code),
                    )
                    if not err.retryable or attempt == len(RETRY_DELAYS):
                        raise err
                    last_err = err
                else:
                    return resp.json()
            except httpx.HTTPError as e:
                last_err = e
                if attempt == len(RETRY_DELAYS):
                    raise GatewayError(f"LLM 端点不可达：{e}", retryable=True) from e
            await asyncio.sleep(RETRY_DELAYS[attempt])
        raise GatewayError(f"LLM 调用重试耗尽：{last_err}", retryable=True)

    # ---------- chat ----------

    async def chat(
        self,
        messages: list[dict],
        *,
        task_type: str,
        params: GenerationParams | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        params = params or GenerationParams()
        if stream:
            return self._chat_stream(messages, task_type, params)
        return await self._chat_once(messages, task_type, params)

    async def _chat_once(
        self, messages: list[dict], task_type: str, params: GenerationParams
    ) -> str:
        started = time.monotonic()
        payload = self.p.chat_payload(messages, params.resolved(task_type), json_schema=None)
        ok, err_msg = False, None
        try:
            data = await self._post(self.p.chat_url, payload, timeout_s=params.timeout_s)
            content = strip_think(data["choices"][0]["message"]["content"] or "")
            ok = True
            return content
        except AppErrorLike as e:
            err_msg = str(e)
            raise
        finally:
            usage = locals().get("data", {}).get("usage") or {}
            log_call(
                provider_id=self.p.provider_id,
                model=self.p.model,
                task_type=task_type,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=ok,
                error=err_msg,
            )

    async def _chat_stream(
        self, messages: list[dict], task_type: str, params: GenerationParams
    ) -> AsyncIterator[str]:
        started = time.monotonic()
        payload = self.p.chat_payload(
            messages, {**params.resolved(task_type), "stream": True}, json_schema=None
        )
        tf = _ThinkStreamFilter()
        usage: dict[str, Any] = {}
        ok, err_msg = False, None
        try:
            async with httpx.AsyncClient(timeout=params.timeout_s) as client:
                async with client.stream(
                    "POST", self.p.chat_url, json=payload, headers=self.p.headers
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode(errors="replace")
                        raise GatewayError(
                            f"LLM 流式 HTTP {resp.status_code}: {body[:200]}",
                            retryable=classify_http_error(resp.status_code),
                        )
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line.removeprefix("data:").strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        if not chunk.get("choices"):
                            continue
                        delta = chunk["choices"][0].get("delta", {}).get("content")
                        if delta:
                            piece = tf.feed(delta)
                            if piece:
                                yield piece
            tail = tf.flush()
            if tail:
                yield tail
            ok = True
        except AppErrorLike as e:
            err_msg = str(e)
            raise
        finally:
            log_call(
                provider_id=self.p.provider_id,
                model=self.p.model,
                task_type=task_type,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=ok,
                error=err_msg,
            )

    # ---------- chat_json ----------

    async def chat_json(
        self,
        messages: list[dict],
        schema: dict,
        *,
        task_type: str,
        params: GenerationParams | None = None,
    ) -> dict:
        params = params or GenerationParams()
        convo = list(messages)
        last_err = ""
        for _ in range(CHAT_JSON_MAX_ATTEMPTS):
            started = time.monotonic()
            payload = self.p.chat_payload(convo, params.resolved(task_type), json_schema=schema)
            try:
                data = await self._post(self.p.chat_url, payload, timeout_s=params.timeout_s)
            except GatewayError:
                raise
            content = strip_think(data["choices"][0]["message"]["content"] or "")
            usage = data.get("usage") or {}
            try:
                result = _parse_json_content(content)
                Draft7Validator(schema).validate(result)
                log_call(
                    provider_id=self.p.provider_id,
                    model=self.p.model,
                    task_type=task_type,
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    ok=True,
                )
                return result
            except Exception as e:  # noqa: BLE001 — JSON/校验失败进入重试
                last_err = f"{type(e).__name__}: {e}"
                log_call(
                    provider_id=self.p.provider_id,
                    model=self.p.model,
                    task_type=task_type,
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    ok=False,
                    error=last_err,
                )
                convo = convo + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": f"输出不符合 JSON Schema（{last_err}）。"
                        f"请严格输出符合以下 Schema 的 JSON，不要输出其他内容：\n{json.dumps(schema, ensure_ascii=False)}",
                    },
                ]
        raise GatewayJSONError(f"结构化输出 {CHAT_JSON_MAX_ATTEMPTS} 次尝试均失败：{last_err}")

    # ---------- 健康检查 ----------

    async def healthcheck(self) -> dict[str, Any]:
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self.p.models_url, headers=self.p.headers)
            latency = int((time.monotonic() - started) * 1000)
            if resp.status_code >= 400:
                return {"ok": False, "latency_ms": latency, "models": [],
                        "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            return {"ok": True, "latency_ms": latency, "models": models}
        except httpx.HTTPError as e:
            return {
                "ok": False,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "models": [],
                "error": str(e)[:200],
            }


# ---------- embed 固定通道（规格 §5.1：与 active provider 无关）----------

EMBED_BATCH_SIZE = 16
EMBED_RETRY_DELAYS = [1, 3]


def _embed_endpoint() -> tuple[str, str]:
    """优先 settings.embedding（可能已被锁定），否则 env 默认。"""
    import json as _json

    from app.core.db import SessionLocal
    from app.models.settings import Setting

    s = get_settings()
    base_url, model = s.embedding_base_url, s.embedding_model
    try:
        db = SessionLocal()
        try:
            row = db.get(Setting, "embedding")
            if row:
                cfg = _json.loads(row.value_json)
                base_url = cfg.get("base_url", base_url)
                model = cfg.get("model", model)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — 无库时回落 env
        pass
    return base_url.rstrip("/"), model


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    base_url, model = _embed_endpoint()
    url = f"{base_url}/embeddings"
    headers = {"Content-Type": "application/json"}
    results: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        payload = {"model": model, "input": batch}
        started = time.monotonic()
        ok, err_msg = False, None
        try:
            for attempt in range(1 + len(EMBED_RETRY_DELAYS)):
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code < 400:
                        data = resp.json()
                        results.extend([item["embedding"] for item in data["data"]])
                        ok = True
                        break
                    if not classify_http_error(resp.status_code):
                        raise GatewayError(
                            f"embedding 端点 HTTP {resp.status_code}", retryable=False
                        )
                except httpx.HTTPError as e:
                    if attempt == len(EMBED_RETRY_DELAYS):
                        raise GatewayError(f"embedding 端点不可达：{e}") from e
                await asyncio.sleep(EMBED_RETRY_DELAYS[min(attempt, 1)])
            if not ok and err_msg is None:
                raise GatewayError("embedding 批次失败")
        except GatewayError as e:
            err_msg = str(e)
            raise
        finally:
            log_call(
                provider_id=None,
                model=model,
                task_type="embed",
                prompt_tokens=sum(len(t) for t in batch) // 2,
                completion_tokens=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=ok,
                error=err_msg,
            )
    return results
