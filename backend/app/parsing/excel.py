"""Excel 解析（规格 §6.4）：每个非空 sheet 一个 table 块；表头启发式。"""

from pathlib import Path

from openpyxl import load_workbook

from app.core.errors import ParseError
from app.parsing.ir import IRBlock, IRMeta, ParsedDoc

_MAX_ROWS = 100_000


def parse_excel(path: Path) -> ParsedDoc:
    try:
        wb = load_workbook(path, data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Excel 解析失败：{e}") from e

    blocks: list[IRBlock] = []
    sheet_count = 0
    truncated = False
    for ws in wb.worksheets:
        rows_raw = [list(r) for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows_raw if any(c is not None and str(c).strip() for c in r)]
        if not rows:
            continue
        sheet_count += 1
        if len(rows) > _MAX_ROWS:
            rows = rows[:_MAX_ROWS]
            truncated = True

        # 表头推断：首行非空占比 ≥60% 且行数 >1
        first = rows[0]
        non_empty_ratio = sum(1 for c in first if str(c).strip()) / max(len(first), 1)
        header_like = len(rows) > 1 and non_empty_ratio >= 0.6
        data = [[str(c) if c is not None else "" for c in r] for r in rows]
        caption = ws.title
        blocks.append(IRBlock(type="table", data=data, caption=caption))
        if not header_like and blocks:
            # 无表头：整体视为数据，caption 注明
            blocks[-1].caption = f"{caption}（未识别表头）"

    wb.close()
    if not blocks:
        raise ParseError("Excel 解析失败：所有 sheet 均为空")

    return ParsedDoc(
        meta=IRMeta(
            title=path.stem,
            pages_or_sheets=sheet_count,
            parse_quality="low" if truncated else "high",
            low_reason="oversize" if truncated else None,
        ),
        blocks=blocks,
    )
