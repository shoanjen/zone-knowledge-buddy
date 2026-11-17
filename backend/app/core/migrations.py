"""轻量迁移（规格 §3.2）：v1 create_all；后续演进用手写步骤表 + PRAGMA user_version。"""

from sqlalchemy import text

import app.models  # noqa: F401  确保所有表注册到 Base
from app.core.db import Base, engine

# (version, [sql...])；执行所有 version > 当前 user_version 的步骤后写入各自版本号
# v2：播客表（新库由 create_all 建出，旧库走此步骤；IF NOT EXISTS 保证两边幂等）
STEPS: list[tuple[int, list[str]]] = [
    (
        2,
        [
            """
            CREATE TABLE IF NOT EXISTS podcast (
                id VARCHAR(40) NOT NULL,
                title VARCHAR(256) NOT NULL,
                intent TEXT NOT NULL,
                style VARCHAR(32) NOT NULL,
                script_json TEXT NOT NULL,
                audio_path VARCHAR(512),
                duration_s FLOAT,
                voice_a VARCHAR(64) NOT NULL,
                voice_b VARCHAR(64) NOT NULL,
                source_doc_ids_json TEXT NOT NULL,
                task_id VARCHAR(40),
                created_at VARCHAR(32) NOT NULL,
                PRIMARY KEY (id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_podcast_task_id ON podcast (task_id)",
        ],
    ),
]


def run_migrations() -> None:
    with engine.begin() as conn:
        current = conn.execute(text("PRAGMA user_version")).scalar() or 0
        if current == 0:
            Base.metadata.create_all(conn)
            conn.execute(text("PRAGMA user_version = 1"))
            current = 1
        for version, sqls in STEPS:
            if version > current:
                for sql in sqls:
                    conn.execute(text(sql))
                conn.execute(text(f"PRAGMA user_version = {version}"))
                current = version
