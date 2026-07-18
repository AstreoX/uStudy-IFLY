import { request } from '@/utils/request'
import { connectSSE } from '@/utils/sse'
import config from '@/config'
import { getTokens } from '@/utils/storage'

/**
 * Get available models list
 * @returns {Promise<Object>} { models: [{ id, display_name, description, is_default }] }
 */
export function getModels() {
  return request({
    url: '/api/models',
    method: 'GET'
  })
}

/**
 * Create a conversation
 * @param {string} spaceId - Learning space ID
 * @param {string} title - Conversation title
 * @returns {Promise<Object>} ConversationResponse
 */
export function createConversation(spaceId, title) {
  return request({
    url: `/api/spaces/${spaceId}/conversations`,
    method: 'POST',
    data: { title }
  })
}

/**
 * Get all conversations in a space
 * @param {string} spaceId - Learning space ID
 * @returns {Promise<Object>} { conversations: [], total: number }
 */
export function getSpaceConversations(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/conversations`,
    method: 'GET'
  })
}

/**
 * Get conversation detail with message history
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} { conversation: {}, messages: [] }
 */
export function getConversation(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}`,
    method: 'GET'
  })
}

/**
 * Upload an attachment file
 * @param {File} file - File to upload
 * @returns {Promise<Object>} { success, attachment, message }
 */
export async function uploadAttachment(file) {
  const tokens = getTokens()
  const token = tokens?.access_token
  if (!token) throw new Error('登录已过期，请重新登录')

  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${config.API_BASE_URL}/api/attachments/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData
  })

  if (!response.ok) {
    let message = '上传失败'
    try {
      const err = await response.json()
      message = err?.detail || err?.message || message
    } catch {}
    throw new Error(message)
  }
  return response.json()
}

/**
 * Delete an orphan attachment
 * @param {string} attachmentId
 * @returns {Promise<Object>}
 */
export function deleteAttachment(attachmentId) {
  return request({
    url: `/api/attachments/${attachmentId}`,
    method: 'DELETE'
  })
}

/**
 * Parse quota error from SSE connection error message
 */
function parseQuotaError(errMessage) {
  const match = errMessage?.match(/^HTTP (\d+): (.+)$/s)
  if (!match) return null
  const statusCode = parseInt(match[1])
  if (statusCode !== 429 && statusCode !== 403) return null
  try {
    const body = JSON.parse(match[2])
    if (body.detail?.code || body.code) {
      const detail = body.detail || body
      return { statusCode, code: detail.code, message: detail.message || errMessage }
    }
  } catch {}
  return null
}

// ==================== Quick Chat API ====================

/**
 * Create a quick chat conversation (no learning space)
 * @param {string} title - Conversation title
 * @returns {Promise<Object>} ConversationResponse
 */
export function createQuickChatConversation(title) {
  return request({
    url: '/api/quick-chat/conversations',
    method: 'POST',
    data: { title }
  })
}

/**
 * Get quick chat conversations
 * @returns {Promise<Object>} { conversations: [] }
 */
export function getQuickChatConversations() {
  return request({
    url: '/api/quick-chat/conversations',
    method: 'GET'
  })
}

/**
 * Send a quick chat message (SSE streaming)
 * @param {string} conversationId - Conversation ID
 * @param {string} content - Message content
 * @param {Object} callbacks - Event callbacks
 * @param {Array<string>} attachmentIds - Attachment IDs (optional)
 * @returns {Function} Cancel function
 */
export function sendQuickChatMessage(conversationId, content, callbacks, attachmentIds = null, modelId = null) {
  const data = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    data.attachment_ids = attachmentIds
  }
  if (modelId) {
    data.model_id = modelId
  }
  return connectSSE({
    url: `/api/quick-chat/conversations/${conversationId}/messages`,
    method: 'POST',
    data,
    onEvent: (eventType, data) => {
      console.log('[QuickChat SSE]', eventType, Object.keys(data))
      switch (eventType) {
        case 'thinking_delta':
          callbacks.onThinkingDelta?.(data.content)
          break
        case 'text_delta':
          callbacks.onTextDelta?.(data.content)
          break
        case 'tool_call':
          callbacks.onToolCall?.(data)
          break
        case 'client_tool_request':
          callbacks.onClientToolRequest?.(data)
          break
        case 'done':
          callbacks.onDone?.(data.content, data.citations)
          break
        case 'error':
          callbacks.onError?.(data.message)
          break
      }
    },
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError: (err) => {
      const quotaErr = parseQuotaError(err.message || String(err))
      if (quotaErr) {
        callbacks.onQuotaError?.(quotaErr)
        if (!callbacks.onQuotaError) callbacks.onError?.(quotaErr.message)
      } else {
        callbacks.onError?.(err.message || 'Connection failed')
      }
    }
  })
}

/**
 * Confirm or reject a tool execution
 * @param {string} conversationId - Conversation ID
 * @param {string} toolCallId - Tool call ID
 * @param {Object} data - { tool_name, arguments, confirmed }
 * @returns {Promise<Object>}
 */
export function confirmToolExecution(conversationId, toolCallId, data) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/confirm`,
    method: 'POST',
    data
  })
}

/**
 * Get async quick-chat tool task status
 * @param {string} conversationId - Conversation ID
 * @param {string} toolCallId - Tool call ID
 * @returns {Promise<Object>}
 */
export function getQuickChatToolTaskStatus(conversationId, toolCallId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/status`,
    method: 'GET'
  })
}

/**
 * List async quick-chat tool tasks for recovery
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>}
 */
export function listQuickChatToolTasks(conversationId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/tasks`,
    method: 'GET'
  })
}

/**
 * Bind quick-chat async create-space task after KG is done
 * @param {string} conversationId - Conversation ID
 * @param {string} toolCallId - Tool call ID
 * @returns {Promise<Object>}
 */
export function bindQuickChatToolTask(conversationId, toolCallId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/bind`,
    method: 'POST'
  })
}

export function sendMessage(conversationId, content, callbacks, attachmentIds = null, modelId = null, panelScreenshot = null) {
  const data = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    data.attachment_ids = attachmentIds
  }
  if (modelId) {
    data.model_id = modelId
  }
  if (panelScreenshot) {
    data.panel_screenshot = panelScreenshot
  }
  return connectSSE({
    url: `/api/conversations/${conversationId}/messages`,
    method: 'POST',
    data,
    onEvent: (eventType, data) => {
      switch (eventType) {
        case 'thinking_delta':
          callbacks.onThinkingDelta?.(data.content)
          break
        case 'text_delta':
          callbacks.onTextDelta?.(data.content)
          break
        case 'tool_call':
          callbacks.onToolCall?.(data)
          break
        case 'client_tool_request':
          callbacks.onClientToolRequest?.(data)
          break
        case 'done':
          callbacks.onDone?.(data.content, data.citations)
          break
        case 'error':
          callbacks.onError?.(data.message)
          break
      }
    },
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError: (err) => {
      const quotaErr = parseQuotaError(err.message || String(err))
      if (quotaErr) {
        callbacks.onQuotaError?.(quotaErr)
        if (!callbacks.onQuotaError) callbacks.onError?.(quotaErr.message)
      } else {
        callbacks.onError?.(err.message || 'Connection failed')
      }
    }
  })
}

export function submitToolResult(conversationId, data) {
  return request({
    url: `/api/conversations/${conversationId}/tool-result`,
    method: 'POST',
    data
  })
}
