import http from './http'

export async function listProviders() {
  const { data } = await http.get('/settings/providers')
  return data // [{ id, type, name, base_url, model, is_active, has_api_key }]
}

export async function createProvider(payload) {
  // payload: { type, name, base_url, model, api_key? }
  const { data } = await http.post('/settings/providers', payload)
  return data
}

export async function updateProvider(id, payload) {
  const { data } = await http.put(`/settings/providers/${id}`, payload)
  return data
}

export async function deleteProvider(id) {
  await http.delete(`/settings/providers/${id}`)
}

export async function testProvider(id) {
  const { data } = await http.post(`/settings/providers/${id}/test`)
  return data // { ok, latency_ms, models, error? } —— 失败也是 200
}

export async function activateProvider(id) {
  const { data } = await http.post(`/settings/providers/${id}/activate`)
  return data
}

export async function getSettings() {
  const { data } = await http.get('/settings')
  return data // { active_provider_id, generation_params, embedding, embedding_locked }
}

export async function putSettings(payload) {
  // payload: { generation_params?, embedding? }
  const { data } = await http.put('/settings', payload)
  return data
}
