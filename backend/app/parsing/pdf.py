"""PDF 解析（规格 §6.4）：PyMuPDF；标题字号启发式 + 表格抽取 + 扫描件检测。"""

from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from app.core.errors import ParseError
from app.parsing.ir import IRBlock, IRMeta, ParsedDoc

_SCAN_MIN_CHARS = 30
_SCAN_PAGE_RATIO = 0.7


def _norm_text(s: str) -> str:
    return " ".join(s.split())


def parse_pdf(path: Path) -> ParsedDoc:
    try:
        doc = fitz.open(path)
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"PDF 无法打开：{e}") from e
    if doc.is_encrypted and not doc.authenticate(""):
        raise ParseError("PDF 解析失败：文件已加密")

    # 1) 全文字号统计 → 正文字号（众数）
    size_counter: Counter[float] = Counter()
    pages_text: list[dict] = []
    for page in doc:
        d = page.get_text("dict")
        spans = [s for b in d["blocks"] if b.get("type") == 0 for ln in b["lines"] for s in ln["spans"]]
        pages_text.append({"page": page.number, "spans": spans})
        for s in spans:
            if s["text"].strip():
                size_counter[round(s["size"], 1)] += len(s["text"])
    body_size = size_counter.most_common(1)[0][0] if size_counter else 10.0

    # 2) 标题字号集合（> 正文 × 1.15），按大小排名映射 level 1–4
    heading_sizes = sorted(
        {sz for sz, _ in size_counter.items() if sz > body_size * 1.15}, reverse=True
    )
    level_of = {sz: min(i + 1, 4) for i, sz in enumerate(heading_sizes)}

    # 3) 逐页抽取：表格与文本按页内坐标排序，保持原始阅读顺序
    blocks: list[IRBlock] = []
    low_pages = 0
    for pt in pages_text:
        page = doc[pt["page"]]
        page_items: list[tuple[float, float, int, str, object]] = []
        table_bboxes = []
        order = 0
        try:
            finder = page.find_tables()
            for t in getattr(finder, "tables", []):
                rows = t.extract()
                if rows and any(any(str(c).strip() for c in row) for row in rows):
                    rect = fitz.Rect(t.bbox)
                    table_bboxes.append(t.bbox)
                    data = [[_norm_text(str(c)) if c is not None else "" for c in row] for row in rows]
                    page_items.append(
                        (rect.y0, rect.x0, order, "table", IRBlock(type="table", data=data, caption=None))
                    )
                    order += 1
        except Exception:  # noqa: BLE001 — 个别页表格失败不致命
            pass

        page_chars = 0
        for s in pt["spans"]:
            txt = s["text"]
            page_chars += len(txt.strip())
            in_table = any(
                fitz.Rect(s["bbox"]).intersects(fitz.Rect(bb)) for bb in table_bboxes
            )
            if in_table:
                continue
            clean = _norm_text(txt)
            if not clean:
                continue
            page_items.append(
                (s["bbox"][1], s["bbox"][0], order, "text", (clean, round(s["size"], 1)))
            )
            order += 1

        page_items.sort(key=lambda item: (round(item[0], 1), item[1], item[2]))
        for _y, _x, _o, kind, payload in page_items:
            if kind == "table":
                blocks.append(payload)  # type: ignore[arg-type]
                continue
            clean, sz = payload  # type: ignore[misc]
            if sz in level_of and len(clean) < 60:
                blocks.append(IRBlock(type="heading", level=level_of[sz], text=clean))
            else:
                if blocks and blocks[-1].type == "paragraph":
                    blocks[-1].text = f"{blocks[-1].text} {clean}".strip()
                else:
                    blocks.append(IRBlock(type="paragraph", text=clean))
        if page_chars < _SCAN_MIN_CHARS:
            low_pages += 1

    quality, low_reason = "high", None
    if doc.page_count and low_pages / doc.page_count > _SCAN_PAGE_RATIO:
        quality, low_reason = "low", "scanned"

    title = None
    for b in blocks:
        if b.type == "heading" and b.text:
            title = b.text
            break

    return ParsedDoc(
        meta=IRMeta(
            title=title,
            author=doc.metadata.get("author") or None,
            pages_or_sheets=doc.page_count,
            parse_quality=quality,
            low_reason=low_reason,
        ),
        blocks=blocks,
    )
