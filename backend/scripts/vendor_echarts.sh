#!/usr/bin/env bash
# 把 frontend 安装的 echarts 供应商化到报告模板资产（规格 §11.2：禁 CDN，自包含单文件 HTML）。
# 用法：在仓库根执行 bash backend/scripts/vendor_echarts.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/frontend/node_modules/echarts/dist/echarts.min.js"
DST="$ROOT/backend/app/report/assets/echarts.min.js"

if [ ! -f "$SRC" ]; then
  echo "未找到 $SRC —— 请先在 frontend/ 执行 npm install" >&2
  exit 1
fi

cp "$SRC" "$DST"
echo "已复制 $(du -h "$DST" | cut -f1) → $DST"
