"""B5 验收：Agent 全链 + 笔记（规格 §8/§9），FakeGateway 脚本化驱动。"""


import pytest
from sqlalchemy.orm import sessionmaker


class FakeGateway:
    def __init__(self, script: list[dict]):
        self.script = list(script)
        self.calls: list[str] = []

    async def chat_json(self, messages, schema, *, task_type, params=None):
        self.calls.append(task_type)
        assert self.script, "脚本耗尽：网关收到的调用比预期多"
        return self.script.pop(0)

    async def chat(self, messages, *, task_type, params=None, stream=False):
        self.calls.append(task_type)
        return "摘要文本"


@pytest.fixture()
def seeded(client, db_engine, auth_headers, monkeypatch):
    """造一篇 ready 文档（含块）+ 生效供应商，并把 orchestrator 接到测试库。"""
    from app.models.documents import Block, Document
    from app.models.llm import LLMProvider
    from app.models.settings import Setting

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    s = TestSession()
    doc = Document(
        id="d_TEST01", source_type="md", origin="a.md", title="测试文档",
        status="ready", parse_quality="high", block_count=2, chunk_count=1,
    )
    s.add(doc)
    s.add(Block(doc_id="d_TEST01", seq=1, block_id="b1", type="paragraph", text="成本下降的论述。"))
    s.add(Block(doc_id="d_TEST01", seq=2, block_id="b2", type="paragraph", text="风险上升的论述。"))
    provider = LLMProvider(type="local-ollama", name="p", base_url="http://x", model="qwen3:4b")
    s.add(provider)
    s.flush()
    s.add(Setting(key="active_provider_id", value_json=str(provider.id)))
    s.commit()
    s.close()

    import app.agent.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "SessionLocal", TestSession)
    import app.api.notes as notes_api

    monkeypatch.setattr(notes_api, "submit", lambda fn, *a, **k: fn(*a, **k))
    return {"doc_id": "d_TEST01"}


def _patch_gateway(monkeypatch, gw: FakeGateway):
    import app.agent.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "build_gateway", lambda db, pid: gw)
    import app.rag.service as rag_service

    monkeypatch.setattr(
        rag_service,
        "search_sync",
        lambda q, **kw: [
            {"chunk_id": "c1", "doc_id": "d_TEST01", "block_ids": ["b1"],
             "text": "成本下降的论述。", "score": 0.92}
        ],
    )


HAPPY_SCRIPT = [
    {"steps": [{"no": 1, "description": "检索资料", "tool_hint": "kb.search"}]},
    {"type": "tool", "thought": "先检索", "tool": "kb.search", "args": {"query": "成本"}},
    {"type": "tool", "thought": "保存笔记", "tool": "note.write",
     "args": {"title": "草稿", "content_md": "# 草稿", "tags": ["t"]}},
    {"type": "final", "thought": "完成",
     "content": "# 成本笔记\n\n## 要点\n\n- 成本下降 [d_TEST01:b1]"},
    {"results": [{"claim_id": 0, "supported": True}]},
]


def test_note_generate_happy_path(client, auth_headers, seeded, monkeypatch):
    gw = FakeGateway(list(HAPPY_SCRIPT))
    _patch_gateway(monkeypatch, gw)

    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": [seeded["doc_id"]], "intent": "整理成本相关笔记"},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]

    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "done", detail
    step_types = [s["step_type"] for s in detail["steps"]]
    assert "tool" in step_types and "observation" in step_types and "reflection" in step_types

    notes = client.get("/api/notes", headers=auth_headers).json()
    assert notes["total"] == 1
    note = client.get(f"/api/notes/{notes['items'][0]['id']}", headers=auth_headers).json()
    assert "[d_TEST01:b1]" in note["content_md"]
    assert note["citations"] and note["citations"][0]["broken"] is False
    assert note["citations"][0]["block_text"] == "成本下降的论述。"


def test_reflection_drops_unsupported(client, auth_headers, seeded, monkeypatch):
    script = [
        {"steps": [{"no": 1, "description": "检索"}]},
        {"type": "final", "thought": "直接产出",
         "content": "# 笔记\n\n- 被支撑的结论 [d_TEST01:b1]\n- 未被支撑的结论 [d_TEST01:b2]"},
        {"results": [{"claim_id": 0, "supported": True}, {"claim_id": 1, "supported": False}]},
    ]
    gw = FakeGateway(script)
    _patch_gateway(monkeypatch, gw)
    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": [seeded["doc_id"]], "intent": "整理"},
        headers=auth_headers,
    )
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "done"

    notes = client.get("/api/notes", headers=auth_headers).json()
    note = client.get(f"/api/notes/{notes['items'][0]['id']}", headers=auth_headers).json()
    assert "未被支撑" not in note["content_md"]
    assert "被支撑" in note["content_md"]
    assert len(note["citations"]) == 1


def test_paused_confirm_flow(client, auth_headers, seeded, monkeypatch):
    # 不含 note.write：paused 期间不应产出任何笔记
    paused_script = [
        HAPPY_SCRIPT[0],
        HAPPY_SCRIPT[1],
        HAPPY_SCRIPT[3],
        HAPPY_SCRIPT[4],
    ]
    gw = FakeGateway(list(paused_script))
    _patch_gateway(monkeypatch, gw)
    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": [seeded["doc_id"]], "intent": "整理", "confirm_required": True},
        headers=auth_headers,
    )
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "paused"
    assert client.get("/api/notes", headers=auth_headers).json()["total"] == 0

    # 人工修订后批准
    resp = client.post(
        f"/api/tasks/{task_id}/confirm",
        json={"approve": True, "content_md": "# 人工修订\n- 修订后的要点 [d_TEST01:b1]"},
        headers=auth_headers,
    )
    assert resp.json()["status"] == "done"
    notes = client.get("/api/notes", headers=auth_headers).json()
    assert notes["total"] == 1
    note = client.get(f"/api/notes/{notes['items'][0]['id']}", headers=auth_headers).json()
    assert "人工修订" in note["content_md"]

    # 拒绝分支
    gw2 = FakeGateway(list(paused_script))
    _patch_gateway(monkeypatch, gw2)
    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": [seeded["doc_id"]], "intent": "整理", "confirm_required": True},
        headers=auth_headers,
    )
    tid2 = resp.json()["task_id"]
    resp = client.post(f"/api/tasks/{tid2}/confirm", json={"approve": False}, headers=auth_headers)
    assert resp.json()["status"] == "failed"
    assert client.get(f"/api/tasks/{tid2}", headers=auth_headers).json()["error"] == "user_rejected"


def test_loop_detection(client, auth_headers, seeded, monkeypatch):
    same_call = {"type": "tool", "thought": "again", "tool": "kb.search",
                 "args": {"query": "成本"}}
    gw = FakeGateway([{"steps": [{"no": 1, "description": "x"}]}, same_call, same_call, same_call])
    _patch_gateway(monkeypatch, gw)
    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": [seeded["doc_id"]], "intent": "整理"},
        headers=auth_headers,
    )
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "failed"
    assert "loop_detected" in detail["error"]


def test_generate_validates_docs(client, auth_headers, seeded):
    resp = client.post(
        "/api/notes/generate",
        json={"doc_ids": ["d_MISSING"], "intent": "整理"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION"


def test_note_edit_rebuilds_citations(client, auth_headers, seeded, db_session):
    from app.agent.citations import rebuild_note_citations
    from app.models.notes import Note, NoteCitation

    note = Note(title="t", content_md="原内容 [d_TEST01:b1] 和坏引用 [d_GONE:b9]")
    db_session.add(note)
    db_session.commit()
    rebuild_note_citations(db_session, note)

    rows = db_session.query(NoteCitation).filter_by(note_id=note.id).all()
    by_block = {c.block_id: c for c in rows}
    assert by_block["b1"].broken is False
    assert by_block["b1"].claim_text.startswith("原内容")
    assert by_block["b9"].broken is True
