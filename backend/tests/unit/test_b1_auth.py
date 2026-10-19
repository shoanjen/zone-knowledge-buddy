"""B1 验收：health + 认证三分支（规格 §4 验收）。"""


def test_health_no_auth(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_login_and_me(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"username": "admin"}


def test_login_wrong_password_unified_message(client, auth_headers):
    # 用户已存在（auth_headers 造过），密码错误 → 401 且文案统一
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"
    assert resp.json()["message"] == "用户名或密码错误"


def test_login_unknown_user_same_message(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "用户名或密码错误"


def test_business_route_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


def test_tampered_token(client):
    import jwt

    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "wrong-secret", algorithm="HS256")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"
