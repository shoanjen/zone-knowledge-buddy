import http from './http'

export async function generatePodcast(payload) {
  // payload: { doc_ids, intent, title?, style?, voice_a?, voice_b? }
  const { data } = await http.post('/podcasts/generate', payload)
  return data // { task_id }
}

export async function listPodcasts(params) {
  const { data } = await http.get('/podcasts', { params })
  return data // { total, items }
}

export async function getPodcast(id) {
  const { data } = await http.get(`/podcasts/${id}`)
  return data // 元数据 + turns
}

export async function fetchPodcastAudio(id) {
  const { data } = await http.get(`/podcasts/${id}/audio`, { responseType: 'blob' })
  return data // Blob(audio/mpeg)
}

export async function downloadPodcast(id) {
  const { data } = await http.get(`/podcasts/${id}/audio`, {
    params: { download: 1 },
    responseType: 'blob',
  })
  return data // Blob
}

export async function deletePodcast(id) {
  await http.delete(`/podcasts/${id}`)
}

export async function listVoices() {
  const { data } = await http.get('/podcasts/voices')
  return data // { voices: [{id,label}], styles: [] }
}
