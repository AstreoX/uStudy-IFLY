import { request } from '@/utils/request'

/**
 * 获取某活动的复习计划
 * @param {string} activityId - 活动 ID
 * @returns {Promise<Object>} { activity_id, items }
 */
export function getActivityReviews(activityId) {
  return request({
    url: `/api/review/activity/${activityId}`,
    method: 'GET'
  })
}

/**
 * 获取到期/逾期复习项
 * @param {number} limit - 最大条数 (默认 20)
 * @returns {Promise<Object>} { items, total }
 */
export function getDueReviews(limit = 20) {
  return request({
    url: '/api/review/due',
    method: 'GET',
    data: { limit }
  })
}

/**
 * 手动标记复习完成
 * @param {string} reviewId - 复习记录 ID
 * @returns {Promise<Object>} { success }
 */
export function completeReview(reviewId) {
  return request({
    url: '/api/review/complete',
    method: 'POST',
    data: { review_id: reviewId }
  })
}
