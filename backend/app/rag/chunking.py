"""确定性分块（规格 §7.1）：目标 500 字/块、重叠 50 字、表格独立成块、章节路径前缀。"""

from typing import Any

TARGET = 500
OVERLAP = 50


def table_to_markdown(data: list[list[str]], caption: str | None = None) -> str:
    def esc(c: str) -> str:
        return str(c).replace("|", "\\|").replace("\n", " ")

    if not data:
        return ""
    header = data[0]
    rows = data[1:] if len(data) > 1 else []
    lines = ["| " + " | ".join(esc(c) for c in header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return (f"{caption}\n" if caption else "") + "\n".join(lines)


def chunk_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """输入有序块（dict: block_id/type/level/text/caption/data/ocr_text），输出 chunk 列表。"""
    results: list[dict[str, Any]] = []
    buf = ""
    buf_blocks: list[str] = []
    section: list[str] = []
    ov_text = ""
    ov_blocks: list[str] = []

    def close(carry: bool) -> None:
        nonlocal buf, buf_blocks, ov_text, ov_blocks
        text = buf.strip()
        if text:
            sec = " > ".join(section)
            header = f"【章节】{sec}\n" if sec else ""
            merged_blocks = list(dict.fromkeys(ov_blocks + buf_blocks))
            results.append(
                {
                    "text": (ov_text + text) if ov_text else (header + text),
                    "block_ids": merged_blocks,
                    "section": sec,
                }
            )
            ov_text, ov_blocks = ("", [])
            if carry:
                ov_text = text[-OVERLAP:]
                ov_blocks = list(buf_blocks)
        buf, buf_blocks = "", []

    for b in blocks:
        btype = b.get("type")
        if btype == "heading":
            if buf:
                close(carry=True)
            level = b.get("level") or 1
            title = (b.get("text") or "").strip()
            if title:
                del section[level - 1 :]
                section.append(title)
        elif btype == "paragraph":
            text = (b.get("text") or "").strip()
            if not text:
                continue
            buf = f"{buf}\n{text}".strip()
            buf_blocks.append(b["block_id"])
            if len(buf) >= TARGET:
                close(carry=True)
        elif btype == "image":
            text = (b.get("ocr_text") or "").strip()
            if text:
                buf = f"{buf}\n{text}".strip()
                buf_blocks.append(b["block_id"])
                if len(buf) >= TARGET:
                    close(carry=True)
        elif btype == "table":
            if buf:
                close(carry=False)
            md = table_to_markdown(b.get("data") or [], b.get("caption"))
            if md:
                sec = " > ".join(section)
                results.append(
                    {
                        "text": f"【表格】{md}" if not sec else f"【章节】{sec}\n【表格】{md}",
                        "block_ids": [b["block_id"]],
                        "section": sec,
                    }
                )
    if buf:
        close(carry=False)
    return results
