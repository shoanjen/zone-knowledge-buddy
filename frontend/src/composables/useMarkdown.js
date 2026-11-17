// 回答 markdown 渲染：完整 markdown → HTML；引用标记先替换为占位符，
// 渲染后回填为可点 chip（样式与 CitationPopover 一致，点击行为由宿主委托处理）。
import MarkdownIt from 'markdown-it'
import { CITATION_PATTERN } from './useCitation'

const md = new MarkdownIt({
  html: false, // LLM 输出中的原始 HTML 一律转义，防注入
  linkify: true,
  breaks: true, // 单换行渲染为 <br>，聊天气泡阅读更自然
})

// 链接统一新窗口打开
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  ((tokens, idx, opts, _, self) => self.renderToken(tokens, idx, opts))
md.renderer.rules.link_open = (tokens, idx, opts, _, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, opts, _, self)
}

// 占位符使用方头括号，markdown-it 不会将其解析为语法
const CITE_SLOT = /⟦cite:(\d+)⟧/g

/**
 * 渲染 markdown 并抽取引用。
 * 返回 { html, cites }：cites[i] 对应 HTML 中 data-cite="i" 的 chip。
 */
export function renderMarkdownWithCitations(text) {
  const cites = []
  const index = new Map()
  const src = String(text || '').replace(CITATION_PATTERN, (_, token) => {
    if (index.has(token)) return `⟦cite:${index.get(token)}⟧`
    const i = cites.length
    const [docId, blockId] = token.split(':')
    cites.push({ doc_id: docId, block_id: blockId })
    index.set(token, i)
    return `⟦cite:${i}⟧`
  })

  let html = md.render(src)
  html = html.replace(CITE_SLOT, (_, i) => {
    const c = cites[Number(i)]
    const short = String(c.doc_id || '').slice(0, 8)
    return `<span class="cite-ref" data-cite="${i}">[${short}…:${c.block_id}]</span>`
  })
  return { html, cites }
}
