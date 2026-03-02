import { request } from '@/utils/request'

export function getSearchSettings() {
  return request({
    url: '/api/search-settings',
    method: 'GET'
  })
}

export function updateSearchSettings(data) {
  return request({
    url: '/api/search-settings',
    method: 'PATCH',
    data
  })
}
