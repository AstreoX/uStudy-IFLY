import { request } from '@/utils/request'

/**
 * 获取空间文件夹列表
 * @param {string} spaceId
 * @param {string} contentType - 'notes' 或 'quizzes'
 * @returns {Promise<Array>}
 */
export function getFolders(spaceId, contentType) {
  return request({
    url: `/api/spaces/${spaceId}/folders?content_type=${contentType}`,
    method: 'GET'
  })
}

/**
 * 创建文件夹
 * @param {string} spaceId
 * @param {Object} data - { name, parent_id?, content_type }
 * @returns {Promise<Object>}
 */
export function createFolder(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}/folders`,
    method: 'POST',
    data
  })
}

/**
 * 重命名文件夹
 * @param {string} spaceId
 * @param {string} folderId
 * @param {Object} data - { name }
 * @returns {Promise<Object>}
 */
export function updateFolder(spaceId, folderId, data) {
  return request({
    url: `/api/spaces/${spaceId}/folders/${folderId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 删除文件夹
 * @param {string} spaceId
 * @param {string} folderId
 * @returns {Promise<void>}
 */
export function deleteFolder(spaceId, folderId) {
  return request({
    url: `/api/spaces/${spaceId}/folders/${folderId}`,
    method: 'DELETE'
  })
}

/**
 * 移动文件夹
 * @param {string} spaceId
 * @param {string} folderId
 * @param {Object} data - { target_parent_id }
 * @returns {Promise<Object>}
 */
export function moveFolder(spaceId, folderId, data) {
  return request({
    url: `/api/spaces/${spaceId}/folders/${folderId}/move`,
    method: 'POST',
    data
  })
}

/**
 * 批量移动笔记到文件夹
 * @param {string} spaceId
 * @param {Object} data - { item_ids: [], target_folder_id }
 * @returns {Promise<Object>}
 */
export function moveNotes(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}/folders/move-notes`,
    method: 'POST',
    data
  })
}

/**
 * 批量移动测试到文件夹
 * @param {string} spaceId
 * @param {Object} data - { item_ids: [], target_folder_id }
 * @returns {Promise<Object>}
 */
export function moveQuizzes(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}/folders/move-quizzes`,
    method: 'POST',
    data
  })
}
