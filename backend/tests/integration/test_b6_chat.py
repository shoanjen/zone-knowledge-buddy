"""B6 验收：问答 SSE（规格 §10）。"""

import json

import pytest
from sqlalchemy.orm import sessionmaker


class FakeStreamGateway:
    def __init__(self, deltas: list[str], ptype="cloud", name="GLM"):
        self.deltas = deltas
        self.p = type("P", (), {"ptype": ptype, "name": name, "model": "glm-4.6"})()

    async def chat(self, messages, *, task_type, params=None, stream=False):
        assert stream is True

        async def _gen():
            for d in self.deltas:
                yield d

        return _gen()


@pytest.fixture()
def chat_env(client, db_engine, auth_headers, monkeypatch):
    from app.models.documents import Block, Document
    from app.models.llm import LLMProvider
    from app.models.settings import Setting

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    s = TestSession()
    doc = Document(id="d_CHAT1", source_type="md", origin="x.md", title="问答文档",
                   status="ready", block_count=1, chunk_count=1)
    s.add(doc)
    s.add(Block(doc_id="d_CHAT1", seq=1, block_id="b1", type="paragraph", text="成本下降的论述。"))
    provider = LLMProvider(type="cloud", name="cloud-glm", base_url="https://x/v1",
                           model="glm-4.6", api_key_enc="enc")
    s.add(provider)
    s.flush()
    s.add(Setting(key="active_provider_id", value_json=str(provider.id)))
    s.commit()
    s.close()

    async def fake_search(q, *, top_k=5, doc_ids=None):
        return [{"chunk_id": "c1", "doc_id": "d_CHAT1", "block_ids": ["b1"],
                 "text": "成本下降的论述。", "score": 0.9, "origin": "x.md", "title": "问答文档"}]

    import app.agent.context as agent_context
    import app.rag.service as rag_service

    monkeypatch.setattr(rag_service, "search", fake_search)
    return {"patch_gateway": lambda gw: monkeypatch.setattr(agent_context, "build_gateway",
                                                            lambda db, pid: gw)}


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.strip().splitlines()
        if not lines:
            continue
        event, data = None, {}
        for ln in lines:
            if ln.startswith("event:"):
                event = ln.split(":", 1)[1].strip()
            elif ln.startswith("data:"):
                data = json.loads(ln.split(":", 1)[1].strip())
        if event:
            events.append((event, data))
    return events


def test_chat_stream_with_citations(client, auth_headers, chat_env):
    gw = FakeStreamGateway(["根据资料，", "成本在下降 [d_CHAT1:b1]"])
    chat_env["patch_gateway"](gw)

    with client.stream(
        "POST", "/api/chat", json={"message": "成本趋势如何？"}, headers=auth_headers
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join(resp.iter_text())
    events = _parse_sse(raw)
    names = [e for e, _ in events]
    assert names[0] == "meta" and names[-1] == "done" and "citations" in names

    meta = dict(events)["meta"]
    assert meta["provider"]["model"] == "glm-4.6"
    assert meta["retrieved"][0]["doc_id"] == "d_CHAT1"

    tokens = "".join(d["delta"] for e, d in events if e == "token")
    assert "成本在下降" in tokens

    cits = dict(events)["citations"]["citations"]
    assert cits[0]["doc_id"] == "d_CHAT1" and cits[0]["block_id"] == "b1"

    # 会话留痕
    sessions = client.get("/api/chat/sessions", headers=auth_headers).json()["items"]
    assert len(sessions) == 1
    detail = client.get(f"/api/chat/sessions/{sessions[0]['id']}", headers=auth_headers).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["citations"][0]["block_id"] == "b1"


def test_chat_error_event(client, auth_headers, chat_env):
    from app.core.errors import GatewayError

    class ErrGW:
        p = type("P", (), {"ptype": "cloud", "name": "GLM", "model": "glm-4.6"})()

        async def chat(self, *a, **k):
            raise GatewayError("端点不可达")

    chat_env["patch_gateway"](ErrGW())
    with client.stream(
        "POST", "/api/chat", json={"message": "问个问题"}, headers=auth_headers
    ) as resp:
        raw = "".join(resp.iter_text())
    events = _parse_sse(raw)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "PROVIDER_UNREACHABLE"


def test_chat_refusal_style(client, auth_headers, chat_env):
    gw = FakeStreamGateway(["知识库中未找到依据。"])
    chat_env["patch_gateway"](gw)
    with client.stream(
        "POST", "/api/chat", json={"message": "无关问题"}, headers=auth_headers
    ) as resp:
        raw = "".join(resp.iter_text())
    events = _parse_sse(raw)
    tokens = "".join(d["delta"] for e, d in events if e == "token")
    assert tokens == "知识库中未找到依据。"
    # 拒答：citations 为空
    assert dict(events)["citations"]["citations"] == []
