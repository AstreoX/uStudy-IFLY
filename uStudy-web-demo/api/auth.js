import { request } from '@/utils/request'

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

export function resetPassword(data) {
  return request({
    url: '/api/auth/reset-password',
    method: 'POST',
    data,
    skipAuth: true,
    skipRefresh: true
  })
}

export function activateCode(code) {
  return request({
    url: '/api/auth/activate',
    method: 'POST',
    data: { code }
  })
}
