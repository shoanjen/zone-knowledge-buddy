"""Jinja2 环境（规格 §11.2）：autoescape 强制开启；预渲染 HTML 用 Markup 显式标记。"""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent
ASSETS_DIR = TEMPLATE_DIR / "assets"


@lru_cache
def get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
    )


def load_echarts_js() -> str:
    p = ASSETS_DIR / "echarts.min.js"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return "console.warn('echarts.min.js 未 vendor：运行 scripts/vendor_echarts.sh');"
