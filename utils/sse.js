/**
 * SSE (Server-Sent Events) streaming client for H5/Web
 * Uses fetch + ReadableStream
 */

import config from '@/config'
import { getTokens } from './storage'

const { API_BASE_URL } = config

/**
 * Parse SSE data chunks
 * @param {string} buffer - Accumulated data buffer
 * @param {Function} onEvent - Event callback (eventType, data)
 * @returns {string} Remaining incomplete data
 */
function parseSSEBuffer(buffer, onEvent) {
  const lines = buffer.split('\n')
  const remaining = lines.pop()

  let currentEvent = 'message'

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      try {
        const parsed = JSON.parse(line.slice(6))
        onEvent?.(currentEvent, parsed)
      } catch (e) {
        console.warn('[SSE] Parse error:', e, 'line:', line)
      }
      currentEvent = 'message'
    }
  }

  return remaining
}

/**
 * Connect to SSE endpoint via fetch + ReadableStream
 * @param {Object} options
 * @param {string} options.url - API path (appended to API_BASE_URL)
 * @param {string} [options.method='POST'] - HTTP method
 * @param {Object} options.data - Request body
 * @param {Function} options.onEvent - SSE event callback (eventType, data)
 * @param {Function} options.onComplete - Connection closed callback
 * @param {Function} options.onConnectionError - Connection error callback
 * @returns {Function} Cancel function
 */
export function connectSSE(options) {
  const { url, method = 'POST', data, onEvent, onComplete, onConnectionError } = options

  const tokens = getTokens()
  const fullUrl = `${API_BASE_URL}${url}`
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  }

  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`
  }

  let aborted = false
  const abortController = new AbortController()

  fetch(fullUrl, {
    method,
    headers,
    body: JSON.stringify(data),
    signal: abortController.signal
  })
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => {
          throw new Error(`HTTP ${response.status}: ${text}`)
        })
      }

      if (!response.body) {
        return response.text().then(text => {
          parseSSEBuffer(text + '\n', onEvent)
          onComplete?.()
          return null
        })
      }

      return response.body.getReader()
    })
    .then(reader => {
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      function read() {
        reader.read().then(({ done, value }) => {
          if (done || aborted) {
            onComplete?.()
            return
          }

          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          buffer = parseSSEBuffer(buffer, onEvent)

          read()
        }).catch(err => {
          if (!aborted) {
            onConnectionError?.(err)
          }
        })
      }

      read()
    })
    .catch(err => {
      if (!aborted) {
        onConnectionError?.(err)
        onComplete?.()
      }
    })

  return () => {
    aborted = true
    abortController.abort()
  }
}
