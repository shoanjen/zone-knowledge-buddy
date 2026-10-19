"""ReAct 执行器（规格 §8.4）：每步产出 tool 调用或 final 内容。"""

from app.agent.context import TaskContext
from app.agent.tools.registry import tools_brief

STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"enum": ["tool", "final"]},
        "thought": {"type": "string"},
        "tool": {"type": "string"},
        "args": {"type": "object"},
        "content": {"type": "string"},
    },
    "required": ["type"],
}

CITATION_RULE = (
    "每条事实性结论尾部必须标注引用标记 [doc_id:block_id]（如 [d_01J8:b3]），"
    "且引用必须来自工具返回的真实块；资料不足以支撑时明确说明，禁止编造。"
)


def build_system(ctx: TaskContext, plan_text: str, final_hint: str) -> str:
    return (
        "你是知识整理 Agent。严格按计划执行，通过调用工具获取信息。\n"
        f"可用工具：\n{tools_brief(ctx.task_type)}\n"
        f"执行计划：\n{plan_text}\n"
        "每一步只输出一个 JSON 对象：\n"
        '调用工具：{"type":"tool","thought":"...","tool":"工具名","args":{...}}\n'
        '最终产出：{"type":"final","thought":"...","content":"最终 markdown 产出"}\n'
        f"{CITATION_RULE}\n{final_hint}"
    )


def run_step(
    ctx: TaskContext, system: str, history: list[dict], *, feedback: str = ""
) -> dict:
    messages = [{"role": "system", "content": system}, *history]
    if feedback:
        messages.append({"role": "user", "content": feedback})
    return ctx.llm_json(messages, STEP_SCHEMA, task_type="tool")
