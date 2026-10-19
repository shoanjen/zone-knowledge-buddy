"""轻量迁移（规格 §3.2）：v1 create_all；后续演进用手写步骤表 + PRAGMA user_version。"""

from sqlalchemy import text

import app.models  # noqa: F401  确保所有表注册到 Base
from app.core.db import Base, engine

# (version, [sql...])；执行所有 version > 当前 user_version 的步骤后写入各自版本号
STEPS: list[tuple[int, list[str]]] = []


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
