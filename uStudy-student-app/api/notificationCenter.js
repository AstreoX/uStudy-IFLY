/**
 * Notification Center REST API
 *
 * CRUD operations for persistent in-app notifications.
 * (Separate from notification.js which handles the SSE stream.)
 */

import { request } from '@/utils/request'

/**
 * 获取通知列表（分页）
 */
export function getNotifications({ offset = 0, limit = 20, unreadOnly = false } = {}) {
  return request({
    url: '/api/notifications',
    method: 'GET',
    data: { offset, limit, unread_only: unreadOnly },
  })
}

/**
 * 获取未读通知数量
 */
export function getUnreadCount() {
  return request({
    url: '/api/notifications/unread-count',
    method: 'GET',
  })
}

/**
 * 标记单条通知为已读
 */
export function markNotificationRead(notificationId) {
  return request({
    url: `/api/notifications/${notificationId}/read`,
    method: 'PATCH',
  })
}

/**
 * 标记全部通知为已读
 */
export function markAllNotificationsRead() {
  return request({
    url: '/api/notifications/read-all',
    method: 'PATCH',
  })
}
