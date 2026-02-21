import { request } from '@/utils/request'
import { connectSSE } from '@/utils/sse'

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
 * Send message via SSE streaming
 * @param {string} conversationId - Conversation ID
 * @param {string} content - Message content
 * @param {Object} callbacks - Event callbacks
 *   - onTextDelta(content): Incremental text
 *   - onToolCall(toolData): Tool call event
 *   - onDone(fullContent): Completion event
 *   - onError(message): Error event
 *   - onComplete(): Connection closed
 * @returns {Function} Cancel function
 */
export function sendMessage(conversationId, content, callbacks) {
  return connectSSE({
    url: `/api/conversations/${conversationId}/messages`,
    method: 'POST',
    data: { content },
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
