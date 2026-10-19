import http from './http'

export async function uploadDocuments(files) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const { data } = await http.post('/documents/upload', form)
  return data // { items: [{ doc_id, filename, status }] }
}

export async function importUrl(url) {
  const { data } = await http.post('/documents/url', { url })
  return data // { doc_id, status }
}

export async function listDocuments(params) {
  const { data } = await http.get('/documents', { params })
  return data // { total, items: [...] }
}

export async function getDocument(id) {
  const { data } = await http.get(`/documents/${id}`)
  return data // 列表字段 + blocks + blocks_truncated
}

export async function deleteDocument(id) {
  await http.delete(`/documents/${id}`)
}

export async function retryDocument(id) {
  const { data } = await http.post(`/documents/${id}/retry`)
  return data
}
