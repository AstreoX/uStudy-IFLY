import { request } from '@/utils/request'
import config from '@/config'
import { getTokens } from '@/utils/storage'

export function getSpaces() {
  return request({
    url: '/api/spaces',
    method: 'GET'
  })
}

/**
 * 删除学习空间
 * @param {string|number} spaceId
 */
export function deleteSpace(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'DELETE'
  })
}

/**
 * Create a learning space
 * @param {Object} data - { name, color, learning_preferences? }
 */
export function createSpace(data) {
  return request({
    url: '/api/spaces',
    method: 'POST',
    data
  })
}

/**
 * Trigger async knowledge graph generation
 * @param {string} spaceId
 * @param {Object} data - { topic, user_preference? }
 */
export function generateKnowledgeGraph(spaceId, data) {
  return request({
    url: `/api/agents/knowledge-graph?space_id=${spaceId}`,
    method: 'POST',
    data
  })
}

export function getSpaceGraph(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/graph?_t=${Date.now()}`,
    method: 'GET'
  })
}

/**
 * 获取测试详情
 * @param {string} quizId
 * @returns {Promise<Object>}
 */
export function getQuizDetail(quizId) {
  return request({
    url: `/api/quizzes/${quizId}`,
    method: 'GET'
  })
}

/**
 * 提交答卷并获取评估结果
 * @param {string} quizId
 * @param {{answers: Array<{question_id: string, answer: any}>}} data
 * @returns {Promise<Object>}
 */
export function submitQuiz(quizId, data) {
  return request({
    url: `/api/quizzes/${quizId}/submit`,
    method: 'POST',
    data,
    timeout: 180000
  })
}

/**
 * 异步提交答卷（web 端使用，不等待 AI 评估完成）
 * @param {string} quizId
 * @param {{answers: Array<{question_id: string, answer: any}>}} data
 * @returns {Promise<{quiz_id: string, attempt_id: string, status: string, message: string}>}
 */
export function submitQuizAsync(quizId, data) {
  return request({
    url: `/api/quizzes/${quizId}/submit?async=true`,
    method: 'POST',
    data,
    timeout: 30000
  })
}

/**
 * 获取空间测验列表
 * @param {string} spaceId
 * @returns {Promise<Array>}
 */
export function getQuizzesBySpace(spaceId) {
  return request({
    url: `/api/quizzes?space_id=${spaceId}`,
    method: 'GET'
  })
}

/**
 * 获取测验作答记录
 * @param {string} quizId
 * @returns {Promise<Object>}
 */
export function getQuizAttempt(quizId) {
  return request({
    url: `/api/quizzes/${quizId}/attempt`,
    method: 'GET'
  })
}

/**
 * 删除测验
 * @param {string} quizId
 * @returns {Promise<void>}
 */
export function deleteQuiz(quizId) {
  return request({
    url: `/api/quizzes/${quizId}`,
    method: 'DELETE'
  })
}

/**
 * 获取学习空间文档/链接列表
 * @param {string|number} spaceId
 * @returns {Promise<{documents: Array, total: number}>}
 */
export function getSpaceDocuments(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/documents`,
    method: 'GET'
  })
}

/**
 * 添加链接到学习空间
 * @param {string|number} spaceId
 * @param {{title: string, url: string}} data
 */
export function addSpaceLink(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}/documents/link`,
    method: 'POST',
    data
  })
}

/**
 * 删除文档或链接
 * @param {string|number} spaceId
 * @param {string} documentId
 */
export function deleteSpaceDocument(spaceId, documentId) {
  return request({
    url: `/api/spaces/${spaceId}/documents/${documentId}`,
    method: 'DELETE'
  })
}

/**
 * H5 上传文档到学习空间
 * @param {string|number} spaceId
 * @param {File} file
 * @param {string} [accessToken]
 * @returns {Promise<Object>}
 */
export async function uploadSpaceDocumentH5(spaceId, file, accessToken) {
  const tokens = getTokens()
  const token = accessToken || tokens?.access_token

  if (!token) {
    throw new Error('登录已过期，请重新登录')
  }

  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${config.API_BASE_URL}/api/spaces/${spaceId}/documents/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: formData
  })

  if (!response.ok) {
    let message = '上传失败'
    try {
      const errorData = await response.json()
      if (typeof errorData?.detail === 'string') {
        message = errorData.detail
      } else if (errorData?.detail?.message) {
        message = errorData.detail.message
      } else if (errorData?.message) {
        message = errorData.message
      }
    } catch (error) {
      message = response.statusText || message
    }
    throw new Error(message)
  }

  return response.json()
}

/**
 * 获取文档处理状态
 * @param {string|number} spaceId
 * @param {string} documentId
 */
export function getDocumentProcessingStatus(spaceId, documentId) {
  return request({
    url: `/api/rag/spaces/${spaceId}/documents/${documentId}/processing`,
    method: 'GET'
  })
}

/**
 * 获取单个学习空间详情
 * @param {string} spaceId
 */
export function getSpace(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'GET'
  })
}

/**
 * 更新学习空间
 * @param {string} spaceId
 * @param {Object} data
 */
export function updateSpace(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 获取工具目录
 * @returns {Promise<Array>}
 */
export function getToolCatalog() {
  return request({
    url: '/api/spaces/tool-catalog',
    method: 'GET'
  })
}

/**
 * 查询异步任务状态
 * @param {string} taskId - 任务 ID
 * @returns {Promise<Object>} AgentTaskResultResponse
 */
export function getTaskStatus(taskId) {
  return request({
    url: `/api/agents/tasks/${taskId}`,
    method: 'GET'
  })
}

/**
 * 扩展知识图谱节点（生成子节点，异步任务）
 * @param {string} spaceId
 * @param {string} nodeId
 * @returns {Promise<Object>} { task_id, status, task_type, created_at }
 */
export function expandNode(spaceId, nodeId) {
  return request({
    url: `/api/agents/expand-node?space_id=${spaceId}&node_id=${nodeId}`,
    method: 'POST',
    data: {}
  })
}

/**
 * 获取学习空间笔记列表
 * @param {string|number} spaceId
 * @param {Object} [options]
 * @param {string|number} [options.nodeId] - 按节点筛选
 * @param {boolean} [options.freeOnly] - 仅返回自由笔记
 * @returns {Promise<Array>}
 */
export function getSpaceNotes(spaceId, { nodeId, freeOnly } = {}) {
  let url = `/api/spaces/${spaceId}/notes`
  const params = []
  if (nodeId !== undefined && nodeId !== null && nodeId !== '') {
    params.push(`node_id=${encodeURIComponent(nodeId)}`)
  }
  if (freeOnly) params.push('free_only=true')
  if (params.length) url += '?' + params.join('&')

  return request({
    url,
    method: 'GET'
  })
}

/**
 * 获取笔记详情
 * @param {string|number} spaceId
 * @param {string|number} noteId
 * @returns {Promise<Object>}
 */
export function getNoteDetail(spaceId, noteId) {
  return request({
    url: `/api/spaces/${spaceId}/notes/${noteId}`,
    method: 'GET'
  })
}

/**
 * 更新笔记
 * @param {string|number} spaceId
 * @param {string|number} noteId
 * @param {Object} data - { title?, content?, node_id?, sort_order? }
 * @returns {Promise<Object>}
 */
export function updateNote(spaceId, noteId, data) {
  return request({
    url: `/api/spaces/${spaceId}/notes/${noteId}`,
    method: 'PATCH',
    data
  })
}
