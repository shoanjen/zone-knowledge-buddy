import http from './http'

export async function login(payload) {
  const { data } = await http.post('/auth/login', payload)
  return data // { token, expires_in, username }
}

export async function me() {
  const { data } = await http.get('/auth/me')
  return data // { username }
}
