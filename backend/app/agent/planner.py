"""Planner（规格 §8.2）：最多 6 步；失败降级固定模板。"""

from app.agent.context import TaskContext

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer"},
                    "description": {"type": "string"},
                    "tool_hint": {"type": "string"},
                },
                "required": ["no", "description"],
            },
        }
    },
    "required": ["steps"],
}

_SYSTEM = (
    "你是任务规划器，只输出 JSON。根据用户意图与文档清单，产出不超过 6 个具体、"
    "可执行的步骤；tool_hint 从这些工具里选：kb.search / kb.read / doc.list / doc.summary。"
)


def make_plan(ctx: TaskContext, intent: str, docs_brief: list[dict]) -> list[dict]:
    user = (
        f"用户意图：{intent}\n文档清单：{docs_brief}\n"
        '输出示例：{"steps":[{"no":1,"description":"检索三份文档中关于成本的数据","tool_hint":"kb.search"}]}'
    )
    try:
        out = ctx.llm_json(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            PLAN_SCHEMA,
            task_type="planner",
        )
        steps = out.get("steps") or []
        if steps:
            return steps[:6]
    except Exception:  # noqa: BLE001 — 规划失败降级固定模板
        pass
    return [
        {"no": 1, "description": "检索与意图相关的资料片段", "tool_hint": "kb.search"},
        {"no": 2, "description": "阅读关键原文块核对内容", "tool_hint": "kb.read"},
        {"no": 3, "description": "汇总产出最终结果", "tool_hint": None},
    ]
