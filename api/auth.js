import { request } from '@/utils/request'

export function login(data) {
  return request({
    url: '/api/auth/login',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function refreshToken(refreshTokenValue) {
  return request({
    url: '/api/auth/refresh',
    method: 'POST',
    data: { refresh_token: refreshTokenValue },
    skipAuth: true,
    skipRefresh: true
  })
}

export function getMe() {
  return request({
    url: '/api/auth/me',
    method: 'GET'
  })
}
