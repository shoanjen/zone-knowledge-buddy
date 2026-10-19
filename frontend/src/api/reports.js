import http from './http'

export async function generateReport(payload) {
  // payload: { doc_ids, intent, title? }
  const { data } = await http.post('/reports/generate', payload)
  return data // { task_id }
}

export async function listReports(params) {
  const { data } = await http.get('/reports', { params })
  return data // { total, items }
}

export async function getReport(id) {
  const { data } = await http.get(`/reports/${id}`)
  return data // 元数据 + sections + size_bytes
}

export async function fetchReportHtml(id) {
  const { data } = await http.get(`/reports/${id}/html`, { responseType: 'blob' })
  return data // Blob(text/html)
}

export async function downloadReport(id) {
  const { data } = await http.get(`/reports/${id}/html`, {
    params: { download: 1 },
    responseType: 'blob',
  })
  return data // Blob
}
