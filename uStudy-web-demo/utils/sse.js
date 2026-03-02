/**
 * SSE (Server-Sent Events) streaming client for H5/Web
 * Uses fetch + ReadableStream
 */

import config from '@/config'
import { getTokens, clearAuth } from './storage'
import { ensureFreshToken } from './request'

const { API_BASE_URL } = config

/**
 * Parse SSE data chunks
 * @param {string} buffer - Accumulated data buffer
 * @param {string} pendingEvent - Event type carried over from previous chunk
 * @param {Function} onEvent - Event callback (eventType, data)
 * @returns {{ remaining: string, pendingEvent: string }}
 */
function parseSSEBuffer(buffer, pendingEvent, onEvent) {
  const lines = buffer.split('\n')
  const remaining = lines.pop()

  let currentEvent = pendingEvent

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

  return { remaining, pendingEvent: currentEvent }
}

/**
 * 检测是否为 401 Unauthorized 错误
 */
function is401Error(err) {
  if (!err) return false
  if (err.statusCode === 401 || err.status === 401) return true
  const msg = err.message || (typeof err === 'string' ? err : '')
  if (/\bHTTP\s+401\b/.test(msg)) return true
  return false
}

/**
 * SSE 连接内部实现
 * @param {Object} options - 连接选项
 * @param {string} [tokenOverride] - 重试时传入的新 token
 * @returns {Function} Cancel function
 */
function _connectSSEInner(options, tokenOverride) {
  const { url, method = 'POST', data, onEvent, onComplete, onConnectionError } = options

  const tokens = getTokens()
  const fullUrl = `${API_BASE_URL}${url}`
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  }

  const tokenToUse = tokenOverride || tokens?.access_token
  if (tokenToUse) {
    headers['Authorization'] = `Bearer ${tokenToUse}`
  }

  let aborted = false
  const abortController = new AbortController()

  const fetchOptions = {
    method,
    headers,
    signal: abortController.signal
  }
  if (method !== 'GET' && data !== undefined) {
    fetchOptions.body = JSON.stringify(data)
  }

  fetch(fullUrl, fetchOptions)
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => {
          throw new Error(`HTTP ${response.status}: ${text}`)
        })
      }

      if (!response.body) {
        return response.text().then(text => {
          parseSSEBuffer(text + '\n', 'message', onEvent)
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
      let pendingEvent = 'message'

      function read() {
        reader.read().then(({ done, value }) => {
          if (done || aborted) {
            if (!aborted) {
              onComplete?.()
            }
            return
          }

          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          const result = parseSSEBuffer(buffer, pendingEvent, onEvent)
          buffer = result.remaining
          pendingEvent = result.pendingEvent

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

/**
 * SSE 连接（含 401 自动刷新重试）
 * @param {Object} options
 * @param {string} options.url - API 路径
 * @param {string} [options.method='POST'] - HTTP 方法
 * @param {Object} options.data - 请求体
 * @param {Function} options.onEvent - SSE 事件回调
 * @param {Function} options.onComplete - 连接关闭回调
 * @param {Function} options.onConnectionError - 连接错误回调
 * @returns {Function} 取消函数
 */
export function connectSSE(options) {
  let aborted = false
  let currentAbort = null
  let retried = false

  const wrappedOptions = {
    ...options,
    onConnectionError: (err) => {
      if (aborted) return

      if (!retried && is401Error(err)) {
        retried = true
        console.log('[SSE] 401 detected, attempting token refresh...')

        ensureFreshToken()
          .then(newToken => {
            if (aborted) return
            console.log('[SSE] Token refreshed, retrying SSE connection...')
            currentAbort = _connectSSEInner(options, newToken)
          })
          .catch(refreshErr => {
            if (aborted) return
            console.error('[SSE] Token refresh failed, redirecting to login...')
            clearAuth()
            uni.reLaunch({ url: '/pages/login/login' })
            options.onConnectionError?.(refreshErr)
          })
        return
      }

      options.onConnectionError?.(err)
    }
  }

  currentAbort = _connectSSEInner(wrappedOptions)

  return () => {
    aborted = true
    currentAbort?.()
  }
}
