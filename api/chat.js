import { request } from '@/utils/request'
import { connectSSE } from '@/utils/sse'
import config from '@/config'
import { getTokens } from '@/utils/storage'

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

export function sendMessage(conversationId, content, callbacks, attachmentIds = null) {
  const data = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    data.attachment_ids = attachmentIds
  }
  return connectSSE({
    url: `/api/conversations/${conversationId}/messages`,
    method: 'POST',
    data,
    onEvent: (eventType, data) => {
      switch (eventType) {
        case 'text_delta':
          callbacks.onTextDelta?.(data.content)
          break
        case 'tool_call':
          callbacks.onToolCall?.(data)
          break
        case 'done':
          callbacks.onDone?.(data.content)
          break
        case 'error':
          callbacks.onError?.(data.message)
          break
      }
    },
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError: (err) => callbacks.onError?.(err.message || 'Connection failed')
  })
}
