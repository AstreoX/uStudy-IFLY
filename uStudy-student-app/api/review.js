import { request } from '@/utils/request'

/**
 * 获取到期/逾期复习项
 * @param {number} limit - 最大条数 (默认 20)
 * @returns {Promise<Object>} { items, total }
 * total 为符合 scheduled_date<=today 且 status=pending 的去重学习事件总数（按 activity_id 去重），
 * items 为按 limit 截断后的子集。
 */
export function getDueReviews(limit = 20) {
  return request({
    url: '/api/review/due',
    method: 'GET',
    data: { limit }
  })
}
