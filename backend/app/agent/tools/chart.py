"""图表规格工具（规格 §8.3 / §11.1）：纯确定性转换，工具内不调用 LLM。

字段选择由 executor 层 LLM 决定后传入（先 kb.read 看表头，再选 type/字段）。
"""

import json

from sqlalchemy import select

from app.agent.tools.registry import register
from app.models.documents import Block


def build_echarts_option(chart_type: str, title: str, header: list[str],
                         rows: list[list[str]], x_field: str, y_field: str) -> dict:
    xi = header.index(x_field)
    yi = header.index(y_field)

    def num(v: str):
        try:
            return float(str(v).replace(",", ""))
        except ValueError:
            return v

    xs = [r[xi] for r in rows]
    ys = [num(r[yi]) for r in rows]
    base = {"title": {"text": title}, "tooltip": {}}
    if chart_type == "pie":
        return {**base,
                "series": [{"type": "pie", "radius": "60%",
                            "data": [{"name": x, "value": y} for x, y in zip(xs, ys, strict=True)]}]}
    return {**base,
            "xAxis": {"type": "category", "data": xs},
            "yAxis": {"type": "value"},
            "series": [{"type": chart_type, "data": ys}]}  # bar / line


@register(
    "chart.spec",
    {"type": "object",
     "properties": {
         "doc_id": {"type": "string"}, "block_id": {"type": "string"},
         "chart_type": {"enum": ["bar", "line", "pie"]},
         "title": {"type": "string"},
         "x_field": {"type": "string"}, "y_field": {"type": "string"},
     },
     "required": ["doc_id", "block_id", "chart_type", "title", "x_field", "y_field"]},
    "将表格块转为 ECharts 图表规格（先 kb.read 查看表头后调用）",
    task_types={"report.generate"},
)
def chart_spec(ctx, args: dict) -> dict:
    block = ctx.db.scalar(
        select(Block).where(Block.doc_id == args["doc_id"], Block.block_id == args["block_id"])
    )
    if block is None or block.type != "table":
        return {"error": f"NOT_TABLE: {args['doc_id']}:{args['block_id']}"}
    data = json.loads(block.data_json or "[]")
    if len(data) < 2:
        return {"error": "EMPTY_TABLE: 表格无数据行"}
    header, rows = data[0], data[1:]
    x_field, y_field = args["x_field"], args["y_field"]
    if x_field not in header or y_field not in header:
        return {"error": f"FIELD_NOT_FOUND: 可用字段 {header}"}
    option = build_echarts_option(args["chart_type"], args["title"], header, rows, x_field, y_field)
    spec = {
        "type": args["chart_type"], "title": args["title"],
        "x_field": x_field, "y_field": y_field,
        "data_source_block_id": args["block_id"], "doc_id": args["doc_id"],
        "echarts_option": option,
    }
    ctx.scratch.setdefault("charts", []).append(spec)
    return {"chart": {k: spec[k] for k in ("type", "title", "x_field", "y_field")},
            "echarts_option": option}
