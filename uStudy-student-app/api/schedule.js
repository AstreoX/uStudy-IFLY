/**
 * @deprecated 日程管理已改为 client_tool_request 协议。
 * 后端通过 SSE 发送日程工具请求 → 前端调用 Android 系统日历 (utils/calendar.js) → POST 结果回后端。
 * 此文件保留仅供参考，不再被使用。
 *
 * 新流程：
 * - 前端日历操作: utils/calendar.js (executeCalendarTool)
 * - 结果提交: api/chat.js (submitToolResult)
 * - SSE 事件: client_tool_request
 */

/**
 * @typedef {Object} Schedule
 * @property {string} id - 唯一日程 ID
 * @property {string} title - 日程标题
 * @property {string} start_time - 开始时间 (YYYY-MM-DD HH:MM)
 * @property {string} end_time - 结束时间 (YYYY-MM-DD HH:MM)
 * @property {string} details - 日程详情
 * @property {string} created_at - ISO 创建时间戳
 * @property {string} updated_at - ISO 更新时间戳
 */

// ============ 常量 ============

const MOCK_NETWORK_DELAY_MS = 100

const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/
const TIME_REGEX = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/

const INITIAL_SCHEDULES = Object.freeze([
  {
    id: 'schedule_001',
    title: '数据结构学习',
    start_time: '2026-02-10 09:00',
    end_time: '2026-02-10 11:00',
    details: '复习链表、栈、队列的基本概念和实现',
    created_at: '2026-02-01T08:00:00.000Z',
    updated_at: '2026-02-01T08:00:00.000Z'
  },
  {
    id: 'schedule_002',
    title: '算法复习',
    start_time: '2026-02-15 14:00',
    end_time: '2026-02-15 17:00',
    details: '重点复习排序算法和二分查找',
    created_at: '2026-02-01T08:00:00.000Z',
    updated_at: '2026-02-01T08:00:00.000Z'
  },
  {
    id: 'schedule_003',
    title: '期末考试',
    start_time: '2026-02-20 09:00',
    end_time: '2026-02-20 12:00',
    details: '数据结构与算法期末考试，地点：教学楼A301',
    created_at: '2026-02-01T08:00:00.000Z',
    updated_at: '2026-02-01T08:00:00.000Z'
  }
])

// ============ 工具函数 ============

/**
 * 生成简单的 UUID
 * @returns {string} UUID 字符串
 */
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

/**
 * 获取当前 ISO 时间字符串
 * @returns {string} ISO 格式时间
 */
function getCurrentISOTime() {
  return new Date().toISOString()
}

/**
 * 解析日期字符串为 Date 对象（仅日期部分）
 * @param {string} dateStr - 格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM
 * @returns {Date} Date 对象
 * @throws {Error} 如果日期格式无效
 */
function parseDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') {
    throw new Error('无效的日期字符串')
  }
  const datePart = dateStr.split(' ')[0]
  const date = new Date(datePart)
  if (isNaN(date.getTime())) {
    throw new Error(`无效的日期: ${dateStr}`)
  }
  return date
}

/**
 * 创建一天结束时间的 Date 对象（不可变方式）
 * @param {Date} date - 原始日期
 * @returns {Date} 当天 23:59:59.999 的新 Date 对象
 */
function getEndOfDay(date) {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    23, 59, 59, 999
  )
}

/**
 * 验证日期格式 YYYY-MM-DD
 * @param {string} dateStr - 日期字符串
 * @returns {boolean} 是否有效
 */
function isValidDateFormat(dateStr) {
  return DATE_REGEX.test(dateStr)
}

/**
 * 验证时间格式 YYYY-MM-DD HH:MM
 * @param {string} timeStr - 时间字符串
 * @returns {boolean} 是否有效
 */
function isValidTimeFormat(timeStr) {
  return TIME_REGEX.test(timeStr)
}

// ============ 模拟数据存储 ============

let mockSchedules = INITIAL_SCHEDULES.map(s => ({ ...s }))

// ============ API 函数 ============

/**
 * 获取指定日期范围内的日程
 * @param {string} startDate - 起始日期，格式 YYYY-MM-DD
 * @param {string} endDate - 结束日期，格式 YYYY-MM-DD
 * @returns {Promise<Object>} 日程列表响应
 * - schedules: Schedule[] 日程数组
 * - total: number 总数
 * - query: Object 查询参数
 */
export function getSchedules(startDate, endDate) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      // 参数验证
      if (!startDate || !endDate) {
        reject(new Error('缺少必要参数：start_date, end_date'))
        return
      }

      if (!isValidDateFormat(startDate) || !isValidDateFormat(endDate)) {
        reject(new Error('日期格式无效，期望格式: YYYY-MM-DD'))
        return
      }

      try {
        const start = parseDate(startDate)
        const endParsed = parseDate(endDate)
        const end = getEndOfDay(endParsed)

        const filtered = mockSchedules.filter((schedule) => {
          const scheduleDate = parseDate(schedule.start_time)
          return scheduleDate >= start && scheduleDate <= end
        })

        resolve({
          schedules: filtered,
          total: filtered.length,
          query: { start_date: startDate, end_date: endDate }
        })
      } catch (error) {
        reject(error)
      }
    }, MOCK_NETWORK_DELAY_MS)
  })
}

/**
 * 添加新日程
 * @param {Object} data - 日程数据
 * @param {string} data.title - 日程标题
 * @param {string} data.start_time - 开始时间，格式 YYYY-MM-DD HH:MM
 * @param {string} data.end_time - 结束时间，格式 YYYY-MM-DD HH:MM
 * @param {string} data.details - 日程详细信息
 * @returns {Promise<Schedule>} 新创建的日程对象
 */
export function addSchedule(data) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      // 参数验证
      if (!data.title || !data.start_time || !data.end_time || !data.details) {
        reject(new Error('缺少必要参数：title, start_time, end_time, details'))
        return
      }

      // 时间格式验证
      if (!isValidTimeFormat(data.start_time) || !isValidTimeFormat(data.end_time)) {
        reject(new Error('时间格式无效，期望格式: YYYY-MM-DD HH:MM'))
        return
      }

      // 时间逻辑验证
      const startTime = new Date(data.start_time.replace(' ', 'T'))
      const endTime = new Date(data.end_time.replace(' ', 'T'))
      if (endTime <= startTime) {
        reject(new Error('结束时间必须晚于开始时间'))
        return
      }

      const now = getCurrentISOTime()
      const newSchedule = {
        id: `schedule_${generateUUID()}`,
        title: data.title,
        start_time: data.start_time,
        end_time: data.end_time,
        details: data.details,
        created_at: now,
        updated_at: now
      }

      // 不可变更新：创建新数组
      mockSchedules = [...mockSchedules, newSchedule]

      resolve(newSchedule)
    }, MOCK_NETWORK_DELAY_MS)
  })
}

/**
 * 删除日程
 * @param {string} scheduleId - 日程 ID
 * @returns {Promise<Object>} 删除结果
 * - success: boolean 是否成功
 * - deleted_id: string 被删除的日程 ID
 */
export function deleteSchedule(scheduleId) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (!scheduleId) {
        reject(new Error('缺少必要参数：schedule_id'))
        return
      }

      const index = mockSchedules.findIndex((s) => s.id === scheduleId)

      if (index === -1) {
        reject(new Error(`日程不存在：${scheduleId}`))
        return
      }

      // 不可变更新：创建新数组，排除被删除的项
      mockSchedules = mockSchedules.filter((s) => s.id !== scheduleId)

      resolve({
        success: true,
        deleted_id: scheduleId
      })
    }, MOCK_NETWORK_DELAY_MS)
  })
}

/**
 * 更新日程
 * @param {string} scheduleId - 日程 ID
 * @param {Object} data - 要更新的字段（可选）
 * @param {string} [data.title] - 新的日程标题
 * @param {string} [data.start_time] - 新的开始时间，格式 YYYY-MM-DD HH:MM
 * @param {string} [data.end_time] - 新的结束时间，格式 YYYY-MM-DD HH:MM
 * @param {string} [data.details] - 新的日程详细信息
 * @returns {Promise<Schedule>} 更新后的日程对象
 */
export function updateSchedule(scheduleId, data) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (!scheduleId) {
        reject(new Error('缺少必要参数：schedule_id'))
        return
      }

      const index = mockSchedules.findIndex((s) => s.id === scheduleId)

      if (index === -1) {
        reject(new Error(`日程不存在：${scheduleId}`))
        return
      }

      // 时间格式验证（如果提供了时间参数）
      if (data.start_time !== undefined && !isValidTimeFormat(data.start_time)) {
        reject(new Error('start_time 格式无效，期望格式: YYYY-MM-DD HH:MM'))
        return
      }
      if (data.end_time !== undefined && !isValidTimeFormat(data.end_time)) {
        reject(new Error('end_time 格式无效，期望格式: YYYY-MM-DD HH:MM'))
        return
      }

      const existingSchedule = mockSchedules[index]

      // 计算最终的时间值用于验证
      const finalStartTime = data.start_time !== undefined ? data.start_time : existingSchedule.start_time
      const finalEndTime = data.end_time !== undefined ? data.end_time : existingSchedule.end_time

      // 时间逻辑验证
      const startTime = new Date(finalStartTime.replace(' ', 'T'))
      const endTime = new Date(finalEndTime.replace(' ', 'T'))
      if (endTime <= startTime) {
        reject(new Error('结束时间必须晚于开始时间'))
        return
      }

      // 不可变更新：创建新对象
      const updatedSchedule = {
        ...existingSchedule,
        ...(data.title !== undefined && { title: data.title }),
        ...(data.start_time !== undefined && { start_time: data.start_time }),
        ...(data.end_time !== undefined && { end_time: data.end_time }),
        ...(data.details !== undefined && { details: data.details }),
        updated_at: getCurrentISOTime()
      }

      // 不可变更新：创建新数组
      mockSchedules = mockSchedules.map((s) =>
        s.id === scheduleId ? updatedSchedule : s
      )

      resolve(updatedSchedule)
    }, MOCK_NETWORK_DELAY_MS)
  })
}

// ============ 辅助函数（用于测试） ============

/**
 * 重置模拟数据到初始状态（仅用于测试）
 */
export function _resetMockData() {
  mockSchedules = INITIAL_SCHEDULES.map(s => ({ ...s }))
}

/**
 * 获取当前所有日程（仅用于测试）
 * @returns {Schedule[]} 所有日程数组的副本
 */
export function _getAllSchedules() {
  return mockSchedules.map(s => ({ ...s }))
}
