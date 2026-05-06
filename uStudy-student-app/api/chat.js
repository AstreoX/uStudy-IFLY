import { request } from '@/utils/request'
import { connectSSE, connectSSEWithResume } from '@/utils/sse'

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
 * 获取对话级 Agent Todo 列表
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>} { todos: [] }
 */
export function getConversationTodos(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}/todos`,
    method: 'GET'
  })
}

/**
 * 更新对话级 Agent Todo 完成状态
 * @param {string} conversationId - 对话 ID
 * @param {string} taskId - todo task_id
 * @param {boolean} completed - 目标完成状态
 * @returns {Promise<Object>} { todos: [] }
 */
export function updateConversationTodoStatus(conversationId, taskId, completed) {
  return request({
    url: `/api/conversations/${conversationId}/todos/${encodeURIComponent(taskId)}`,
    method: 'PATCH',
    data: { completed }
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
 * 解析配额错误（从 SSE 连接错误中提取配额相关信息）
 */
function parseQuotaError(errMessage) {
  const match = errMessage?.match(/^HTTP (\d+): (.+)$/s)
  if (!match) return null
  const statusCode = parseInt(match[1])
  if (statusCode !== 429 && statusCode !== 403 && statusCode !== 402) return null
  try {
    const body = JSON.parse(match[2])
    if (body.detail?.code || body.code) {
      const detail = body.detail || body
      return { statusCode, code: detail.code, message: detail.message || errMessage }
    }
  } catch {}
  return null
}

/**
 * 发送消息（SSE 流式）
 * @param {string} conversationId - 对话 ID
 * @param {string} content - 消息内容
 * @param {Object} callbacks - 事件回调
 *   - onTextDelta(content): 增量文本
 *   - onThinking(content): 思考过程增量内容（reasoning 模型）
 *   - onToolCall(toolData): 工具调用事件
 *   - onDone(fullContent, citations, rawData): 完成事件
 *   - onError(message): 错误事件
 *   - onQuotaError(info): 配额超限错误事件
 *   - onComplete(): 连接关闭
 *   - onReconnecting(attempt): 正在重连（仅 enableResume=true 时）
 *   - onReconnected(): 重连成功（仅 enableResume=true 时）
 * @param {Array<string>} attachmentIds - 附件ID列表（可选）
 * @param {string} modelId - 模型 ID（可选）
 * @param {Object} options - 额外选项
 *   - enableResume: boolean - 是否启用断点续传（默认 true）
 * @returns {Function} 取消函数
 */
export function sendMessage(conversationId, content, callbacks, attachmentIds = null, modelId = null, options = {}) {
  const { enableResume = true, thinking = null } = options

  const requestData = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    requestData.attachment_ids = attachmentIds
  }
  if (modelId) {
    requestData.model_id = modelId
  }
  if (thinking !== null) {
    requestData.thinking = thinking
  }

  const onEvent = (eventType, data) => {
    switch (eventType) {
      case 'text_delta':
        callbacks.onTextDelta?.(data.content)
        break
      case 'thinking_delta':
        callbacks.onThinking?.(data.content)
        break
      case 'tool_call':
        callbacks.onToolCall?.(data)
        break
      case 'client_tool_request':
        callbacks.onClientToolRequest?.(data)
        break
      case 'title':
        callbacks.onTitle?.(data.title)
        break
      case 'done':
        callbacks.onDone?.(data.content, data.citations, data)
        break
      case 'error':
        callbacks.onError?.(data.message)
        break
    }
  }

  const onConnectionError = (err) => {
    const quotaErr = parseQuotaError(err.message || String(err))
    if (quotaErr) {
      callbacks.onQuotaError?.(quotaErr)
      if (!callbacks.onQuotaError) callbacks.onError?.(quotaErr.message)
    } else {
      callbacks.onError?.(err.message || '连接失败')
    }
  }

  // 使用带断点续传的 SSE 连接
  if (enableResume) {
    return connectSSEWithResume({
      url: `/api/conversations/${conversationId}/messages`,
      conversationId,
      method: 'POST',
      data: requestData,
      onEvent,
      onComplete: () => callbacks.onComplete?.(),
      onConnectionError,
      onReconnecting: callbacks.onReconnecting,
      onReconnected: callbacks.onReconnected,
      getStreamingStatus: (convId) => getStreamingStatus(convId),
    })
  }

  // 不启用断点续传时使用普通 SSE 连接
  return connectSSE({
    url: `/api/conversations/${conversationId}/messages`,
    method: 'POST',
    data: requestData,
    onEvent,
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError,
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

/**
 * 回滚最后一轮对话（删除最后一条用户消息及其后续AI回复）
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>} { deleted_count: number }
 */
export function rollbackLastMessage(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}/rollback`,
    method: 'POST'
  })
}

/**
 * 搜索学习空间对话
 * @param {string} spaceId - 学习空间 ID
 * @param {string} q - 搜索关键词
 * @param {string} scope - 搜索范围: 'title' | 'content' | 'all'
 * @param {number} page - 页码
 * @param {number} pageSize - 每页条数
 * @returns {Promise<Object>} ConversationSearchResponse
 */
export function searchSpaceConversations(spaceId, q, scope = 'all', page = 1, pageSize = 20) {
  return request({
    url: `/api/spaces/${spaceId}/conversations/search`,
    method: 'GET',
    data: { q, scope, page, page_size: pageSize }
  })
}

/**
 * 搜索快速对话
 * @param {string} q - 搜索关键词
 * @param {string} scope - 搜索范围: 'title' | 'content' | 'all'
 * @param {number} page - 页码
 * @param {number} pageSize - 每页条数
 * @returns {Promise<Object>} ConversationSearchResponse
 */
export function searchQuickChatConversations(q, scope = 'all', page = 1, pageSize = 20) {
  return request({
    url: '/api/quick-chat/conversations/search',
    method: 'GET',
    data: { q, scope, page, page_size: pageSize }
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
 *   - onThinking(content): 思考过程增量内容（reasoning 模型）
 *   - onToolCall(toolData): 工具调用事件
 *   - onDone(fullContent, citations, rawData): 完成事件
 *   - onError(message): 错误事件
 *   - onComplete(): 连接关闭
 *   - onReconnecting(attempt): 正在重连（仅 enableResume=true 时）
 *   - onReconnected(): 重连成功（仅 enableResume=true 时）
 * @param {Array<string>} attachmentIds - 附件ID列表（可选）
 * @param {string} modelId - 模型 ID（可选）
 * @param {Object} options - 额外选项
 *   - enableResume: boolean - 是否启用断点续传（默认 true）
 * @returns {Function} 取消函数
 */
export function sendQuickChatMessage(conversationId, content, callbacks, attachmentIds = null, modelId = null, options = {}) {
  const { enableResume = true, thinking = null } = options

  const requestData = { content }
  if (attachmentIds && attachmentIds.length > 0) {
    requestData.attachment_ids = attachmentIds
  }
  if (modelId) {
    requestData.model_id = modelId
  }
  if (thinking !== null) {
    requestData.thinking = thinking
  }

  const onEvent = (eventType, data) => {
    switch (eventType) {
      case 'text_delta':
        callbacks.onTextDelta?.(data.content)
        break
      case 'thinking_delta':
        callbacks.onThinking?.(data.content)
        break
      case 'tool_call':
        callbacks.onToolCall?.(data)
        break
      case 'client_tool_request':
        callbacks.onClientToolRequest?.(data)
        break
      case 'title':
        callbacks.onTitle?.(data.title)
        break
      case 'done':
        callbacks.onDone?.(data.content, data.citations, data)
        break
      case 'error':
        callbacks.onError?.(data.message)
        break
    }
  }

  const onConnectionError = (err) => {
    const quotaErr = parseQuotaError(err.message || String(err))
    if (quotaErr) {
      callbacks.onQuotaError?.(quotaErr)
      if (!callbacks.onQuotaError) callbacks.onError?.(quotaErr.message)
    } else {
      callbacks.onError?.(err.message || '连接失败')
    }
  }

  // 使用带断点续传的 SSE 连接
  if (enableResume) {
    return connectSSEWithResume({
      url: `/api/quick-chat/conversations/${conversationId}/messages`,
      conversationId,
      method: 'POST',
      data: requestData,
      onEvent,
      onComplete: () => callbacks.onComplete?.(),
      onConnectionError,
      onReconnecting: callbacks.onReconnecting,
      onReconnected: callbacks.onReconnected,
      getStreamingStatus: (convId) => getStreamingStatus(convId),
    })
  }

  // 不启用断点续传时使用普通 SSE 连接
  return connectSSE({
    url: `/api/quick-chat/conversations/${conversationId}/messages`,
    method: 'POST',
    data: requestData,
    onEvent,
    onComplete: () => callbacks.onComplete?.(),
    onConnectionError,
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

/**
 * 获取快速对话异步工具任务状态
 * @param {string} conversationId - 对话 ID
 * @param {string} toolCallId - 工具调用 ID
 * @returns {Promise<Object>}
 */
export function getQuickChatToolTaskStatus(conversationId, toolCallId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/status`,
    method: 'GET'
  })
}

/**
 * 获取快速对话异步工具任务列表（用于恢复进行中的任务）
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>}
 */
export function listQuickChatToolTasks(conversationId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/tasks`,
    method: 'GET'
  })
}

/**
 * 绑定快速对话异步创建空间任务（KG 完成后调用）
 * @param {string} conversationId - 对话 ID
 * @param {string} toolCallId - 工具调用 ID
 * @returns {Promise<Object>}
 */
export function bindQuickChatToolTask(conversationId, toolCallId) {
  return request({
    url: `/api/quick-chat/conversations/${conversationId}/tools/${toolCallId}/bind`,
    method: 'POST'
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

// ==================== 流式状态与断点续传 API ====================

/**
 * 查询流式传输状态
 *
 * 用于客户端断连后检查 AI 是否仍在生成回复，以及获取已生成的部分内容。
 *
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>}
 *   - is_streaming: boolean - 是否正在流式传输
 *   - partial_content: string|null - 已生成的文本内容
 *   - partial_thinking: string|null - 已生成的思考内容
 *   - tool_calls: Array - 工具调用记录
 *   - updated_at: number|null - 最后更新时间戳
 */
export function getStreamingStatus(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}/streaming-status`,
    method: 'GET'
  })
}

/**
 * 主动终止当前会话的 AI 流式回复
 *
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>}
 *   - stopped: boolean
 *   - is_streaming: boolean
 *   - is_stopped: boolean
 *   - partial_content: string|null
 *   - partial_thinking: string|null
 *   - tool_calls: Array
 *   - updated_at: number|null
 */
export function stopStreamingReply(conversationId) {
  return request({
    url: `/api/conversations/${conversationId}/stop-stream`,
    method: 'POST'
  })
}

/**
 * 检查 AI 是否已回复（轻量级轮询端点）
 *
 * @param {string} conversationId - 对话 ID
 * @param {number} after - 用户消息发送时间戳 (Unix seconds)
 * @returns {Promise<Object>} { has_reply: boolean, preview: string }
 */
export function checkReplyStatus(conversationId, after) {
  return request({
    url: `/api/conversations/${conversationId}/reply-status`,
    method: 'GET',
    data: { after }
  })
}
