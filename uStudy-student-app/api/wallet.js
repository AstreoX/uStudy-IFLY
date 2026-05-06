import { request } from '@/utils/request'

export function getWalletStatus() {
  return request({
    url: '/api/wallet/status',
    method: 'GET'
  })
}

export function getWalletTransactions(params = {}) {
  return request({
    url: '/api/wallet/transactions',
    method: 'GET',
    data: params
  })
}
