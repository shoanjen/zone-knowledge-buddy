import http from './http'

export async function search(params) {
  // params: { q, top_k, doc_ids }
  const { data } = await http.get('/search', { params })
  return data // { results: [{ chunk_id, doc_id, block_ids, text, score, origin, title }] }
}
