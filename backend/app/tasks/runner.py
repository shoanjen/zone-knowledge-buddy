"""统一异步任务执行器（规格 §6.2）：线程池 max_workers=2，与解析/Agent 共享。"""

import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("kb.runner")

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kb-task")


def submit(fn, *args, **kwargs) -> None:
    """投递后台任务；异常在任务内消化并写库，不外抛。"""
    def _wrapped():
        try:
            fn(*args, **kwargs)
        except Exception:  # noqa: BLE001 — 兜底日志，正常路径已自行落 failed
            logger.exception("后台任务异常：%s", fn)

    _pool.submit(_wrapped)
