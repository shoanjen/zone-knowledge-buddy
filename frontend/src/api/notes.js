import http from './http'

export async function generateNote(payload) {
  // payload: { doc_ids, intent, confirm_required }
  const { data } = await http.post('/notes/generate', payload)
  return data // { task_id }
}

export async function listNotes(params) {
  const { data } = await http.get('/notes', { params })
  return data // { total, items }
}

export async function getNote(id) {
  const { data } = await http.get(`/notes/${id}`)
  return data // 详情：content_md + citations
}

export async function updateNote(id, payload) {
  // payload: { title?, content_md?, tags? }
  const { data } = await http.put(`/notes/${id}`, payload)
  return data
}

export async function deleteNote(id) {
  await http.delete(`/notes/${id}`)
}
