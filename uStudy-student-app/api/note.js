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

/**
 * 更新笔记
 * @param {string|number} spaceId
 * @param {string|number} noteId
 * @param {Object} data - { title, content }
 * @returns {Promise<Object>}
 */
export function updateNote(spaceId, noteId, data) {
  return request({
    url: `/api/spaces/${spaceId}/notes/${noteId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 删除笔记
 * @param {string|number} spaceId
 * @param {string|number} noteId
 * @returns {Promise<void>}
 */
export function deleteNote(spaceId, noteId) {
  return request({
    url: `/api/spaces/${spaceId}/notes/${noteId}`,
    method: 'DELETE'
  })
}

/**
 * 创建笔记
 * @param {string|number} spaceId
 * @param {Object} data - { title, content, node_id, sort_order } (all optional)
 * @returns {Promise<Object>}
 */
export function createNote(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}/notes`,
    method: 'POST',
    data
  })
}
