import http from './http'

export async function listTasks(params) {
  const { data } = await http.get('/tasks', { params })
  return data // { total, items }
}

export async function getTask(id) {
  const { data } = await http.get(`/tasks/${id}`)
  return data // 详情：input + steps
}

export async function confirmTask(id, approve, contentMd = null) {
  const { data } = await http.post(`/tasks/${id}/confirm`, {
    approve,
    content_md: contentMd,
  })
  return data // { ok, status }
}

export async function cancelTask(id) {
  const { data } = await http.post(`/tasks/${id}/cancel`)
  return data
}
