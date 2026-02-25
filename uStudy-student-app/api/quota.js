import { request } from '@/utils/request'

export function getQuotaStatus() {
  return request({ url: '/api/quota/status', method: 'GET' })
}
