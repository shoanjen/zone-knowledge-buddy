"""B2 验收：供应商管理 API（规格 §12.2）。"""

import respx
from httpx import Response

from app.models.llm import LLMProvider


def _mk(db_session, **kw) -> LLMProvider:
    row = LLMProvider(
        type=kw.get("type", "local-ollama"),
        name=kw.get("name", "p"),
        base_url=kw.get("base_url", "http://localhost:11434/v1"),
        model=kw.get("model", "qwen3:4b"),
        api_key_enc=kw.get("api_key_enc"),
        is_active=kw.get("is_active", False),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_create_cloud_requires_key(client, auth_headers):
    resp = client.post(
        "/api/settings/providers",
        json={"type": "cloud", "name": "c1", "base_url": "https://x/v1", "model": "m"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "PROVIDER_CONFIG"


def test_create_and_never_leak_key(client, auth_headers):
    resp = client.post(
        "/api/settings/providers",
        json={
            "type": "cloud",
            "name": "c1",
            "base_url": "https://x/v1",
            "model": "m",
            "api_key": "sk-secret",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_api_key"] is True
    assert "sk-secret" not in resp.text


def test_activate_and_flag(client, auth_headers, db_session):
    a = _mk(db_session, name="a")
    b = _mk(db_session, name="b")
    resp = client.post(f"/api/settings/providers/{a.id}/activate", headers=auth_headers)
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.get(LLMProvider, a.id).is_active is True
    assert db_session.get(LLMProvider, b.id).is_active is False
    # settings 表记录
    from app.models.settings import Setting

    assert db_session.get(Setting, "active_provider_id").value_json == str(a.id)


def test_delete_active_conflict(client, auth_headers, db_session):
    a = _mk(db_session, name="a")
    client.post(f"/api/settings/providers/{a.id}/activate", headers=auth_headers)
    resp = client.delete(f"/api/settings/providers/{a.id}", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "PROVIDER_ACTIVE"


def test_provider_endpoint_test(client, auth_headers, db_session):
    a = _mk(db_session, name="a", base_url="http://localhost:11434/v1")
    with respx.mock:
        respx.get("http://localhost:11434/v1/models").mock(
            return_value=Response(200, json={"data": [{"id": "qwen3:4b"}]})
        )
        resp = client.post(f"/api/settings/providers/{a.id}/test", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and "qwen3:4b" in body["models"]

    # 不可达也返回 200 + ok=false（测试结果不是错误）
    with respx.mock:
        respx.get("http://localhost:11434/v1/models").mock(return_value=Response(503))
        resp = client.post(f"/api/settings/providers/{a.id}/test", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_requires_auth(client):
    resp = client.get("/api/settings/providers")
    assert resp.status_code == 401
