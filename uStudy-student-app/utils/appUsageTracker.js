/**
 * App Usage Tracker — heartbeat-based real usage time tracking.
 *
 * Every 60 s the tracker POSTs elapsed seconds to the backend.
 * On failure the timestamp is NOT updated, so the next heartbeat
 * carries the accumulated time (capped at 120 s).
 */
import { request } from './request'
import { getTokens } from './storage'

const HEARTBEAT_INTERVAL_MS = 60_000
const MAX_SECONDS = 120

let intervalId = null
let lastReportedAt = 0

function sendHeartbeat() {
  const now = Date.now()
  const elapsed = Math.min(
    Math.round((now - lastReportedAt) / 1000),
    MAX_SECONDS
  )
  if (elapsed < 1) return

  request({
    url: '/api/usage/heartbeat',
    method: 'POST',
    data: { seconds: elapsed }
  })
    .then(() => {
      lastReportedAt = Date.now()
    })
    .catch(() => {
      // Keep lastReportedAt unchanged so next tick accumulates
    })
}

export function startTracking() {
  if (intervalId !== null) return // idempotent guard

  const tokens = getTokens()
  if (!tokens?.access_token) return // not logged in

  lastReportedAt = Date.now()
  intervalId = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS)
}

export function stopTracking() {
  if (intervalId === null) return

  clearInterval(intervalId)
  intervalId = null

  // Fire-and-forget final heartbeat
  const tokens = getTokens()
  if (!tokens?.access_token) return

  const now = Date.now()
  const elapsed = Math.min(
    Math.round((now - lastReportedAt) / 1000),
    MAX_SECONDS
  )
  if (elapsed >= 1) {
    request({
      url: '/api/usage/heartbeat',
      method: 'POST',
      data: { seconds: elapsed }
    }).catch(() => {})
  }
}

