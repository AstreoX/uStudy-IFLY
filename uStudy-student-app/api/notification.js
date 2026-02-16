/**
 * Notification SSE connection
 *
 * Connects to the notification stream endpoint for real-time updates
 * (mastery score changes, etc.)
 *
 * Includes automatic reconnection with backoff when the connection drops
 * unexpectedly (network flap, Android 120s XHR timeout, server restart, etc.).
 */

import { connectSSE } from '@/utils/sse'

const RETRY_DELAYS = [1000, 2000, 3000, 5000, 5000, 5000, 5000, 5000]
const MAX_RETRIES = RETRY_DELAYS.length

/**
 * Connect to the notification SSE stream.
 *
 * @param {Object} callbacks
 * @param {Function} [callbacks.onMasteryUpdate] - Called with { node_name, change, new_mastery }
 * @returns {Function} Abort function to close the connection
 */
export function connectNotificationStream(callbacks) {
  let intentionalAbort = false
  let retryCount = 0
  let retryTimer = null
  let innerAbort = null

  function connect() {
    let reconnectScheduled = false

    function tryScheduleReconnect() {
      if (reconnectScheduled) return
      reconnectScheduled = true
      scheduleReconnect()
    }

    innerAbort = connectSSE({
      url: '/api/notifications/stream',
      method: 'GET',
      onEvent: (eventType, data) => {
        // Any successful event proves the connection is healthy
        retryCount = 0

        if (eventType === 'mastery_update') {
          callbacks.onMasteryUpdate?.(data)
        }
      },
      onComplete: () => {
        console.warn('[Notification] SSE stream closed')
        tryScheduleReconnect()
      },
      onConnectionError: (err) => {
        console.warn('[Notification] SSE connection error:', err)
        tryScheduleReconnect()
      }
    })
  }

  function scheduleReconnect() {
    if (intentionalAbort) return
    if (retryCount >= MAX_RETRIES) {
      console.warn(`[Notification] Giving up after ${MAX_RETRIES} retries`)
      return
    }

    const delay = RETRY_DELAYS[retryCount]
    console.warn(`[Notification] Reconnecting in ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})`)
    retryCount++

    retryTimer = setTimeout(() => {
      retryTimer = null
      if (!intentionalAbort) {
        connect()
      }
    }, delay)
  }

  // Initial connection
  connect()

  // Return abort function — compatible with existing spaceChat.vue cleanup
  return () => {
    intentionalAbort = true
    if (retryTimer !== null) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    innerAbort?.()
  }
}
