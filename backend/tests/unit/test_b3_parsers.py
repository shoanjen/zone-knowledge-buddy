"""B3 验收：五格式解析器（规格 §6.4）。样例全部程序内生成（规格 §15.1）。"""

from pathlib import Path

import pytest

from app.core.errors import ParseError, ParseUnsupportedError
from app.parsing import excel, md, pdf, word


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> Path:
    """真实文本 PDF：两级标题 + 正文 + 表格。"""
    import fitz

    p = tmp_path_factory.mktemp("pdf") / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for text, size in [
        ("研究背景", 18),
        ("本文研究个人知识管理系统的自动整理方法。", 11),
        ("本段补充说明研究动机与现状，" + "知识工作者面临多格式资料分散的问题。" * 3, 11),
        ("相关工作", 16),
        ("已有系统多为云端黑盒方案，缺少可溯源能力。", 11),
        ("实验设置", 16),
        ("本文在自建数据集上评测三种方案。", 11),
    ]:
        page.insert_text((72, y), text, fontsize=size, fontname="china-s")
        y += size + 14
    # 表格区域（数字避免标点乱序）
    table_x, table_y = 72, y + 10
    for r, row in enumerate([["方案", "得分"], ["基线", "61"], ["本方法", "83"]]):
        for c, cell in enumerate(row):
            rect = fitz.Rect(table_x + c * 90, table_y + r * 18, table_x + (c + 1) * 90, table_y + (r + 1) * 18)
            page.insert_textbox(rect, cell, fontsize=10, fontname="china-s")
            page.draw_rect(rect)
    doc.save(p)
    doc.close()
    return p


@pytest.fixture(scope="module")
def scanned_pdf(tmp_path_factory) -> Path:
    """扫描件模拟：只有一页非文本图像（文本量极低）。"""
    import fitz

    p = tmp_path_factory.mktemp("pdf") / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(50, 50, 545, 700), color=(0, 0, 0), width=1)
    doc.save(p)
    doc.close()
    return p


def test_pdf_headings_and_table(sample_pdf):
    parsed = pdf.parse_pdf(sample_pdf)
    types = [b.type for b in parsed.blocks]
    assert "heading" in types and "paragraph" in types and "table" in types
    headings = [b for b in parsed.blocks if b.type == "heading"]
    assert any(b.level == 1 and "研究背景" in (b.text or "") for b in headings)
    tables = [b for b in parsed.blocks if b.type == "table"]
    assert tables and tables[0].data
    assert tables[0].data[0][0] == "方案"
    assert tables[0].data[1][1].strip() == "61"
    assert parsed.meta.parse_quality == "high"


def test_pdf_scanned_detected(scanned_pdf):
    parsed = pdf.parse_pdf(scanned_pdf)
    assert parsed.meta.parse_quality == "low"
    assert parsed.meta.low_reason == "scanned"


def test_word_docx(tmp_path):
    from docx import Document

    d = Document()
    d.add_heading("季度报告", level=1)
    d.add_paragraph("本季度营收稳步增长。")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "指标"
    t.cell(0, 1).text = "数值"
    t.cell(1, 0).text = "营收"
    t.cell(1, 1).text = "120"
    p = tmp_path / "a.docx"
    d.save(p)

    parsed = word.parse_word(p)
    assert parsed.blocks[0].type == "heading" and parsed.blocks[0].level == 1
    assert any(b.type == "table" and b.data == [["指标", "数值"], ["营收", "120"]] for b in parsed.blocks)


def test_word_rejects_doc_suffix(tmp_path):
    with pytest.raises(ParseUnsupportedError):
        word.parse_word(tmp_path / "old.doc")


def test_md_with_frontmatter_and_table(tmp_path):
    p = tmp_path / "n.md"
    p.write_text(
        "---\ntitle: 我的笔记\nauthor: 张三\n---\n"
        "# 标题一\n\n第一段内容。\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n",
        encoding="utf-8",
    )
    parsed = md.parse_md(p)
    assert parsed.meta.title == "我的笔记" and parsed.meta.author == "张三"
    assert parsed.blocks[0].type == "heading"
    tables = [b for b in parsed.blocks if b.type == "table"]
    assert tables and tables[0].data == [["A", "B"], ["1", "2"]]


def test_md_empty_rejected(tmp_path):
    p = tmp_path / "e.md"
    p.write_text("---\ntitle: 空\n---\n", encoding="utf-8")
    with pytest.raises(ParseError):
        md.parse_md(p)


def test_excel_sheets(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    ws.append(["名称", "数量"])
    ws.append(["苹果", 3])
    ws2 = wb.create_sheet("空表")
    ws2.append([])
    ws2.append([])
    p = tmp_path / "d.xlsx"
    wb.save(p)

    parsed = excel.parse_excel(p)
    tables = [b for b in parsed.blocks if b.type == "table"]
    assert len(tables) == 1  # 空 sheet 被跳过
    assert tables[0].caption == "数据"
    assert tables[0].data[0] == ["名称", "数量"]
    assert tables[0].data[1] == ["苹果", "3"]


def test_excel_all_empty_rejected(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    p = tmp_path / "empty.xlsx"
    wb.save(p)
    with pytest.raises(ParseError):
        excel.parse_excel(p)
