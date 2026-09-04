import { request } from '@/utils/request'

/**
 * 获取 OJ 运行能力。用于隐藏教师出题入口和禁用学生样例运行，
 * 不影响已发布编程题的题面、草稿及历史结果读取。
 */
export function getOjCapabilities() {
  return request({
    url: '/api/assignments/oj/capabilities',
    method: 'GET',
    timeout: 10000
  })
}

/**
 * 获取当前学生在指定空间收到的教师作业。
 */
export function getAssignmentsBySpace(spaceId) {
  return request({
    url: `/api/assignments?space_id=${encodeURIComponent(spaceId)}`,
    method: 'GET'
  })
}

/**
 * 获取作业题目及当前学生的草稿信息。
 * 截止前服务端不得在此响应中返回标准答案或评分规则。
 */
export function getAssignmentDetail(assignmentId) {
  return request({
    url: `/api/assignments/${assignmentId}`,
    method: 'GET'
  })
}

/**
 * 幂等保存学生作业草稿。
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
 * 提交一次性答卷。后台可返回 202 并异步批改。
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
 * 获取当前学生的提交、批改进度和成绩。
 */
export function getAssignmentSubmission(assignmentId) {
  return request({
    url: `/api/assignments/${assignmentId}/submission`,
    method: 'GET'
  })
}

/**
 * 运行编程题公开样例。服务端仅允许返回 public_config 中的样例结果。
 */
export function createAssignmentSampleRun(assignmentId, questionId, data) {
  return request({
    url: `/api/assignments/${assignmentId}/questions/${questionId}/sample-runs`,
    method: 'POST',
    data,
    timeout: 15000
  })
}

/**
 * 查询当前学生创建的公开样例运行；访问其他学生的 run 必须由服务端拒绝。
 */
export function getAssignmentSampleRun(assignmentId, runId) {
  return request({
    url: `/api/assignments/${assignmentId}/sample-runs/${runId}`,
    method: 'GET',
    timeout: 15000
  })
}
