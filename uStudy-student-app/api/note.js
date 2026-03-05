import { request } from '@/utils/request'

/**
 * 获取学习空间笔记列表
 * @param {string|number} spaceId
 * @param {Object} [options]
 * @param {string|number} [options.nodeId] - 按节点筛选
 * @param {boolean} [options.freeOnly] - 仅返回自由笔记
 * @returns {Promise<Array>}
 */
export function getSpaceNotes(spaceId, { nodeId, freeOnly } = {}) {
  let url = `/api/spaces/${spaceId}/notes`
  const params = []
  if (nodeId !== undefined && nodeId !== null && nodeId !== '') {
    params.push(`node_id=${encodeURIComponent(nodeId)}`)
  }
  if (freeOnly) params.push('free_only=true')
  if (params.length) url += '?' + params.join('&')

  return request({
    url,
    method: 'GET'
  })
}

/**
 * 获取笔记详情
 * @param {string|number} spaceId
 * @param {string|number} noteId
 * @returns {Promise<Object>}
 */
export function getNoteDetail(spaceId, noteId) {
  return request({
    url: `/api/spaces/${spaceId}/notes/${noteId}`,
    method: 'GET'
  })
}
