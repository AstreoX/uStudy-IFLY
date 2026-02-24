import { request } from '@/utils/request'
import { connectSSE } from '@/utils/sse'

/**
 * 获取可用模型列表
 * @returns {Promise<Object>} { models: [{ id, display_name, description, is_default }] }
 */
export function getModels() {
  return request({
    url: '/api/models',
    method: 'GET'
  })
}

/**
 * 创建对话
 * @param {string} spaceId - 学习空间 ID
 * @param {string} title - 对话标题
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
 * 获取空间内所有对话
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<Object>} { conversations: [], total: number }
 */
export function getSpaceConversations(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/conversations`,
    method: 'GET'
  })
}

/**
 * 获取对话详情（含历史消息）
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>} { conversation: {}, messages: [] }
 */
export function getConversation(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}`,
    method: 'GET'
  })
}

/**
 * 删除对话
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<void>}
 */
export function deleteConversation(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}`,
    method: 'DELETE'
  })
}

/**
 * 调试执行知识图谱工具调用
 * @param {string} spaceId - 学习空间 ID
 * @param {Object} toolCall - tool_call JSON（LLM 实际格式）
 * @returns {Promise<Object>} { raw_tool_output: string, parsed?: object }
 */
export function executeToolCall(spaceId, toolCall) {
  return request({
    url: `/api/spaces/${spaceId}/tools/execute`,
    method: 'POST',
    data: toolCall
  })
}

/**
 * 发送消息（SSE 流式）
 * @param {string} conversationId - 对话 ID
 * @param {string} content - 消息内容
 * @param {Object} callbacks - 事件回调
 *   - onTextDelta(content): 增量文本
 *   - onToolCall(toolData): 工具调用事件
 *   - onDone(fullContent): 完成事件
 *   - onError(message): 错误事件
 *   - onComplete(): 连接关闭
 * @param {Array<string>} attachmentIds - 附件ID列表（可选）
 * @returns {Function} 取消函数
 */
export function sendMessage(conversationId, content, callbacks, attachmentIds = null) {
  const requestData = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    requestData.attachment_ids = attachmentIds
  }

  return connectSSE({
    url: `/api/conversations/${conversationId}/messages`,
    method: 'POST',
    data: requestData,
    onEvent: (eventType, data) => {
      switch (eventType) {
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
          callbacks.onDone?.(data.content)
          break
        case 'error':
          callbacks.onError?.(data.message)
          break
      }
    },
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError: (err) => callbacks.onError?.(err.message || '连接失败')
  })
}

/**
 * 提交客户端工具执行结果
 * @param {string} conversationId - 对话 ID
 * @param {Object} data - 结果数据
 *   - tool_call_id: 工具调用 ID
 *   - success: 是否成功
 *   - result: 结果数据（可选）
 *   - error: 错误消息（可选）
 * @returns {Promise<Object>} { received, message }
 */
export function submitToolResult(conversationId, data) {
  return request({
    url: `/api/conversations/${conversationId}/tool-result`,
    method: 'POST',
    data
  })
}

// ==================== Quick Chat API ====================

/**
 * 创建快速对话（无学习空间绑定）
 * @param {string} title - 对话标题
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
 * 获取快速对话列表（space_id 为空的对话）
 * @returns {Promise<Object>} { conversations: [] }
 */
export function getQuickChatConversations() {
  return request({
    url: '/api/quick-chat/conversations',
    method: 'GET'
  })
}

/**
 * 更新对话（用于绑定到学习空间等）
 * @param {string} conversationId - 对话 ID
 * @param {Object} data - 更新数据 { space_id?: string, title?: string }
 * @returns {Promise<Object>} ConversationResponse
 */
export function updateConversation(conversationId, data) {
  return request({
    url: `/api/conversations/${conversationId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 发送快速对话消息（SSE 流式）
 * @param {string} conversationId - 对话 ID
 * @param {string} content - 消息内容
 * @param {Object} callbacks - 事件回调
 *   - onTextDelta(content): 增量文本
 *   - onToolCall(toolData): 工具调用事件
 *   - onDone(fullContent): 完成事件
 *   - onError(message): 错误事件
 *   - onComplete(): 连接关闭
 * @param {Array<string>} attachmentIds - 附件ID列表（可选）
 * @returns {Function} 取消函数
 */
export function sendQuickChatMessage(conversationId, content, callbacks, attachmentIds = null) {
  const requestData = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    requestData.attachment_ids = attachmentIds
  }

  return connectSSE({
    url: `/api/quick-chat/conversations/${conversationId}/messages`,
    method: 'POST',
    data: requestData,
    onEvent: (eventType, data) => {
      switch (eventType) {
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
          callbacks.onDone?.(data.content)
          break
        case 'error':
          callbacks.onError?.(data.message)
          break
      }
    },
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError: (err) => callbacks.onError?.(err.message || '连接失败')
  })
}

/**
 * 确认或拒绝工具执行
 * @param {string} conversationId - 对话 ID
 * @param {string} toolCallId - 工具调用 ID
 * @param {Object} data - 确认数据
 *   - tool_name: 工具名称
 *   - arguments: 工具参数
 *   - confirmed: 是否确认执行
 * @returns {Promise<Object>} { status, success, data, message }
 */
export function confirmToolExecution(conversationId, toolCallId, data) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/confirm`,
    method: 'POST',
    data
  })
}

// ==================== Feedback API ====================

/**
 * Submit user feedback for an AI response
 * @param {Object} feedbackData - Feedback data
 * @param {string} feedbackData.conversation_id - Conversation ID (may be null)
 * @param {string} feedbackData.message_id - The AI message ID that triggered feedback (optional)
 * @param {string} feedbackData.chat_mode - 'quick_chat' or 'space_chat'
 * @param {string} feedbackData.space_name - Learning space name (if space_chat mode)
 * @param {string} feedbackData.feedback_content - User's feedback text
 * @param {Array} feedbackData.conversation_history - Complete conversation data with timestamps
 * @returns {Promise<Object>} { success: boolean, message: string }
 */
export function submitFeedback(feedbackData) {
  return request({
    url: '/api/feedback/submit',
    method: 'POST',
    data: feedbackData
  })
}
