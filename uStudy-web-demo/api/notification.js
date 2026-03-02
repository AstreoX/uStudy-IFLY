/**
 * Notification SSE connection for web frontend
 *
 * Connects to the notification stream endpoint for real-time updates
 * (mastery score changes, etc.)
 *
 * Includes automatic reconnection with exponential backoff.
 */

import { connectSSE } from '@/utils/sse'

const RETRY_DELAYS = [1000, 2000, 3000, 5000, 5000, 5000, 5000, 5000]
const MAX_RETRIES = RETRY_DELAYS.length

/**
 * Connect to the notification SSE stream.
 *
 * @param {Object} callbacks
 * @param {Function} [callbacks.onMasteryUpdate] - Called with { node_name, change, new_mastery }
 * @param {Function} [callbacks.onDebugLog] - Optional debug logger
 * @returns {Function} Abort function to close the connection and stop retries
 */
export function connectNotificationStream(callbacks) {
  let intentionalAbort = false
  let retryCount = 0
  let retryTimer = null
  let innerAbort = null

  function connect() {
    let reconnectScheduled = false
    callbacks.onDebugLog?.(`[Notification] connect() attempt ${retryCount + 1}`)

    function tryScheduleReconnect() {
      if (reconnectScheduled) return
      reconnectScheduled = true
      scheduleReconnect()
    }

    innerAbort = connectSSE({
      url: '/api/notifications/stream',
      method: 'GET',
      onEvent: (eventType, data) => {
        retryCount = 0

        if (eventType === '_heartbeat') {
          callbacks.onDebugLog?.('[Notification] heartbeat')
          return
        }

        if (eventType === 'mastery_update') {
          callbacks.onMasteryUpdate?.(data)
        }
      },
      onComplete: () => {
        callbacks.onDebugLog?.('[Notification] SSE stream closed')
        tryScheduleReconnect()
      },
      onConnectionError: (err) => {
        callbacks.onDebugLog?.(`[Notification] SSE error: ${err?.message || err}`)
        tryScheduleReconnect()
      }
    })
  }

  function scheduleReconnect() {
    if (intentionalAbort) return
    if (retryCount >= MAX_RETRIES) {
      callbacks.onDebugLog?.(`[Notification] Giving up after ${MAX_RETRIES} retries`)
      return
    }

    const delay = RETRY_DELAYS[retryCount]
    callbacks.onDebugLog?.(`[Notification] Reconnecting in ${delay}ms (${retryCount + 1}/${MAX_RETRIES})`)
    retryCount++

    retryTimer = setTimeout(() => {
      retryTimer = null
      if (!intentionalAbort) {
        connect()
      }
    }, delay)
  }

  connect()

  return () => {
    intentionalAbort = true
    if (retryTimer !== null) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    innerAbort?.()
  }
}
