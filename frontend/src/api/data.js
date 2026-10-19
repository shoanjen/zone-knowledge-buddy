import http from './http'

export async function exportData() {
  const { data } = await http.get('/data/export', { responseType: 'blob' })
  return data // Blob(application/zip)
}
