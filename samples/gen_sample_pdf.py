#!/usr/bin/env python
"""生成测试样例 PDF：两级标题 + 正文 + 数据表格（复用 B3 测试的生成方式）。"""
import sys
from pathlib import Path

import fitz

OUT = Path(__file__).resolve().parent.parent / "samples" / "样例-项目调研报告.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

doc = fitz.open()
page = doc.new_page()

y = 72
for text, size in [
    ("智能客服系统调研报告", 20),
    ("本报告调研三家智能客服供应商的方案与报价，供选型决策参考。", 11),
    ("调研覆盖工单自动分派、多轮对话、知识库问答三类核心场景，" * 4, 11),
    ("一、调研背景", 16),
    ("客服团队日均处理工单约 1200 单，其中 40% 为重复咨询。", 11),
    ("引入智能客服的目标是将重复咨询的人工占比降到 15% 以内，" * 3, 11),
    ("二、供应商对比", 16),
    ("三家供应商均支持私有化部署，差异主要在对话能力与报价结构。", 11),
    ("三、结论与建议", 16),
    ("建议优先试点乙方案，其知识库问答能力与现有资料库衔接成本最低。", 11),
]:
    page.insert_text((72, y), text, fontsize=size, fontname="china-s")
    y += size + 16

# 数据表格（带边框线，供 find_tables 识别为独立 table 块）
table_x, table_y = 72, y + 12
rows = [
    ["供应商", "工单分派", "多轮对话", "知识库问答", "年报价"],
    ["甲方案", "支持", "支持", "基础版", "18"],
    ["乙方案", "支持", "支持", "完整版", "26"],
    ["丙方案", "不支持", "支持", "完整版", "12"],
]
col_w = [80, 80, 80, 90, 60]
for r, row in enumerate(rows):
    x = table_x
    for c, cell in enumerate(row):
        rect = fitz.Rect(x, table_y + r * 20, x + col_w[c], table_y + (r + 1) * 20)
        page.insert_textbox(rect, cell, fontsize=10, fontname="china-s")
        page.draw_rect(rect)
        x += col_w[c]

doc.save(OUT)
doc.close()
print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
