"""回归测试：覆盖本轮修复的纯函数级缺陷。"""

import json

from app.agent.orchestrator import truncate_observation
from app.parsing import excel, md
from app.rag.chunking import chunk_blocks
from app.report.builder import _render_inline, _script_json
from app.report.jinja_env import get_env


def test_chunk_overlap_keeps_header_and_only_real_block_ids():
    blocks = [
        {"block_id": "b1", "type": "heading", "level": 1, "text": "第一章"},
        {"block_id": "b2", "type": "paragraph", "text": "甲" * 600},
        {"block_id": "b3", "type": "paragraph", "text": "乙" * 300},
        {"block_id": "b4", "type": "heading", "level": 2, "text": "小节"},
        {"block_id": "b5", "type": "paragraph", "text": "丙" * 100},
    ]
    chunks = chunk_blocks(blocks)

    assert len(chunks) >= 3
    # 每个块都必须带章节前缀
    assert all(c["text"].startswith("【章节】") for c in chunks)
    # 第二块以第一块尾部 50 字开头，且只声明真正出现在文本里的 b2/b3
    second = chunks[1]
    assert second["block_ids"] == ["b2", "b3"]
    assert "甲" in second["text"] and "乙" in second["text"]
    # 章节边界不携带上一节尾部
    last = chunks[-1]
    assert last["section"] == "第一章 > 小节"
    assert last["block_ids"] == ["b5"]
    assert "丙" in last["text"]


def test_chunk_table_is_independent_and_prefixed():
    blocks = [
        {"block_id": "b1", "type": "heading", "level": 1, "text": "数据"},
        {"block_id": "b2", "type": "paragraph", "text": "说明" * 30},
        {"block_id": "b3", "type": "table", "caption": "表1", "data": [["A", "B"], ["1", "2"]]},
    ]
    chunks = chunk_blocks(blocks)
    table_chunks = [c for c in chunks if "【表格】" in c["text"]]
    assert len(table_chunks) == 1
    assert table_chunks[0]["block_ids"] == ["b3"]
    assert table_chunks[0]["section"] == "数据"


def test_md_table_only_is_valid(tmp_path):
    p = tmp_path / "t.md"
    p.write_text("| A | B |\n| --- | --- |\n| 1 | 2 |\n", encoding="utf-8")
    parsed = md.parse_md(p)
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].type == "table"
    assert parsed.blocks[0].data == [["A", "B"], ["1", "2"]]


def test_md_truly_empty_still_rejected():
    import tempfile
    from pathlib import Path

    import pytest

    from app.core.errors import ParseError

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "e.md"
        p.write_text("---\ntitle: 空\n---\n", encoding="utf-8")
        with pytest.raises(ParseError):
            md.parse_md(p)


def test_excel_headerless_first_row_is_preserved(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "无表头"
    ws.append([None, None, "备注"])  # 非空占比 1/3，不应被判为表头
    ws.append(["苹果", 3, "水果"])
    p = tmp_path / "d.xlsx"
    wb.save(p)

    parsed = excel.parse_excel(p)
    table = parsed.blocks[0]
    assert table.caption.endswith("（未识别表头）")
    assert table.data[0] == ["列1", "列2", "列3"]
    assert ["", "", "备注"] in table.data
    assert ["苹果", "3", "水果"] in table.data


def test_observation_truncation_is_valid_json_and_bounded():
    result = {"results": [{"chunk_id": f"c{i}", "text": "长" * 900} for i in range(8)]}
    raw, obj = truncate_observation(result)
    assert len(raw) <= 4000
    assert json.loads(raw) == obj
    assert obj.get("results") or obj.get("truncated")


def test_observation_fallback_is_valid_json():
    result = {"k": ["x" * 5000 for _ in range(3)]}
    raw, obj = truncate_observation(result)
    assert len(raw) <= 4000
    assert json.loads(raw) == obj


def test_report_citation_numbering_starts_at_one():
    html, citations = _render_inline("- 结论一 [d_1:b2]\n- 结论二 [d_1:b3]")
    assert len(citations) == 2
    assert 'data-cite="d_1:b2">[1]</sup>' in html
    assert 'data-cite="d_1:b3">[2]</sup>' in html


def test_report_template_does_not_escape_inline_script_or_json():
    citation_json = _script_json(
        [{"doc_id": "d_1", "block_id": "b1", "text": "</script><b>x</b>"}]
    )
    html = get_env().get_template("template.html").render(
        title="标题",
        intent="意图",
        sections=[],
        section_htmls=[],
        charts=[],
        chart_option_jsons=[],
        citation_json=citation_json,
        echarts_js="if (a < b && c > d) { window.__ok = 1; }",
        charts_truncated=False,
        generated_at="2026-10-20",
    )
    assert "if (a < b && c > d)" in html
    assert "&lt;script&gt;" not in html
    assert "</script><b>" not in html
    assert 'var CITEDATA = [{"doc_id": "d_1"' in html
