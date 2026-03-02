import { request } from '@/utils/request'

/**
 * 获取用户搜索渠道设置
 * @returns {Promise<Object>} { web_search_enabled, academic_search_enabled, encyclopedia_search_enabled, course_search_enabled }
 */
export function getSearchSettings() {
  return request({
    url: '/api/search-settings',
    method: 'GET'
  })
}

/**
 * 更新用户搜索渠道设置（局部更新）
 * @param {Object} data - 要更新的字段
 * @returns {Promise<Object>} 更新后的完整设置
 */
export function updateSearchSettings(data) {
  return request({
    url: '/api/search-settings',
    method: 'PATCH',
    data
  })
}
