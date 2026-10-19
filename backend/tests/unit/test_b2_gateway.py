"""B2 验收：网关 chat/chat_json/重试/think 剥离/健康检查（规格 §5）。"""

import json

import pytest
import respx
from httpx import Response

import app.llm.gateway as gw_mod
from app.core.errors import GatewayError, GatewayJSONError
from app.llm.gateway import GenerationParams, LLMGateway
from app.llm.providers import ProviderSnapshot

CLOUD = ProviderSnapshot(
    provider_id=1,
    ptype="cloud",
    name="cloud-glm",
    base_url="https://api.example.com/v1",
    model="glm-4.6",
    api_key="sk-test",
)
OLLAMA = ProviderSnapshot(
    provider_id=2,
    ptype="local-ollama",
    name="local-ollama",
    base_url="http://localhost:11434/v1",
    model="qwen3:4b",
    api_key="ollama",
)


def _chat_response(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.fixture()
def calls(monkeypatch):
    recorded: list[dict] = []

    def fake_log(**kw):
        recorded.append(kw)

    monkeypatch.setattr(gw_mod, "log_call", fake_log)
    return recorded


async def test_chat_ok_and_accounting(calls):
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=Response(200, json=_chat_response("你好"))
        )
        out = await LLMGateway(CLOUD).chat(
            [{"role": "user", "content": "hi"}], task_type="chat"
        )
    assert out == "你好"
    assert len(calls) == 1
    assert calls[0]["ok"] is True
    assert calls[0]["prompt_tokens"] == 10
    assert calls[0]["task_type"] == "chat"


async def test_chat_strips_think(calls):
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=Response(200, json=_chat_response("<think>推理...</think>结论"))
        )
        out = await LLMGateway(CLOUD).chat([{"role": "user", "content": "q"}], task_type="chat")
    assert out == "结论"


async def test_chat_payload_differs_by_provider():
    captured: dict[str, dict] = {}

    def _capture(request):
        captured[request.url.host] = json.loads(request.content)
        return Response(200, json=_chat_response('{"a": 1}'))

    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(side_effect=_capture)
        respx.post("http://localhost:11434/v1/chat/completions").mock(side_effect=_capture)
        schema = {"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]}
        await LLMGateway(CLOUD).chat_json(
            [{"role": "user", "content": "j"}], schema, task_type="extract"
        )
        await LLMGateway(OLLAMA).chat_json(
            [{"role": "user", "content": "j"}], schema, task_type="extract"
        )

    assert captured["api.example.com"]["response_format"]["type"] == "json_schema"
    assert captured["localhost"]["format"] == schema


async def test_chat_json_success_after_retry(calls):
    schema = {"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]}
    with respx.mock:
        route = respx.post("https://api.example.com/v1/chat/completions")
        route.side_effect = [
            Response(200, json=_chat_response("not json")),
            Response(200, json=_chat_response('{"a": 1}')),
        ]
        out = await LLMGateway(CLOUD).chat_json(
            [{"role": "user", "content": "j"}], schema, task_type="extract"
        )
    assert out == {"a": 1}
    statuses = [c["ok"] for c in calls]
    assert statuses == [False, True]


async def test_chat_json_exhausts_attempts(calls):
    schema = {"type": "object", "required": ["a"]}
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=Response(200, json=_chat_response("垃圾输出"))
        )
        with pytest.raises(GatewayJSONError):
            await LLMGateway(CLOUD).chat_json(
                [{"role": "user", "content": "j"}], schema, task_type="extract"
            )
    assert len(calls) == 3  # 3 次尝试全失败


async def test_retry_on_500_then_ok(calls):
    with respx.mock:
        route = respx.post("https://api.example.com/v1/chat/completions")
        route.side_effect = [
            Response(500, text="boom"),
            Response(200, json=_chat_response("ok")),
        ]
        out = await LLMGateway(CLOUD).chat([{"role": "user", "content": "q"}], task_type="chat")
    assert out == "ok"


async def test_no_retry_on_401():
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=Response(401, text="bad key")
        )
        with pytest.raises(GatewayError) as ei:
            await LLMGateway(CLOUD).chat([{"role": "user", "content": "q"}], task_type="chat")
        assert ei.value.retryable is False


async def test_healthcheck():
    with respx.mock:
        respx.get("https://api.example.com/v1/models").mock(
            return_value=Response(200, json={"data": [{"id": "glm-4.6"}]})
        )
        out = await LLMGateway(CLOUD).healthcheck()
    assert out["ok"] is True and out["models"] == ["glm-4.6"]

    with respx.mock:
        respx.get("http://localhost:11434/v1/models").mock(return_value=Response(503))
        out = await LLMGateway(OLLAMA).healthcheck()
    assert out["ok"] is False


async def test_default_temperature_resolution():
    p = GenerationParams()
    assert p.resolved("chat")["temperature"] == 0.3
    assert p.resolved("report")["temperature"] == 0.4
    assert p.resolved("planner")["temperature"] == 0.2  # planner 归 extract 桶
    p2 = GenerationParams(temperature=0.9)
    assert p2.resolved("chat")["temperature"] == 0.9
