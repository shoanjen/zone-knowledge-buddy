"""Markdown 解析（规格 §6.4）：markdown-it-py token 流 + frontmatter。"""

import re
from pathlib import Path

from markdown_it import MarkdownIt

from app.core.errors import ParseError
from app.parsing.ir import IRBlock, IRMeta, ParsedDoc

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[m.end() :]


def parse_md(path: Path) -> ParsedDoc:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(raw)
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(body)

    blocks: list[IRBlock] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            level = int(t.tag[1])
            inline = tokens[i + 1]
            blocks.append(
                IRBlock(type="heading", level=level, text=(inline.content or "").strip())
            )
            i += 3  # heading_open + inline + heading_close
            continue
        if t.type == "paragraph_open":
            inline = tokens[i + 1]
            blocks.append(IRBlock(type="paragraph", text=(inline.content or "").strip()))
            i += 3
            continue
        if t.type == "table_open":
            rows: list[list[str]] = []
            j = i + 1
            row: list[str] = []
            while j < len(tokens) and tokens[j].type != "table_close":
                tk = tokens[j]
                if tk.type in ("th_open", "td_open"):
                    cell = tokens[j + 1].content if j + 1 < len(tokens) else ""
                    row.append((cell or "").strip())
                elif tk.type == "tr_close":
                    if row:
                        rows.append(row)
                    row = []
                j += 1
            if row:
                rows.append(row)
            if rows:
                blocks.append(IRBlock(type="table", data=rows))
            i = j + 1
            continue
        i += 1

    if not any(b.type in ("heading", "paragraph") for b in blocks):
        raise ParseError("MD 解析失败：无有效内容（empty）")

    return ParsedDoc(
        meta=IRMeta(
            title=fm.get("title") or next(
                (b.text for b in blocks if b.type == "heading" and b.text), None
            ),
            author=fm.get("author"),
        ),
        blocks=blocks,
    )
