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
    """输入有序块（dict: block_id/type/level/text/caption/data/ocr_text），输出 chunk 列表。

    每个块文本都带【章节】前缀；50 字重叠只继承真正落在尾部窗口内的 block_id，
    避免把未出现在块文本中的原文块声明为来源（反思/引用会据此误判支撑）。
    """
    results: list[dict[str, Any]] = []
    parts: list[str] = []  # 当前缓冲区中的段落片段
    ids: list[str] = []  # 与 parts 一一对应的 block_id
    section: list[str] = []
    carry_text = ""
    carry_ids: list[str] = []

    def _flush(carry: bool) -> None:
        nonlocal parts, ids, carry_text, carry_ids
        body = "\n".join(p for p in parts).strip()
        if not body:
            parts, ids = [], []
            return
        sec = " > ".join(section)
        header = f"【章节】{sec}\n" if sec else ""
        text = (carry_text + "\n" if carry_text else "") + body
        chunk_ids = list(dict.fromkeys(carry_ids + ids))
        results.append({"text": header + text, "block_ids": chunk_ids, "section": sec})

        if carry:
            tail = body[-OVERLAP:]
            need = len(tail)
            acc = 0
            tail_ids: list[str] = []
            for part, bid in zip(reversed(parts), reversed(ids), strict=False):
                if acc >= need:
                    break
                tail_ids.append(bid)
                acc += len(part) + 1
            carry_text = tail
            carry_ids = list(dict.fromkeys(reversed(tail_ids)))
        else:
            carry_text, carry_ids = "", []
        parts, ids = [], []

    for b in blocks:
        btype = b.get("type")
        if btype == "heading":
            # 章节边界不携带上一节尾部，保证新块前缀与正文同属一节
            if parts:
                _flush(carry=False)
            level = b.get("level") or 1
            title = (b.get("text") or "").strip()
            if title:
                del section[level - 1 :]
                section.append(title)
        elif btype == "paragraph":
            text = (b.get("text") or "").strip()
            if not text:
                continue
            parts.append(text)
            ids.append(b["block_id"])
            if sum(len(p) + 1 for p in parts) >= TARGET:
                _flush(carry=True)
        elif btype == "image":
            text = (b.get("ocr_text") or "").strip()
            if text:
                parts.append(text)
                ids.append(b["block_id"])
                if sum(len(p) + 1 for p in parts) >= TARGET:
                    _flush(carry=True)
        elif btype == "table":
            if parts:
                _flush(carry=False)
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
    if parts:
        _flush(carry=False)
    return results
