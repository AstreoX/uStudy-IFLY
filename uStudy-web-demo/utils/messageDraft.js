/**
 * 消息草稿管理工具
 * 用于持久化未同步的用户消息，防止请求失败后消息丢失
 */

const PENDING_PREFIX = 'pending_messages_'
const MAX_PENDING_MESSAGES = 10

/**
 * 获取存储 key
 * @param {string} conversationId - 对话ID
 * @returns {string}
 */
function getStorageKey(conversationId) {
  return `${PENDING_PREFIX}${conversationId}`
}

/**
 * 保存待同步消息
 * @param {string} conversationId - 对话ID
 * @param {Object} message - 消息对象 { id, role, content, attachments, timestamp }
 */
export function savePendingMessage(conversationId, message) {
  if (!conversationId || !message) return

  try {
    const key = getStorageKey(conversationId)
    const existing = localStorage.getItem(key)
    let messages = []

    if (existing) {
      try {
        messages = JSON.parse(existing)
        if (!Array.isArray(messages)) {
          messages = []
        }
      } catch {
        messages = []
      }
    }

    const msgWithTimestamp = {
      ...message,
      timestamp: message.timestamp || Date.now(),
      pendingId: message.pendingId || `pending_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    }

    // 检查是否已存在（基于 pendingId 去重）
    const existingIndex = messages.findIndex(m => m.pendingId === msgWithTimestamp.pendingId)
    if (existingIndex >= 0) {
      messages[existingIndex] = msgWithTimestamp
    } else {
      messages.push(msgWithTimestamp)
    }

    // 限制最大数量
    if (messages.length > MAX_PENDING_MESSAGES) {
      messages = messages.slice(-MAX_PENDING_MESSAGES)
    }

    localStorage.setItem(key, JSON.stringify(messages))
  } catch (err) {
    console.warn('[messageDraft] savePendingMessage failed:', err)
  }
}

/**
 * 获取待同步消息列表
 * @param {string} conversationId - 对话ID
 * @returns {Array} 消息列表
 */
export function getPendingMessages(conversationId) {
  if (!conversationId) return []

  try {
    const key = getStorageKey(conversationId)
    const raw = localStorage.getItem(key)
    if (!raw) return []

    const messages = JSON.parse(raw)
    return Array.isArray(messages) ? messages : []
  } catch (err) {
    console.warn('[messageDraft] getPendingMessages failed:', err)
    return []
  }
}

/**
 * 移除已同步的消息
 * @param {string} conversationId - 对话ID
 * @param {string} pendingId - 待同步消息的唯一标识
 */
export function removePendingMessage(conversationId, pendingId) {
  if (!conversationId || !pendingId) return

  try {
    const key = getStorageKey(conversationId)
    const raw = localStorage.getItem(key)
    if (!raw) return

    let messages = JSON.parse(raw)
    if (!Array.isArray(messages)) return

    messages = messages.filter(m => m.pendingId !== pendingId)

    if (messages.length === 0) {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, JSON.stringify(messages))
    }
  } catch (err) {
    console.warn('[messageDraft] removePendingMessage failed:', err)
  }
}

/**
 * 清空对话的所有待同步消息
 * @param {string} conversationId - 对话ID
 */
export function clearPendingMessages(conversationId) {
  if (!conversationId) return

  try {
    const key = getStorageKey(conversationId)
    localStorage.removeItem(key)
  } catch (err) {
    console.warn('[messageDraft] clearPendingMessages failed:', err)
  }
}

/**
 * 批量保存待同步消息（用于页面离开时保存）
 * @param {string} conversationId - 对话ID
 * @param {Array} messages - 消息列表（只保存 synced: false 的用户消息）
 */
export function savePendingMessagesFromArray(conversationId, messages) {
  if (!conversationId || !Array.isArray(messages)) return

  const pendingMessages = messages.filter(
    m => m.role === 'user' && m.synced === false && m.pendingId
  )

  if (pendingMessages.length === 0) {
    clearPendingMessages(conversationId)
    return
  }

  try {
    const key = getStorageKey(conversationId)
    const toSave = pendingMessages.slice(-MAX_PENDING_MESSAGES).map(m => ({
      pendingId: m.pendingId,
      role: m.role,
      content: m.content,
      attachments: m.attachments || [],
      timestamp: m.timestamp || Date.now()
    }))
    localStorage.setItem(key, JSON.stringify(toSave))
  } catch (err) {
    console.warn('[messageDraft] savePendingMessagesFromArray failed:', err)
  }
}

/**
 * 迁移临时对话的待同步消息到正式对话
 * @param {string} tempId - 临时对话ID
 * @param {string} realId - 正式对话ID
 */
export function migratePendingMessages(tempId, realId) {
  if (!tempId || !realId) return

  try {
    const tempKey = getStorageKey(tempId)
    const raw = localStorage.getItem(tempKey)
    if (!raw) return

    const messages = JSON.parse(raw)
    if (Array.isArray(messages) && messages.length > 0) {
      const realKey = getStorageKey(realId)
      localStorage.setItem(realKey, JSON.stringify(messages))
    }
    localStorage.removeItem(tempKey)
  } catch (err) {
    console.warn('[messageDraft] migratePendingMessages failed:', err)
  }
}
