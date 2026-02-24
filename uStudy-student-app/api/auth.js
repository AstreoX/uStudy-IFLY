import { request } from '@/utils/request'

export function register(data) {
  return request({
    url: '/api/auth/register',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function sendCode(data) {
  return request({
    url: '/api/auth/send-code',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function verifyCode(data) {
  return request({
    url: '/api/auth/verify-code',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function registerWithCode(data) {
  return request({
    url: '/api/auth/register-with-code',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function resetPassword(data) {
  return request({
    url: '/api/auth/reset-password',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function login(data) {
  return request({
    url: '/api/auth/login',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function appleLogin(idToken) {
  return request({
    url: '/api/auth/apple',
    method: 'POST',
    data: { id_token: idToken },
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

export function updateNickname(nickname) {
  return request({
    url: '/api/auth/me',
    method: 'PATCH',
    data: { nickname }
  })
}
