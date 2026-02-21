import { request } from '@/utils/request'

export function getSpaces() {
  return request({
    url: '/api/spaces',
    method: 'GET'
  })
}

export function getSpaceGraph(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/graph?_t=${Date.now()}`,
    method: 'GET'
  })
}
