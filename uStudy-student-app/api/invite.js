import { request } from '@/utils/request'

export function getMyInvite() {
  return request({
    url: '/api/invites/me',
    method: 'GET'
  })
}

export function resolveInviteCode(code) {
  return request({
    url: '/api/invites/resolve',
    method: 'GET',
    data: { code },
    skipAuth: true,
    skipRefresh: true
  })
}

