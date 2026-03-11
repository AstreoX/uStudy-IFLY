/**
 * SSE (Server-Sent Events) 跨平台连接工具
 *
 * H5: 使用 fetch + ReadableStream
 * App-Android: 使用 renderjs + fetch (在 WebView 渲染层直接使用浏览器原生 API)
 * App-iOS: 使用 uni.request + onChunkReceived
 * 小程序: 使用 uni.request (无流式，完整响应后解析)
 */

import config from '@/config'
import { getTokens, clearAuth } from './storage'
import { ensureFreshToken } from './request'

const { API_BASE_URL } = config

// ==================== Renderjs 事件总线 (Android) ====================

/** @type {Object|null} renderjs 组件引用 */
let sseEventBus = null

/** @type {Object<number, { onEvent, onComplete, onError }>} 按 requestId 注册的回调 */
const sseCallbacks = {}

/**
 * 注册 renderjs 组件实例作为事件总线
 * 在页面 mounted 时调用
 */
export function setSseEventBus(bus) {
  sseEventBus = bus
}

/**
 * 清除事件总线引用
 * 在页面 beforeDestroy 时调用
 */
export function clearSseEventBus() {
  sseEventBus = null
}

/**
 * 处理 renderjs 传回的批量 SSE 事件
 */
export function handleSseEvents(eventData) {
  const { requestId, events } = eventData
  const callbacks = sseCallbacks[requestId]
  if (callbacks?.onEvent) {
    for (const evt of events) {
      callbacks.onEvent(evt.eventType, evt.data)
      if (evt.eventType === 'done') {
        callbacks._doneReceived = true
      }
    }
  }
}

/**
 * 处理 renderjs 传回的完成信号（含 doneEventData 冗余投递）
 */
export function handleSseComplete(eventData) {
  const { requestId, finalEvents, doneEventData } = eventData
  const callbacks = sseCallbacks[requestId]
  if (!callbacks) return

  if (finalEvents?.length > 0 && callbacks.onEvent) {
    for (const evt of finalEvents) {
      callbacks.onEvent(evt.eventType, evt.data)
      if (evt.eventType === 'done') {
        callbacks._doneReceived = true
      }
    }
  }

  // 安全兜底：如果 done 事件未通过常规 events 到达，从 doneEventData 重播
  if (!callbacks._doneReceived && doneEventData && callbacks.onEvent) {
    console.warn('[SSE] Done event missed in regular events, replaying from completion payload')
    callbacks.onEvent('done', doneEventData)
  }

  callbacks.onComplete?.()
  delete sseCallbacks[requestId]
}

/**
 * 处理 renderjs 传回的错误
 */
export function handleSseError(eventData) {
  const { requestId, error } = eventData
  const callbacks = sseCallbacks[requestId]
  if (callbacks?.onError) {
    callbacks.onError(new Error(error))
  }
  delete sseCallbacks[requestId]
}

/**
 * 解析 SSE 数据块
 * @param {string} buffer - 累积的数据缓冲区
 * @param {string} pendingEvent - 上一次调用遗留的事件类型
 * @param {Function} onEvent - 事件回调 (eventType, data)
 * @returns {{ remaining: string, pendingEvent: string }}
 */
function parseSSEBuffer(buffer, pendingEvent, onEvent) {
  const lines = buffer.split('\n')
  const remaining = lines.pop() // 保留不完整的行

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
 * 将完整 SSE 响应文本解析为事件数组
 * @param {string} text
 * @returns {Array<{ eventType: string, data: any }>}
 */
function collectSSEEvents(text) {
  const events = []
  parseSSEBuffer(text, 'message', (eventType, data) => {
    events.push({ eventType, data })
  })
  return events
}

/**
 * 在无真分块能力时，按小间隔回放事件，模拟流式输出
 */
function replayEventsGradually(events, onEvent, onDone, isAborted) {
  if (!events || events.length === 0) {
    onDone?.()
    return []
  }

  let delay = 0
  const timerIds = []

  events.forEach((evt, index) => {
    const step = (evt.eventType === 'text_delta' || evt.eventType === 'thinking_delta') ? 24 : 0
    delay += step

    const timerId = setTimeout(() => {
      if (isAborted()) return
      onEvent?.(evt.eventType, evt.data)
      if (index === events.length - 1) {
        onDone?.()
      }
    }, delay)
    timerIds.push(timerId)
  })

  return timerIds
}

/**
 * 检测是否为 Android 平台
 */
function isAndroidPlatform() {
  try {
    const info = uni.getSystemInfoSync()
    return (info.platform || '').toLowerCase() === 'android'
  } catch (e) {
    return false
  }
}

/**
 * 检测是否为 401 Unauthorized 错误
 * 需匹配各平台的不同错误格式
 */
function is401Error(err) {
  if (!err) return false
  if (err.statusCode === 401 || err.status === 401) return true
  const msg = err.message || (typeof err === 'string' ? err : '')
  if (/\bHTTP\s+401\b/.test(msg)) return true
  return false
}

/**
 * H5 平台 SSE 实现
 */
function connectSSE_H5(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError) {
  let aborted = false
  const abortController = new AbortController()

  console.log('[SSE-H5] Starting fetch...')

  fetch(fullUrl, {
    method,
    headers,
    body: JSON.stringify(data),
    signal: abortController.signal
  })
    .then(response => {
      console.log('[SSE-H5] Response:', response.status, response.statusText)

      if (!response.ok) {
        return response.text().then(text => {
          throw new Error(`HTTP ${response.status}: ${text}`)
        })
      }

      // 检查是否支持 ReadableStream
      if (!response.body) {
        console.warn('[SSE-H5] ReadableStream not supported, using text fallback')
        return response.text().then(text => {
          console.log('[SSE-H5] Full response length:', text.length)
          parseSSEBuffer(text + '\n', 'message', onEvent)
          onComplete?.()
          return null
        })
      }

      console.log('[SSE-H5] Using ReadableStream')
      return response.body.getReader()
    })
    .then(reader => {
      if (!reader) return // Fallback 已处理

      const decoder = new TextDecoder()
      let buffer = ''
      let pendingEvent = 'message'

      function read() {
        reader.read().then(({ done, value }) => {
          if (done || aborted) {
            console.log('[SSE-H5] Stream ended')
            if (!aborted) {
              onComplete?.()
            }
            return
          }

          const chunk = decoder.decode(value, { stream: true })
          console.log('[SSE-H5] Chunk received:', chunk.length, 'bytes')
          buffer += chunk
          const result = parseSSEBuffer(buffer, pendingEvent, onEvent)
          buffer = result.remaining
          pendingEvent = result.pendingEvent

          read()
        }).catch(err => {
          if (!aborted) {
            console.error('[SSE-H5] Read error:', err)
            onConnectionError?.(err)
          }
        })
      }

      read()
    })
    .catch(err => {
      if (!aborted) {
        console.error('[SSE-H5] Connection error:', err)
        onConnectionError?.(err)
      }
    })

  return () => {
    console.log('[SSE-H5] Aborting')
    aborted = true
    abortController.abort()
  }
}

/**
 * Android 平台 SSE 实现 (使用 plus.net.XMLHttpRequest)
 * plus.net.XMLHttpRequest 支持 onprogress 事件，可实现真正的流式响应
 */
function connectSSE_Android(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError) {
  let aborted = false
  let buffer = ''
  let pendingEvent = 'message'
  let lastProcessedLength = 0
  let xhr = null

  console.log('[SSE-Android] Starting plus.net.XMLHttpRequest...')

  // 清理函数，防止内存泄漏
  const cleanup = () => {
    if (xhr) {
      xhr.onprogress = null
      xhr.onload = null
      xhr.onerror = null
      xhr.ontimeout = null
      xhr = null
    }
  }

  xhr = new plus.net.XMLHttpRequest()
  xhr.timeout = 120000 // 2分钟超时

  xhr.onprogress = function(e) {
    if (aborted || !xhr) return

    try {
      const responseText = xhr.responseText
      // 校验 responseText 有效性
      if (typeof responseText !== 'string' || responseText.length <= lastProcessedLength) {
        return
      }

      const newData = responseText.substring(lastProcessedLength)
      lastProcessedLength = responseText.length

      if (newData) {
        console.log('[SSE-Android] Progress chunk:', newData.length, 'bytes')
        buffer += newData
        const result = parseSSEBuffer(buffer, pendingEvent, onEvent)
        buffer = result.remaining
        pendingEvent = result.pendingEvent
      }
    } catch (e) {
      console.warn('[SSE-Android] Progress parse error:', e)
    }
  }

  xhr.onload = function() {
    if (aborted) {
      cleanup()
      return
    }

    console.log('[SSE-Android] Request completed, status:', xhr?.status)

    if (xhr && xhr.status >= 200 && xhr.status < 300) {
      // 处理缓冲区中剩余的数据
      if (buffer) {
        parseSSEBuffer(buffer + '\n', pendingEvent, onEvent)
      }
      onComplete?.()
    } else {
      onConnectionError?.(new Error(`HTTP ${xhr?.status}: ${xhr?.statusText}`))
    }
    cleanup()
  }

  xhr.onerror = function(e) {
    if (!aborted) {
      console.error('[SSE-Android] Request error:', e)
      onConnectionError?.(e)
    }
    cleanup()
  }

  xhr.ontimeout = function() {
    if (!aborted) {
      console.error('[SSE-Android] Request timeout')
      onConnectionError?.(new Error('Request timeout'))
    }
    cleanup()
  }

  // 配置请求
  xhr.open(method.toUpperCase(), fullUrl)

  // 设置请求头
  Object.keys(headers).forEach(key => {
    xhr.setRequestHeader(key, headers[key])
  })

  // 发送请求
  xhr.send(JSON.stringify(data))

  // 返回取消函数
  return () => {
    console.log('[SSE-Android] Aborting')
    aborted = true
    try {
      xhr?.abort()
    } catch (e) {
      console.warn('[SSE-Android] Abort error:', e)
    }
    cleanup()
  }
}

/**
 * App 平台 SSE 实现
 * Android + renderjs: 使用 renderjs + fetch (浏览器原生流式读取)
 * Android (fallback): 使用 plus.net.XMLHttpRequest + onprogress
 * iOS: 使用 uni.request + onChunkReceived
 */
function connectSSE_App(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError) {
  // Android + renderjs 可用: 使用 renderjs 实现真正的流式响应
  if (isAndroidPlatform() && sseEventBus) {
    console.log('[SSE-App] Detected Android, using renderjs fetch')

    const requestId = sseEventBus.startSSE({
      url: fullUrl,
      method,
      headers,
      data
    })

    sseCallbacks[requestId] = {
      onEvent,
      onComplete,
      onError: onConnectionError
    }

    return () => {
      console.log('[SSE-App] Aborting renderjs request:', requestId)
      sseEventBus?.abortSSE(requestId)
      delete sseCallbacks[requestId]
    }
  }

  // Android fallback: 使用 plus.net.XMLHttpRequest
  if (isAndroidPlatform() && typeof plus !== 'undefined' && plus.net && plus.net.XMLHttpRequest) {
    console.log('[SSE-App] Detected Android, falling back to plus.net.XMLHttpRequest')
    return connectSSE_Android(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError)
  }

  // iOS 和其他平台: 保持现有 uni.request 实现
  let aborted = false
  let buffer = ''
  let pendingEvent = 'message'
  let chunksReceived = 0
  let replayTimerIds = []

  console.log('[SSE-App] Starting request...')

  const requestTask = uni.request({
    url: fullUrl,
    method: method.toUpperCase(),
    header: headers,
    data,
    enableChunked: true,
    success: (res) => {
      console.log('[SSE-App] Request completed, status:', res.statusCode, 'chunks:', chunksReceived)

      // HTTP error (e.g. 401) — uni.request routes these to success, not fail
      if (res.statusCode < 200 || res.statusCode >= 300) {
        if (!aborted) {
          onConnectionError?.(new Error(`HTTP ${res.statusCode}: ${typeof res.data === 'string' ? res.data : JSON.stringify(res.data)}`))
        }
        return
      }

      // 如果没有收到分块数据，尝试从完整响应解析
      if (chunksReceived === 0 && res.data) {
        console.log('[SSE-App] No chunks received, replaying parsed events gradually')
        const responseText = typeof res.data === 'string' ? res.data : JSON.stringify(res.data)
        const events = collectSSEEvents(responseText + '\n')
        replayTimerIds = replayEventsGradually(
          events,
          onEvent,
          onComplete,
          () => aborted
        )
        return
      }

      onComplete?.()
    },
    fail: (err) => {
      if (!aborted) {
        console.error('[SSE-App] Request failed:', JSON.stringify(err))
        onConnectionError?.(err)
      }
    }
  })

  // 监听分块数据
  if (requestTask && typeof requestTask.onChunkReceived === 'function') {
    console.log('[SSE-App] onChunkReceived available')

    requestTask.onChunkReceived((res) => {
      if (aborted) return
      chunksReceived++

      try {
        let chunk
        if (typeof TextDecoder !== 'undefined') {
          chunk = new TextDecoder('utf-8').decode(new Uint8Array(res.data))
        } else {
          // Fallback
          const arr = new Uint8Array(res.data)
          chunk = Array.from(arr).map(b => String.fromCharCode(b)).join('')
        }

        console.log('[SSE-App] Chunk #' + chunksReceived + ':', chunk.length, 'bytes')
        buffer += chunk
        const result = parseSSEBuffer(buffer, pendingEvent, onEvent)
        buffer = result.remaining
        pendingEvent = result.pendingEvent
      } catch (e) {
        console.warn('[SSE-App] Chunk parse error:', e)
      }
    })
  } else {
    console.warn('[SSE-App] onChunkReceived NOT available - using gradual replay fallback')
  }

  return () => {
    console.log('[SSE-App] Aborting')
    aborted = true
    if (replayTimerIds.length > 0) {
      replayTimerIds.forEach((id) => clearTimeout(id))
      replayTimerIds = []
    }
    requestTask?.abort()
  }
}

/**
 * 跨平台 SSE 连接（内部实现）
 * @param {Object} options - 连接选项
 * @param {string} [tokenOverride] - 重试时传入的新 token
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

  console.log('[SSE] ===== New Connection =====')
  console.log('[SSE] URL:', fullUrl)
  console.log('[SSE] Has token:', !!tokenToUse)

  // #ifdef H5
  console.log('[SSE] Platform: H5')
  return connectSSE_H5(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError)
  // #endif

  // #ifdef APP-PLUS
  console.log('[SSE] Platform: APP-PLUS')
  return connectSSE_App(fullUrl, method, headers, data, onEvent, onComplete, onConnectionError)
  // #endif

  // #ifdef MP
  console.log('[SSE] Platform: Mini Program (no streaming)')

  uni.request({
    url: fullUrl,
    method: method.toUpperCase(),
    header: headers,
    data,
    success: (res) => {
      console.log('[SSE-MP] Response:', res.statusCode)
      if (res.statusCode < 200 || res.statusCode >= 300) {
        onConnectionError?.(new Error(`HTTP ${res.statusCode}: ${typeof res.data === 'string' ? res.data : JSON.stringify(res.data)}`))
        return
      }
      if (typeof res.data === 'string') {
        parseSSEBuffer(res.data + '\n', 'message', onEvent)
      }
      onComplete?.()
    },
    fail: (err) => {
      console.error('[SSE-MP] Failed:', err)
      onConnectionError?.(err)
    }
  })

  return () => {}
  // #endif
}

/**
 * 跨平台 SSE 连接（含 401 自动刷新重试）
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
  let retryPending = false

  const wrappedOptions = {
    ...options,
    onConnectionError: (err) => {
      if (aborted) return

      if (!retried && is401Error(err)) {
        retried = true
        retryPending = true
        console.log('[SSE] 401 detected, attempting token refresh...')

        ensureFreshToken()
          .then(newToken => {
            if (aborted) return
            retryPending = false
            console.log('[SSE] Token refreshed, retrying SSE connection...')
            currentAbort = _connectSSEInner(wrappedOptions, newToken)
          })
          .catch(refreshErr => {
            retryPending = false
            if (aborted) return
            console.error('[SSE] Token refresh failed, redirecting to login...')
            clearAuth()
            uni.reLaunch({ url: '/pages/login/login' })
            options.onConnectionError?.(refreshErr)
            options.onComplete?.()
          })
        return
      }

      options.onConnectionError?.(err)
    },
    onComplete: () => {
      if (retryPending) return
      options.onComplete?.()
    }
  }

  currentAbort = _connectSSEInner(wrappedOptions)

  return () => {
    aborted = true
    currentAbort?.()
  }
}

// ==================== 断点续传配置 ====================

const DEFAULT_RECONNECT_CONFIG = {
  enabled: true,
  maxAttempts: 3,
  initialDelay: 1000,
  backoffMultiplier: 2,
  maxDelay: 10000,
}

/**
 * 简单的 sleep 函数
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * 带断点续传的 SSE 连接
 *
 * 在普通 SSE 连接基础上，增加自动重连和断点续传能力：
 * 1. 断连后自动尝试重连（指数退避）
 * 2. 调用后端 API 查询流式状态
 * 3. 如果仍在流式传输，从断点继续接收
 *
 * @param {Object} options
 * @param {string} options.url - SSE 请求路径
 * @param {string} options.conversationId - 对话 ID，用于查询状态和断点续传
 * @param {string} [options.method='POST'] - HTTP 方法
 * @param {Object} options.data - 请求体
 * @param {Function} options.onEvent - SSE 事件回调 (eventType, data)
 * @param {Function} [options.onComplete] - 连接正常关闭回调
 * @param {Function} [options.onConnectionError] - 连接错误回调
 * @param {Function} [options.onReconnecting] - 正在重连回调 (attempt)
 * @param {Function} [options.onReconnected] - 重连成功回调
 * @param {Object} [options.reconnect] - 重连配置
 * @param {Function} [options.getStreamingStatus] - 获取流式状态的函数 (conversationId) => Promise
 * @returns {Function} 取消函数
 */
export function connectSSEWithResume(options) {
  const {
    url,
    conversationId,
    method = 'POST',
    data,
    onEvent,
    onComplete,
    onConnectionError,
    onReconnecting,
    onReconnected,
    reconnect = DEFAULT_RECONNECT_CONFIG,
    getStreamingStatus,
  } = options

  let receivedContentLength = 0  // 已接收的文本字符数
  let reconnectAttempts = 0
  let aborted = false
  let currentCancel = null
  let doneReceived = false

  // 包装 onEvent，跟踪接收进度
  const wrappedOnEvent = (eventType, eventData) => {
    if (eventType === 'text_delta' && eventData?.content) {
      receivedContentLength += eventData.content.length
    }
    if (eventType === 'done') {
      doneReceived = true
    }
    onEvent?.(eventType, eventData)
  }

  // 异常断连处理
  const handleDisconnect = async () => {
    if (aborted || doneReceived) {
      onComplete?.()
      return
    }

    // 检查是否需要重连
    if (!reconnect.enabled || reconnectAttempts >= reconnect.maxAttempts) {
      console.warn('[SSE-Resume] Max reconnect attempts reached or reconnect disabled')
      onConnectionError?.(new Error('连接中断，请刷新重试'))
      onComplete?.()
      return
    }

    reconnectAttempts++
    const delay = Math.min(
      reconnect.initialDelay * Math.pow(reconnect.backoffMultiplier, reconnectAttempts - 1),
      reconnect.maxDelay
    )

    console.log(`[SSE-Resume] Attempting reconnect ${reconnectAttempts}/${reconnect.maxAttempts} in ${delay}ms`)
    onReconnecting?.(reconnectAttempts)

    await sleep(delay)

    if (aborted) {
      return
    }

    // 查询流式状态
    if (!getStreamingStatus) {
      console.warn('[SSE-Resume] No getStreamingStatus function provided, cannot resume')
      onConnectionError?.(new Error('无法恢复连接'))
      onComplete?.()
      return
    }

    try {
      const status = await getStreamingStatus(conversationId)
      console.log('[SSE-Resume] Streaming status:', status)

      if (aborted) {
        return
      }

      if (!status.is_streaming) {
        // 流式已完成
        if (status.partial_content) {
          // 补发剩余内容
          const alreadyReceived = receivedContentLength
          if (status.partial_content.length > alreadyReceived) {
            const remaining = status.partial_content.slice(alreadyReceived)
            onEvent?.('text_delta', { content: remaining })
          }
          onEvent?.('done', { content: status.partial_content, resumed: true })
        } else {
          onEvent?.('done', { content: '', resumed: true, cache_expired: true })
        }
        onReconnected?.()
        onComplete?.()
        return
      }

      // 仍在流式传输，从断点继续
      console.log(`[SSE-Resume] Resuming from offset ${receivedContentLength}`)
      currentCancel = connectSSE({
        url: url.replace(/\/messages$/, `/resume-stream?offset=${receivedContentLength}`),
        method: 'GET',
        data: null,
        onEvent: wrappedOnEvent,
        onComplete: () => {
          if (!doneReceived && !aborted) {
            // 断连了但没收到 done，继续尝试重连
            handleDisconnect()
          } else {
            reconnectAttempts = 0
            onReconnected?.()
            onComplete?.()
          }
        },
        onConnectionError: (err) => {
          console.error('[SSE-Resume] Resume connection error:', err)
          handleDisconnect()
        },
      })
    } catch (err) {
      console.error('[SSE-Resume] Failed to get streaming status:', err)
      handleDisconnect()
    }
  }

  // 初始连接
  currentCancel = connectSSE({
    url,
    method,
    data,
    onEvent: wrappedOnEvent,
    onComplete: () => {
      if (!doneReceived && !aborted) {
        // 连接断开但没收到 done 事件，触发重连
        console.log('[SSE-Resume] Connection closed without done event, attempting reconnect')
        handleDisconnect()
      } else {
        onComplete?.()
      }
    },
    onConnectionError: (err) => {
      console.error('[SSE-Resume] Initial connection error:', err)
      // 401 等错误由 connectSSE 内部处理，其他错误尝试重连
      if (!is401Error(err)) {
        handleDisconnect()
      } else {
        onConnectionError?.(err)
      }
    },
  })

  // 返回取消函数
  return () => {
    aborted = true
    currentCancel?.()
  }
}
