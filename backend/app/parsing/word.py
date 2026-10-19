"""Word(.docx) 解析（规格 §6.4）：python-docx；Heading N → heading。"""

from pathlib import Path

from docx import Document as DocxDocument

from app.core.errors import ParseError, ParseUnsupportedError
from app.parsing.ir import IRBlock, IRMeta, ParsedDoc


def parse_word(path: Path) -> ParsedDoc:
    if path.suffix.lower() == ".doc":
        raise ParseUnsupportedError("旧版 .doc 不支持，请转存为 .docx")
    try:
        d = DocxDocument(str(path))
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Word 解析失败：{e}") from e

    blocks: list[IRBlock] = []
    # 按文档体顺序遍历段落与表格
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    def _iter_body(parent):
        for child in parent.element.body.iterchildren():
            if child.tag.endswith("}p"):
                yield Paragraph(child, parent)
            elif child.tag.endswith("}tbl"):
                yield Table(child, parent)

    for item in _iter_body(d):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style = (item.style.name if item.style is not None else "") or ""
            if style.startswith("Heading") or style.startswith("标题"):
                digits = "".join(ch for ch in style if ch.isdigit())
                level = int(digits) if digits.isdigit() else 2
                blocks.append(IRBlock(type="heading", level=min(level, 6), text=text))
            else:
                blocks.append(IRBlock(type="paragraph", text=text))
        else:  # Table
            data = [[c.text.strip() for c in row.cells] for row in item.rows]
            if data and any(any(cell for cell in row) for row in data):
                blocks.append(IRBlock(type="table", data=data))

    title = next((b.text for b in blocks if b.type == "heading" and b.text), None)
    return ParsedDoc(
        meta=IRMeta(title=title, author=d.core_properties.author or None),
        blocks=blocks,
    )
