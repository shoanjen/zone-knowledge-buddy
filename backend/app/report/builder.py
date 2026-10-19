"""报告构建（规格 §11）：markdown 产出 → 分节 → 引用折叠标记 → 自包含 HTML。

安全：正文经 markdown-it（html=False，源内联 HTML 被转义）渲染后以 Markup 注入模板；
模板 autoescape 强制开启。
"""

import json
import re
from pathlib import Path

from markdown_it import MarkdownIt
from markupsafe import Markup
from sqlalchemy import select

from app.agent.citations import parse_citations
from app.core.config import get_settings
from app.core.ids import utc_now_iso
from app.models.documents import Block
from app.models.reports import Report
from app.models.tasks import AgentTask
from app.report.jinja_env import get_env, load_echarts_js

_md = MarkdownIt("commonmark")  # html=False：转义源内联 HTML
_TOKEN_RE = re.compile(r"\[(d_[A-Za-z0-9]+:b\d+)\]")


def _block_snapshot(db, doc_id: str, block_id: str) -> dict:
    b = db.scalar(select(Block).where(Block.doc_id == doc_id, Block.block_id == block_id))
    if b is None:
        return {"doc_id": doc_id, "block_id": block_id, "text": None, "missing": True}
    text = b.text
    if b.type == "table" and b.data_json:
        text = json.dumps(json.loads(b.data_json), ensure_ascii=False)[:800]
    return {"doc_id": doc_id, "block_id": block_id, "text": (text or "")[:600]}


def _render_inline(md_text: str) -> tuple[str, list[dict]]:
    """markdown → HTML，并把 [d_x:bN] 替换为 <sup>（预转义文本上的安全替换）。"""
    citations = parse_citations(md_text)

    def _sub(m: re.Match) -> str:
        token = m.group(1)
        idx = next((i + 1 for i, c in enumerate(citations)
                    if f"{c['doc_id']}:{c['block_id']}" == token[1:-1]), 0)
        return f"⟦CITE:{token}:{idx}⟧"

    placeholder = _TOKEN_RE.sub(_sub, md_text)
    html = _md.render(placeholder)
    # 占位符 → sup 标签（在已转义 HTML 上做纯文本替换，不引入注入面）
    html = re.sub(
        r"⟦CITE:(d_[A-Za-z0-9]+:b\d+):(\d+)⟧",
        r'<sup class="cite" data-cite="\1">[\2]</sup>',
        html,
    )
    return html, citations


def _split_sections(content_md: str) -> list[dict]:
    sections: list[dict] = []
    current_title = "概述"
    buf: list[str] = []
    seen_heading = False  # 首个 ## 之前的内容若只剩文档 H1 标题则不入节

    def _close() -> None:
        lines = [t for t in buf if t.strip()]
        if not lines:
            return
        if seen_heading or any(not t.strip().startswith("# ") for t in lines):
            sections.append({"heading": current_title, "lines": list(buf)})

    for line in content_md.splitlines():
        m = re.match(r"^##\s+(.*)", line.strip())
        if m:
            _close()
            seen_heading = True
            current_title = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    _close()
    return sections


def build_report(db, task: AgentTask, content_md: str, *, charts: list | None = None) -> Report:
    input_data = json.loads(task.input_json or "{}")
    title = next(
        (ln.lstrip("# ").strip() for ln in content_md.splitlines() if ln.startswith("# ")),
        input_data.get("title") or "未命名报告",
    )

    rendered_sections = []
    all_citations: list[dict] = []
    for i, sec in enumerate(_split_sections(content_md)):
        html, cits = _render_inline("\n".join(sec["lines"]))
        rendered_sections.append({"no": i + 1, "heading": sec["heading"], "html": html})
        for c in cits:
            if c not in all_citations:
                all_citations.append(c)

    citation_data = [_block_snapshot(db, c["doc_id"], c["block_id"]) for c in all_citations]
    charts = charts or []
    safe_charts = [
        {"title": c.get("title", "图表"), "option": c.get("echarts_option", {})} for c in charts
    ]

    html_out = get_env().get_template("template.html").render(
        title=title,
        intent=input_data.get("intent", ""),
        sections=rendered_sections,
        section_htmls=[  # 预组合，避免模板内 zip（Jinja2 无该全局）
            {"no": s["no"], "heading": s["heading"], "html": Markup(s["html"])}
            for s in rendered_sections
        ],
        charts=safe_charts,
        chart_option_jsons=[json.dumps(c["option"], ensure_ascii=False) for c in safe_charts],
        citation_json=json.dumps(citation_data, ensure_ascii=False),
        echarts_js=load_echarts_js(),
        generated_at=utc_now_iso(),
    )

    report = db.query(Report).filter(Report.task_id == task.id).one_or_none()
    if report is None:
        report = Report(
            title=title,
            intent=input_data.get("intent", ""),
            source_doc_ids_json=json.dumps(input_data.get("doc_ids", [])),
            task_id=task.id,
        )
        db.add(report)
        db.flush()
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.id}.html"
    path.write_text(html_out, encoding="utf-8")
    report.html_path = str(path)
    report.created_at = utc_now_iso()
    db.commit()
    return report
