"""Agent 任务上下文与同步 LLM 调用封装（规格 §8）。

任务运行在线程池中（无事件循环），LLM 异步调用经 asyncio.run 桥接。
"""

import asyncio
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.llm.gateway import GenerationParams, LLMGateway


@dataclass
class TaskContext:
    db: Session
    gateway: LLMGateway
    task_id: str
    task_type: str  # note.generate / report.generate
    doc_scope: list[str] = field(default_factory=list)  # 任务限定的文档集
    created_note_id: str | None = None  # note.write 工具产出，终态时更新
    scratch: dict = field(default_factory=dict)  # 工具间共享暂存（如图表 spec）

    def is_cancelled(self) -> bool:
        from app.models.tasks import AgentTask

        fresh = self.db.get(AgentTask, self.task_id)
        return fresh is None or fresh.status == "cancelled"

    def llm_json(self, messages: list[dict], schema: dict, *, task_type: str) -> dict:
        return asyncio.run(
            self.gateway.chat_json(messages, schema, task_type=task_type)
        )

    def llm_chat(self, messages: list[dict], *, task_type: str,
                 params: GenerationParams | None = None) -> str:
        return asyncio.run(
            self.gateway.chat(messages, task_type=task_type, params=params)
        )


def build_gateway(db: Session, provider_id: int | None):
    """按任务快照的 provider_id 构建网关；None 时取当前生效供应商。"""

    from app.core.errors import ProviderConfigError
    from app.llm.gateway import LLMGateway
    from app.llm.providers import ProviderSnapshot
    from app.models.llm import LLMProvider
    from app.models.settings import Setting

    row = None
    if provider_id is not None:
        row = db.get(LLMProvider, provider_id)
    if row is None:
        setting = db.get(Setting, "active_provider_id")
        if setting is None:
            raise ProviderConfigError("尚未启用任何模型供应商：请到设置页 activate")
        row = db.get(LLMProvider, int(setting.value_json))
    if row is None:
        raise ProviderConfigError("供应商不存在，请到设置页重新 activate")
    return LLMGateway(ProviderSnapshot.from_row(row))
