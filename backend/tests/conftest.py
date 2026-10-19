"""测试设施（规格 §15.1）：tmp SQLite + tmp 数据目录 + mock 网关注入点。

conftest 在导入任何 app 模块之前设置环境变量，保证 get_settings 读到测试配置。
"""

import os
import tempfile
from pathlib import Path

# 必须在 import app 之前设置
_TEST_DIR = Path(tempfile.mkdtemp(prefix="kb-test-"))
os.environ["KB_SECRET_KEY"] = "z0eK3gQ7VqM8jJ1wF5xK9pT3sN7bL2dR4uH6oP8aS9c="
os.environ["KB_DATA_DIR"] = str(_TEST_DIR / "data")
os.environ["KB_ENV"] = "test"
os.environ["EMBEDDING_BASE_URL"] = "http://localhost:11434/v1"
os.environ["EMBEDDING_MODEL"] = "bge-m3"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: F401,E402
from app.core.db import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA user_version = 1"))
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        # 不用 with（不触发 lifespan）：测试自带独立库，无需真实初始化
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client, db_engine):
    """在测试独立库造默认用户并真实走一遍登录。"""
    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        if s.scalar(select(User).where(User.username == "admin")) is None:
            s.add(User(username="admin", password_hash=hash_password("admin123")))
            s.commit()
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}
