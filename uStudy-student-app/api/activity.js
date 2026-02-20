import { request } from '@/utils/request'

/**
 * 获取学习活动时间线
 * @param {number} page - 页码 (默认 1)
 * @param {number} limit - 每页条数 (默认 20)
 * @param {string} [spaceId] - 可选空间 ID 筛选
 * @param {string} [activityType] - 可选活动类型筛选
 * @returns {Promise<Object>} { items, total, page, limit }
 * items[] 包含 `next_review_date` 与 `review_completed_today`
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

/**
 * 获取 AI 学习建议
 * @param {boolean} [refresh] - 是否绕过缓存强制刷新
 * @returns {Promise<Object>} { decision, subject, guidance, title, source }
 */
export function getStudySuggestion(refresh = false) {
  const data = {}
  if (refresh) data.refresh = true
  return request({
    url: '/api/activity/suggestion',
    method: 'GET',
    data
  })
}
