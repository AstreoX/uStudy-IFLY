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
