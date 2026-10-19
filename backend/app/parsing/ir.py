"""DocumentIR：全系统统一文档中间表示（规格 §6.3）。

解析器产出 ParsedDoc（block_id 由 dispatcher 统一编号 b1..bn），
落库映射：block 表每块一行（data_json 存表格/图片扩展字段）。
"""

from typing import Literal

from pydantic import BaseModel, Field

SourceT = Literal["pdf", "word", "md", "excel", "web"]
BlockT = Literal["heading", "paragraph", "table", "image"]


class IRBlock(BaseModel):
    block_id: str = ""
    type: BlockT
    level: int | None = None
    text: str | None = None
    caption: str | None = None
    data: list[list[str]] | None = None
    ref: str | None = None
    ocr_text: str | None = None


class IRSource(BaseModel):
    type: SourceT
    origin: str = ""
    imported_at: str = ""


class IRMeta(BaseModel):
    title: str | None = None
    author: str | None = None
    pages_or_sheets: int | None = None
    parse_quality: Literal["high", "low"] = "high"
    low_reason: str | None = None


class DocumentIR(BaseModel):
    doc_id: str
    source: IRSource
    meta: IRMeta
    blocks: list[IRBlock] = Field(default_factory=list)


class ParsedDoc(BaseModel):
    """解析器返回值：meta + 未编号的块序列。"""

    meta: IRMeta
    blocks: list[IRBlock]
