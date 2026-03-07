import { request } from '@/utils/request'
import config from '@/config'
import { getTokens } from '@/utils/storage'

/**
 * 创建学习空间
 * @param {Object} data - {
 *   name: string,
 *   description?: string,
 *   color: string,
 *   learning_preferences?: {
 *     preset_preferences: string[],
 *     custom_preference?: string
 *   }
 * }
 * @returns {Promise<Object>} SpaceResponse
 */
export function createSpace(data) {
  return request({
    url: '/api/spaces',
    method: 'POST',
    data
  })
}

/**
 * 获取用户所有学习空间
 * @returns {Promise<Array>} List of SpaceResponse
 */
export function getSpaces() {
  return request({
    url: '/api/spaces',
    method: 'GET'
  })
}

/**
 * 获取单个学习空间详情
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<Object>} SpaceResponse
 */
export function getSpace(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'GET'
  })
}

/**
 * 更新学习空间
 * @param {string} spaceId - 学习空间 ID
 * @param {Object} data - { name?: string, description?: string, color?: string }
 * @returns {Promise<Object>} SpaceResponse
 */
export function updateSpace(spaceId, data) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 获取学习空间的知识图谱
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<Object>} { nodes: NodeResponse[], edges: EdgeResponse[] }
 */
export function getSpaceGraph(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/graph?_t=${Date.now()}`,
    method: 'GET'
  })
}

/**
 * 删除学习空间
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<void>}
 */
export function deleteSpace(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}`,
    method: 'DELETE'
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
 * 触发知识图谱生成（异步任务）
 * @param {string} spaceId - 学习空间 ID
 * @param {Object} data - { topic: string, user_preference?: string }
 * @returns {Promise<Object>} { task_id, status, task_type, created_at }
 */
export function generateKnowledgeGraph(spaceId, data) {
  return request({
    url: `/api/agents/knowledge-graph?space_id=${spaceId}`,
    method: 'POST',
    data
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
 * 触发测试题生成（异步任务）
 * @param {string} spaceId - 学习空间 ID
 * @param {Object} data - { topic: string, difficulty_level: string, test_struct: Array }
 * @returns {Promise<Object>} { task_id, status, task_type, created_at }
 */
export function generateQuiz(spaceId, data) {
  return request({
    url: `/api/agents/quiz?space_id=${spaceId}`,
    method: 'POST',
    data
  })
}

/**
 * 获取测试详情
 * @param {string} quizId - 测试 ID
 * @returns {Promise<Object>} QuizDetailResponse
 */
export function getQuizDetail(quizId) {
  return request({
    url: `/api/quizzes/${quizId}`,
    method: 'GET'
  })
}

/**
 * 提交答卷并获取评估结果
 * @param {string} quizId - 测试 ID
 * @param {Object} data - { answers: [{ question_id: string, answer: any }] }
 * @returns {Promise<Object>} QuizEvaluationResponse
 */
export function submitQuiz(quizId, data) {
  return request({
    url: `/api/quizzes/${quizId}/submit`,
    method: 'POST',
    data,
    timeout: 180000 // AI 评估可能需要较长时间，设置 3 分钟超时
  })
}

/**
 * 获取空间所有测验列表
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<Array>} List of QuizListItemResponse
 */
export function getQuizzesBySpace(spaceId) {
  return request({
    url: `/api/quizzes?space_id=${spaceId}`,
    method: 'GET'
  })
}

/**
 * 获取测验作答记录
 * @param {string} quizId - 测试 ID
 * @returns {Promise<Object>} QuizAttemptResponse
 */
export function getQuizAttempt(quizId) {
  return request({
    url: `/api/quizzes/${quizId}/attempt`,
    method: 'GET'
  })
}

/**
 * 删除测验
 * @param {string} quizId - 测试 ID
 * @returns {Promise<void>}
 */
export function deleteQuiz(quizId) {
  return request({
    url: `/api/quizzes/${quizId}`,
    method: 'DELETE'
  })
}

// ============ 知识库文档/链接 API ============

/**
 * 获取学习空间的所有文档和链接
 * @param {string} spaceId - 学习空间 ID
 * @returns {Promise<Object>} { documents: DocumentResponse[], total: number }
 */
export function getSpaceDocuments(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/documents`,
    method: 'GET'
  })
}

/**
 * 添加链接到学习空间
 * @param {string} spaceId - 学习空间 ID
 * @param {Object} data - { title: string, url: string }
 * @returns {Promise<Object>} DocumentResponse
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
 * @param {string} spaceId - 学习空间 ID
 * @param {string} documentId - 文档 ID
 * @returns {Promise<void>}
 */
export function deleteSpaceDocument(spaceId, documentId) {
  return request({
    url: `/api/spaces/${spaceId}/documents/${documentId}`,
    method: 'DELETE'
  })
}

/**
 * 上传文档到学习空间
 * @param {string} spaceId - 学习空间 ID
 * @param {string} filePath - 本地文件路径
 * @param {Function} onProgress - 上传进度回调 (progressEvent) => void
 * @returns {Promise<Object>} DocumentResponse
 */
export function uploadSpaceDocument(spaceId, filePath, onProgress) {
  return new Promise((resolve, reject) => {
    const tokens = getTokens()

    const uploadTask = uni.uploadFile({
      url: `${config.API_BASE_URL}/api/spaces/${spaceId}/documents/upload`,
      filePath: filePath,
      name: 'file',
      header: {
        Authorization: tokens?.access_token ? `Bearer ${tokens.access_token}` : ''
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const data = JSON.parse(res.data)
            resolve(data)
          } catch (e) {
            reject(new Error('响应解析失败'))
          }
        } else {
          try {
            const errorData = JSON.parse(res.data)
            reject(new Error(errorData.detail || '上传失败'))
          } catch (e) {
            reject(new Error(`上传失败: ${res.statusCode}`))
          }
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '网络错误'))
      }
    })

    if (onProgress && uploadTask) {
      uploadTask.onProgressUpdate((res) => {
        onProgress(res)
      })
    }
  })
}

// ============ 工具模式 API ============

/**
 * 获取工具目录（按分类组织）
 * @returns {Promise<Array>} [{ category: string, tools: [{ name, summary }] }]
 */
export function getToolCatalog() {
  return request({
    url: '/api/spaces/tool-catalog',
    method: 'GET'
  })
}

// ============ RAG 文档处理状态 API ============

/**
 * 获取文档处理状态
 * @param {string} spaceId - 学习空间 ID
 * @param {string} documentId - 文档 ID
 * @returns {Promise<Object>} ProcessingStatusResponse
 * - document_id: string
 * - status: 'not_started' | 'pending' | 'processing' | 'completed' | 'failed'
 * - chunk_count: number | null (完成时有值)
 * - error_message: string | null (失败时有值)
 * - started_at: string | null
 * - completed_at: string | null
 * - created_at: string
 */
export function getDocumentProcessingStatus(spaceId, documentId) {
  return request({
    url: `/api/rag/spaces/${spaceId}/documents/${documentId}/processing`,
    method: 'GET'
  })
}

// ============ 空间分享 API ============

export function generateShareCode(spaceId) {
  return request({
    url: `/api/spaces/${spaceId}/share-code`,
    method: 'POST'
  })
}

export function importSpaceByCode(shareCode) {
  return request({
    url: '/api/spaces/import',
    method: 'POST',
    data: { share_code: shareCode }
  })
}
