"""app factory 与 lifespan（规格 §3.1）。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.ids import new_request_id
from app.core.migrations import run_migrations
from app.core.security import encrypt_secret, hash_password

logger = logging.getLogger("kb")

API_VERSION = "0.1.0"


def _init_seed() -> None:
    """初始化单用户、三条 provider seed、settings 默认值（规格 §5.4 / §12.3）。"""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import LLMProvider, Setting, User

    s = get_settings()
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)) is None:
            db.add(
                User(
                    username=s.kb_admin_username,
                    password_hash=hash_password(s.kb_admin_password),
                )
            )
            logger.warning("已初始化默认用户 %r（请尽快修改密码：见 README）", s.kb_admin_username)

        if db.scalar(select(LLMProvider).limit(1)) is None:
            db.add_all(
                [
                    LLMProvider(
                        type="cloud",
                        name="cloud-glm",
                        base_url=s.glm_base_url,
                        api_key_enc=encrypt_secret(s.glm_api_key) if s.glm_api_key else None,
                        model=s.glm_model,
                    ),
                    LLMProvider(type="local-ollama", name="local-ollama",
                                base_url="http://localhost:11434/v1", model="qwen3:4b"),
                    LLMProvider(type="local-lmstudio", name="local-lmstudio",
                                base_url="http://localhost:1234/v1", model="qwen3:4b"),
                ]
            )

        defaults = {
            "generation_params": {"extract": 0.2, "chat": 0.3, "report": 0.4},
            "embedding": {
                "provider_type": "local-ollama",
                "base_url": s.embedding_base_url,
                "model": s.embedding_model,
                "locked_at": None,
            },
        }
        for key, value in defaults.items():
            if db.get(Setting, key) is None:
                import json

                db.add(Setting(key=key, value_json=json.dumps(value, ensure_ascii=False)))
        db.commit()
    finally:
        db.close()


def _recover_orphans() -> None:
    """启动自愈：进程退出时仍停在中间态的文档/任务已无线程推进，统一置 failed。

    - 文档：pending/parsing → failed（可重试/可删）
    - 任务：pending/planning/running/reflecting → failed（线程已随进程消失）；
      paused 保留：草稿已生成，确认/拒绝不依赖 LLM，重启后仍可操作
    """
    from sqlalchemy import update

    from app.core.db import SessionLocal
    from app.models import AgentTask, Document

    db = SessionLocal()
    try:
        doc_result = db.execute(
            update(Document)
            .where(Document.status.in_(("pending", "parsing")))
            .values(status="failed", error="服务重启时解析中断，请重试")
        )
        task_result = db.execute(
            update(AgentTask)
            .where(AgentTask.status.in_(("pending", "planning", "running", "reflecting")))
            .values(status="failed", error="服务重启时任务中断，请重新发起")
        )
        db.commit()
        if doc_result.rowcount:
            logger.warning(
                "启动自愈：%s 个 pending/parsing 文档已置为 failed（可重试/可删除）", doc_result.rowcount
            )
        if task_result.rowcount:
            logger.warning("启动自愈：%s 个进行中任务已置为 failed（可重新发起）", task_result.rowcount)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.chroma_dir.mkdir(parents=True, exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    s.podcasts_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    _init_seed()
    _recover_orphans()
    logging.basicConfig(
        level=logging.DEBUG if s.is_dev else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="zone-knowledge-buddy", version=API_VERSION, lifespan=lifespan)

    if s.is_dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[s.kb_cors_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_id_middleware(request, call_next):
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    register_error_handlers(app)

    from app.api import (
        auth,
        chat,
        data,
        documents,
        notes,
        podcasts,
        reports,
        search,
        settings,
        tasks,
    )

    app.include_router(auth.router)
    app.include_router(settings.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(notes.router)
    app.include_router(tasks.router)
    app.include_router(chat.router)
    app.include_router(reports.router)
    app.include_router(podcasts.router)
    app.include_router(data.router)

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok", "version": API_VERSION}

    # 报告静态服务：仅放行 .html（规格 §14 路径安全）
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/reports-html",
        StaticFiles(directory=s.reports_dir, html=False, check_dir=True),
        name="reports",
    )
    return app


app = create_app()
