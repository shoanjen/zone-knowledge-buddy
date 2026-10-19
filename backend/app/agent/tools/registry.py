"""工具注册表（规格 §8.3）：@register 装饰器；按任务类型过滤可用集合。"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.context import TaskContext


@dataclass
class ToolDef:
    name: str
    fn: Callable[[TaskContext, dict], dict]
    input_schema: dict
    description: str
    task_types: set[str] | None  # None = 所有任务可用


TOOLS: dict[str, ToolDef] = {}


def register(name: str, input_schema: dict, description: str, task_types: set[str] | None = None):
    def _wrap(fn: Callable[[TaskContext, dict], dict]):
        TOOLS[name] = ToolDef(name, fn, input_schema, description, task_types)
        return fn

    return _wrap


def available_tools(task_type: str) -> dict[str, ToolDef]:
    return {
        name: t
        for name, t in TOOLS.items()
        if t.task_types is None or task_type in t.task_types
    }


def call_tool(ctx: TaskContext, name: str, args: dict) -> dict:
    """执行工具；未知/参数错误返回结构化 error observation（循环继续，规格 §8.4）。"""
    tool = available_tools(ctx.task_type).get(name)
    if tool is None:
        return {"error": f"UNKNOWN_TOOL: {name}"}
    try:
        return tool.fn(ctx, args or {})
    except Exception as e:  # noqa: BLE001 — 工具错误作为 observation 返回
        return {"error": f"{type(e).__name__}: {e}"}


def tools_brief(task_type: str) -> str:
    lines = []
    for name, t in sorted(available_tools(task_type).items()):
        lines.append(f"- {name}: {t.description} 入参 Schema: {t.input_schema}")
    return "\n".join(lines)


def tool_schema_any() -> dict:
    return {"type": "object"}


def _not_implemented(*_: Any, **__: Any) -> dict:  # pragma: no cover
    raise NotImplementedError
