// 引用标记解析（规格§9.2：语法 [d_xxx:bN]，与后端 agent/citations.py 同一正则）
export const CITATION_PATTERN = /\[(d_[A-Za-z0-9]+:b\d+)\]/g

/**
 * 把文本切成 text / citation 片段，供模板渲染内联可点引用。
 * 返回 [{ type: 'text', text } | { type: 'citation', token, docId, blockId }]
 */
export function splitByCitations(text) {
  if (!text) return []
  const out = []
  let last = 0
  for (const m of String(text).matchAll(CITATION_PATTERN)) {
    if (m.index > last) out.push({ type: 'text', text: text.slice(last, m.index) })
    const [docId, blockId] = m[1].split(':')
    out.push({ type: 'citation', token: m[1], docId, blockId })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ type: 'text', text: text.slice(last) })
  return out
}
