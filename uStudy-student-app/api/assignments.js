import { request } from '@/utils/request'

/**
 * 获取当前学生在学习空间中收到的教师测验。
 * @param {string} spaceId
 * @returns {Promise<Array>}
 */
export function getAssignmentsBySpace(spaceId) {
  return request({
    url: `/api/assignments?space_id=${encodeURIComponent(spaceId)}`,
    method: 'GET'
  })
}

/**
 * 获取教师测验题目和当前学生草稿。
 * OJ 私有评测数据不会由该接口返回。
 */
export function getAssignmentDetail(assignmentId) {
  return request({
    url: `/api/assignments/${assignmentId}`,
    method: 'GET'
  })
}

/**
 * 保存教师测验草稿。
 */
export function saveAssignmentDraft(assignmentId, data) {
  return request({
    url: `/api/assignments/${assignmentId}/draft`,
    method: 'PUT',
    data,
    timeout: 15000
  })
}

/**
 * 提交不含 OJ 编程题的教师测验。
 */
export function submitAssignment(assignmentId, data) {
  return request({
    url: `/api/assignments/${assignmentId}/submit`,
    method: 'POST',
    data,
    timeout: 30000
  })
}

/**
 * 获取当前学生的教师测验批改结果。
 */
export function getAssignmentSubmission(assignmentId) {
  return request({
    url: `/api/assignments/${assignmentId}/submission`,
    method: 'GET'
  })
}
