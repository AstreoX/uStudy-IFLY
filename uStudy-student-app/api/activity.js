import { request } from '@/utils/request'

/**
 * 获取学习活动时间线
 * @param {number} page - 页码 (默认 1)
 * @param {number} limit - 每页条数 (默认 20)
 * @param {string} [spaceId] - 可选空间 ID 筛选
 * @param {string} [activityType] - 可选活动类型筛选
 * @returns {Promise<Object>} { items, total, page, limit }
 */
export function getActivityTimeline(page = 1, limit = 20, spaceId, activityType) {
  const data = { page, limit }
  if (spaceId) data.space_id = spaceId
  if (activityType) data.activity_type = activityType
  return request({
    url: '/api/activity/timeline',
    method: 'GET',
    data
  })
}
