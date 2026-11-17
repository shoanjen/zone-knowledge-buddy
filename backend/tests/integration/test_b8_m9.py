"""B8/M9 收口集成测试：settings GET/PUT + embedding 锁、数据导出、任务面板（规格 §12）。"""

import io
import json
import zipfile

from app.core.config import get_settings
from app.models.notes import Note
from app.models.settings import Setting
from app.models.tasks import AgentTask, AgentTaskStep


def _seed_setting(db_session, key: str, value: dict) -> None:
    row = db_session.get(Setting, key)
    payload = json.dumps(value, ensure_ascii=False)
    if row is None:
        db_session.add(Setting(key=key, value_json=payload))
    else:
        row.value_json = payload
    db_session.commit()


def _mk_task(db_session, **kw) -> AgentTask:
    t = AgentTask(
        id=kw.get("id", "t_test01"),
        type=kw.get("type", "note.generate"),
        status=kw.get("status", "pending"),
        provider_id=kw.get("provider_id"),
        input_json=kw.get("input_json", json.dumps({"doc_ids": [], "intent": "测试"})),
        draft_json=kw.get("draft_json"),
        error=kw.get("error"),
    )
    db_session.add(t)
    db_session.commit()
    return t


# ---------- §12.3 设置与 embedding 锁 ----------


def test_settings_roundtrip_and_embedding_lock(client, auth_headers, db_session):
    _seed_setting(
        db_session,
        "embedding",
        {"provider_type": "local-ollama", "base_url": "http://localhost:11434/v1",
         "model": "bge-m3", "locked_at": None},
    )

    r = client.get("/api/settings", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_provider_id"] is None
    assert body["generation_params"] == {"extract": 0.2, "chat": 0.3, "report": 0.4}
    assert body["embedding"]["model"] == "bge-m3"
    assert body["embedding_locked"] is False

    # 未锁定时允许修改 embedding 与 generation_params
    r = client.put(
        "/api/settings",
        headers=auth_headers,
        json={
            "generation_params": {"extract": 0.1, "chat": 0.2, "report": 0.5},
            "embedding": {"base_url": "http://localhost:8000/v1", "model": "bge-m3"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generation_params"]["extract"] == 0.1
    assert body["embedding"]["base_url"] == "http://localhost:8000/v1"
    assert body["embedding_locked"] is False

    # 锁定后 embedding 拒改（409 EMBEDDING_LOCKED），generation_params 不受影响
    _seed_setting(
        db_session,
        "embedding",
        {"provider_type": "local-ollama", "base_url": "http://localhost:8000/v1",
         "model": "bge-m3", "locked_at": "2026-10-20T00:00:00Z"},
    )
    r = client.put(
        "/api/settings", headers=auth_headers, json={"embedding": {"model": "x"}}
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "EMBEDDING_LOCKED"

    r = client.put(
        "/api/settings",
        headers=auth_headers,
        json={"generation_params": {"extract": 0.3, "chat": 0.3, "report": 0.4}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["embedding_locked"] is True

    # 锁定后同时提交参数与 embedding：必须整体 409，generation_params 不得部分生效
    r = client.put(
        "/api/settings",
        headers=auth_headers,
        json={
            "generation_params": {"extract": 0.9, "chat": 0.9, "report": 0.9},
            "embedding": {"model": "other"},
        },
    )
    assert r.status_code == 409
    body = client.get("/api/settings", headers=auth_headers).json()
    assert body["generation_params"]["extract"] == 0.3


# ---------- §12.4 数据导出 ----------


def test_data_export_zip_entries(client, auth_headers, db_session):
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    (s.storage_dir / "d_test").mkdir(exist_ok=True)
    (s.storage_dir / "d_test" / "original.pdf").write_bytes(b"%PDF-test")

    r = client.get("/api/data/export", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "zip" in r.headers["content-type"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "kb.sqlite3" in names
    assert "storage/d_test/original.pdf" in names


# ---------- §12.1 任务面板 ----------


def test_tasks_list_detail_and_cancel(client, auth_headers, db_session):
    r = client.get("/api/tasks", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"total": 0, "items": []}

    t = _mk_task(db_session, id="t_list01", status="pending")
    db_session.add(
        AgentTaskStep(task_id=t.id, seq=1, step_type="thought",
                      content_json=json.dumps({"text": "先检索"}))
    )
    db_session.commit()

    r = client.get("/api/tasks", headers=auth_headers)
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "t_list01"
    assert body["items"][0]["provider_name"] is None

    r = client.get("/api/tasks/t_list01", headers=auth_headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["input"] == {"doc_ids": [], "intent": "测试"}
    assert detail["steps"][0]["step_type"] == "thought"
    assert detail["steps"][0]["content"] == {"text": "先检索"}

    # pending 可取消；取消后再次取消 → 409
    r = client.post("/api/tasks/t_list01/cancel", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    r = client.post("/api/tasks/t_list01/cancel", headers=auth_headers)
    assert r.status_code == 409 and r.json()["code"] == "TASK_STATE"

    # 非 paused 不可 confirm
    r = client.post(
        "/api/tasks/t_list01/confirm", headers=auth_headers, json={"approve": True}
    )
    assert r.status_code == 409 and r.json()["code"] == "TASK_STATE"

    # 不存在 → 404
    r = client.get("/api/tasks/t_nope", headers=auth_headers)
    assert r.status_code == 404


def test_task_confirm_reject(client, auth_headers, db_session):
    _mk_task(db_session, id="t_rej01", status="paused")
    r = client.post(
        "/api/tasks/t_rej01/confirm", headers=auth_headers, json={"approve": False}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed"
    t = db_session.get(AgentTask, "t_rej01")
    assert t.error == "user_rejected"


def test_task_confirm_approve_creates_note(client, auth_headers, db_session):
    _mk_task(
        db_session,
        id="t_ok01",
        status="paused",
        draft_json=json.dumps(
            {"content_md": "# 对比笔记\n\n要点一 [d_missing:b1]", "charts": []},
            ensure_ascii=False,
        ),
    )
    # paused 详情附带 draft（B8 前端确认页需要）
    r = client.get("/api/tasks/t_ok01", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["draft"]["content_md"].startswith("# 对比笔记")

    r = client.post(
        "/api/tasks/t_ok01/confirm", headers=auth_headers, json={"approve": True}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"

    note = db_session.query(Note).filter(Note.task_id == "t_ok01").one()
    assert note.title == "对比笔记"
    # 引用指向不存在块 → broken 标记（规格 §9.3）
    from app.models.notes import NoteCitation

    rows = (
        db_session.query(NoteCitation).filter(NoteCitation.note_id == note.id).all()
    )
    assert len(rows) == 1
    assert rows[0].doc_id == "d_missing"
    assert rows[0].broken is True
