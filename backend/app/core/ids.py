"""ID 与时间约定（规格 §2.5）：ULID 前缀 ID；UTC ISO8601 时间。"""

from datetime import UTC, datetime

from ulid import ULID


def new_id(prefix: str) -> str:
    return f"{prefix}_{ULID()}"


def new_doc_id() -> str:
    return new_id("d")


def new_chunk_id() -> str:
    return new_id("c")


def new_note_id() -> str:
    return new_id("n")


def new_report_id() -> str:
    return new_id("r")


def new_podcast_id() -> str:
    return new_id("p")


def new_task_id() -> str:
    return new_id("t")


def new_session_id() -> str:
    return new_id("s")


def new_message_id() -> str:
    return new_id("m")


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_request_id() -> str:
    return new_id("req")
