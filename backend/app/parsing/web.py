"""网页解析（规格 §6.4）：trafilatura 主链 → Playwright 渲染兜底 → 明确失败。"""

import httpx
import trafilatura

from app.core.errors import ParseError, UrlInvalidError
from app.parsing.ir import IRBlock, IRMeta, ParsedDoc

_MIN_CHARS = 200
_FETCH_TIMEOUT_S = 30


def _fetch_html(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            timeout=_FETCH_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 zone-knowledge-buddy/0.1"},
        )
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        raise ParseError(f"网页抓取失败（fetch_failed）：{e}") from e


def _render_html(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ParseError(
            "动态渲染需要 Playwright（未安装浏览器内核：运行 playwright install chromium）"
        ) from e
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=_FETCH_TIMEOUT_S * 1000)
                page.wait_for_timeout(3000)
                return page.content()
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"网页渲染失败：{e}") from e


def _html_to_parsed(html: str, url: str) -> ParsedDoc | None:
    text = trafilatura.extract(html, output_format="txt", include_tables=True)
    if not text or len(text.strip()) < _MIN_CHARS:
        return None
    meta = trafilatura.extract_metadata(html)
    blocks: list[IRBlock] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) < 60 and not blocks:
            blocks.append(IRBlock(type="heading", level=1, text=para))
        else:
            blocks.append(IRBlock(type="paragraph", text=para))
    if not blocks:
        return None
    title = (meta.title if meta and meta.title else url)
    return ParsedDoc(meta=IRMeta(title=title[:200]), blocks=blocks)


def parse_web(url: str) -> ParsedDoc:
    if not url.startswith(("http://", "https://")):
        raise UrlInvalidError("URL 必须以 http(s):// 开头")
    html = _fetch_html(url)
    parsed = _html_to_parsed(html, url)
    if parsed is None:
        html2 = _render_html(url)
        parsed = _html_to_parsed(html2, url)
    if parsed is None:
        raise ParseError("网页正文抽取失败（web_empty）：正文过短或需要登录")
    return parsed
