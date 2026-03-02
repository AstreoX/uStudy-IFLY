import { request } from '@/utils/request'

/**
 * 获取个人资料统计数据
 * @returns {Promise<Object>} { study_days, total_study_hours, avg_mastery, node_coverage_percent }
 */
export function getProfileStats() {
  return request({
    url: '/api/assessment/profile-stats',
    method: 'GET'
  })
}

/**
 * 获取连续性分数和状态
 * @returns {Promise<Object>} { score, cumulative_active_days, effective_gap_days, current_streak, last_gap, reset_threshold }
 */
export function getContinuityScore() {
  return request({
    url: '/api/assessment/continuity',
    method: 'GET'
  })
}

/**
 * 获取专注度分数
 * @param {number} weekOffset - 周偏移 (0=本周, 1=上周, 默认0)
 * @returns {Promise<Object>} { score, week_start, week_end, total_sessions, avg_session_depth, avg_session_duration_min, rhythm_score, active_days }
 */
export function getFocusScore(weekOffset = 0) {
  return request({
    url: `/api/assessment/focus?week_offset=${weekOffset}`,
    method: 'GET'
  })
}

/**
 * 获取深入程度分数
 * @param {number} weekOffset - 周偏移 (0=本周, 1=上周, 默认0)
 * @returns {Promise<Object>} { score, week_start, week_end, total_conversations, avg_messages_per_conv, avg_message_length, mastery_score, studied_node_count, total_node_count }
 */
export function getDepthScore(weekOffset = 0) {
  return request({
    url: `/api/assessment/depth?week_offset=${weekOffset}`,
    method: 'GET'
  })
}

/**
 * 获取理解程度分数
 * @returns {Promise<Object>} { score, quiz_accuracy, mastery_ratio, quiz_score_sum, quiz_total_score_sum, high_mastery_node_count, total_node_count }
 */
export function getComprehensionScore() {
  return request({
    url: '/api/assessment/comprehension',
    method: 'GET'
  })
}

/**
 * 获取知识结构分数
 * @returns {Promise<Object>} { score, solidity, advanced_ratio, qualifying_parent_count, total_node_count, advanced_edge_count }
 */
export function getKnowledgeStructureScore() {
  return request({
    url: '/api/assessment/knowledge-structure',
    method: 'GET'
  })
}

/**
 * 获取复习情况分数
 * @returns {Promise<Object>} { score, completion_rate, punctuality_rate, overdue_penalty, completed_count, overdue_count, on_time_count, avg_overdue_days }
 */
export function getReviewScore() {
  return request({
    url: '/api/assessment/review',
    method: 'GET'
  })
}

/**
 * 获取学习日历热力图数据
 * @param {number} months - 查询月数 (1-12, 默认3)
 * @returns {Promise<Object>} { start_date, end_date, records: [{date, activity_count}] }
 */
export function getContinuityCalendar(months = 3) {
  return request({
    url: `/api/assessment/continuity/calendar?months=${months}`,
    method: 'GET'
  })
}
