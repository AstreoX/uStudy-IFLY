/**
 * Android 系统日历桥接模块
 *
 * 使用 plus.android API 直接调用 Android CalendarContract，
 * 无需编写原生插件。
 *
 * 后端时间格式: "YYYY-MM-DD HH:MM"
 * Android CalendarContract: 毫秒时间戳 (UTC)
 */

const CALENDAR_DEBUG_STORAGE_KEY = 'calendar_debug'

function getCalendarErrorMessage(err) {
  if (!err) return ''
  if (typeof err === 'string') return err
  if (err.message) return String(err.message)
  if (err.errMsg) return String(err.errMsg)
  try {
    return JSON.stringify(err)
  } catch (e) {
    return String(err)
  }
}

function isCalendarDebugEnabled() {
  try {
    return !!uni.getStorageSync(CALENDAR_DEBUG_STORAGE_KEY)
  } catch (err) {
    return false
  }
}

function calendarDebugLog(...args) {
  if (!isCalendarDebugEnabled()) return
  console.log('[CalendarBridge]', ...args)
}

function isAndroidCalendarRuntimeAvailable() {
  try {
    return (
      typeof plus !== 'undefined' &&
      plus &&
      plus.os &&
      plus.os.name === 'Android' &&
      plus.android &&
      typeof plus.android.runtimeMainActivity === 'function'
    )
  } catch (err) {
    return false
  }
}

function tryImportClass(target) {
  if (
    !target ||
    typeof plus === 'undefined' ||
    !plus ||
    !plus.android ||
    typeof plus.android.importClass !== 'function'
  ) {
    return null
  }
  try {
    return plus.android.importClass(target)
  } catch (err) {
    calendarDebugLog('importClass failed:', getCalendarErrorMessage(err))
    return null
  }
}

function getAndroidResolver() {
  if (!isAndroidCalendarRuntimeAvailable()) {
    throw new Error('当前运行环境不支持 Android 日历桥接')
  }

  const main = plus.android.runtimeMainActivity()
  tryImportClass(main)

  const resolver = main.getContentResolver()
  tryImportClass(resolver)

  if (!resolver) {
    throw new Error('无法获取 Android ContentResolver')
  }

  return { main, resolver }
}

function invokeCompat(target, method, args = []) {
  if (!target) {
    throw new Error(`Android 调用失败: target 为空 (${method})`)
  }

  if (typeof target[method] === 'function') {
    try {
      return { value: target[method](...args), usedFallback: false }
    } catch (err) {
      calendarDebugLog(`direct call failed: ${method}`, getCalendarErrorMessage(err))
    }
  }

  if (
    typeof plus !== 'undefined' &&
    plus &&
    plus.android &&
    typeof plus.android.invoke === 'function'
  ) {
    const value = plus.android.invoke(target, method, ...args)
    return { value, usedFallback: true }
  }

  throw new Error(`Android 调用失败: 方法 ${method} 不可用`)
}

function resolverQuery(resolver, uri, projection, selection, selectionArgs, sortOrder) {
  const result = invokeCompat(resolver, 'query', [uri, projection, selection, selectionArgs, sortOrder])
  if (result.usedFallback) {
    calendarDebugLog('resolver.query fallback used')
  }
  return result.value
}

function resolverInsert(resolver, uri, values) {
  const result = invokeCompat(resolver, 'insert', [uri, values])
  if (result.usedFallback) {
    calendarDebugLog('resolver.insert fallback used')
  }
  return result.value
}

function resolverDelete(resolver, uri, selection, selectionArgs) {
  const result = invokeCompat(resolver, 'delete', [uri, selection, selectionArgs])
  if (result.usedFallback) {
    calendarDebugLog('resolver.delete fallback used')
  }
  return result.value
}

function resolverUpdate(resolver, uri, values, selection, selectionArgs) {
  const result = invokeCompat(resolver, 'update', [uri, values, selection, selectionArgs])
  if (result.usedFallback) {
    calendarDebugLog('resolver.update fallback used')
  }
  return result.value
}

function safeCloseCursor(cursor) {
  if (!cursor) return
  tryImportClass(cursor)
  try {
    const result = invokeCompat(cursor, 'close', [])
    if (result.usedFallback) {
      calendarDebugLog('cursor.close fallback used')
    }
  } catch (err) {
    calendarDebugLog('cursor.close failed:', getCalendarErrorMessage(err))
  }
}

/**
 * 将 "YYYY-MM-DD HH:MM" 转为毫秒时间戳
 */
function parseToMillis(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') {
    throw new Error('无效的时间格式')
  }

  const [datePart, timePart] = timeStr.split(' ')
  if (!datePart || !timePart) {
    throw new Error(`时间格式错误: ${timeStr}`)
  }

  const [year, month, day] = datePart.split('-').map(Number)
  const [hour, minute] = timePart.split(':').map(Number)
  if (
    Number.isNaN(year) ||
    Number.isNaN(month) ||
    Number.isNaN(day) ||
    Number.isNaN(hour) ||
    Number.isNaN(minute)
  ) {
    throw new Error(`时间格式错误: ${timeStr}`)
  }

  const d = new Date(year, month - 1, day, hour, minute, 0)
  if (Number.isNaN(d.getTime())) {
    throw new Error(`时间无效: ${timeStr}`)
  }
  return d.getTime()
}

/**
 * 将毫秒时间戳转为 "YYYY-MM-DD HH:MM"
 */
function millisToStr(millis) {
  const d = new Date(millis)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * 请求日历读写权限
 * @returns {Promise<boolean>} 是否获得权限
 */
export function requestCalendarPermission() {
  return new Promise((resolve) => {
    // #ifdef APP-PLUS
    try {
      if (!isAndroidCalendarRuntimeAvailable()) {
        resolve(false)
        return
      }

      const { main } = getAndroidResolver()
      const ContextCompat = plus.android.importClass('androidx.core.content.ContextCompat')
      const PackageManager = plus.android.importClass('android.content.pm.PackageManager')

      const readPerm = 'android.permission.READ_CALENDAR'
      const writePerm = 'android.permission.WRITE_CALENDAR'

      const hasRead = ContextCompat.checkSelfPermission(main, readPerm) === PackageManager.PERMISSION_GRANTED
      const hasWrite = ContextCompat.checkSelfPermission(main, writePerm) === PackageManager.PERMISSION_GRANTED

      if (hasRead && hasWrite) {
        resolve(true)
        return
      }

      const permsToRequest = []
      if (!hasRead) permsToRequest.push(readPerm)
      if (!hasWrite) permsToRequest.push(writePerm)

      plus.android.requestPermissions(
        permsToRequest,
        (result) => {
          const grantedLength = result && result.granted ? Number(result.granted.length || 0) : 0
          const granted = grantedLength === permsToRequest.length
          calendarDebugLog('permission result:', { granted, grantedLength })
          resolve(granted)
        },
        (err) => {
          console.error('Calendar permission request failed:', err)
          resolve(false)
        }
      )
    } catch (err) {
      console.error('Calendar permission request failed:', err)
      resolve(false)
    }
    // #endif

    // #ifndef APP-PLUS
    resolve(false)
    // #endif
  })
}

/**
 * 获取默认日历账户 ID
 * @returns {number|null} 日历 ID 或 null
 */
function getCalendarId() {
  // #ifdef APP-PLUS
  const { resolver } = getAndroidResolver()
  const CalendarContract = plus.android.importClass('android.provider.CalendarContract')

  let cursor = null
  try {
    cursor = resolverQuery(
      resolver,
      CalendarContract.Calendars.CONTENT_URI,
      ['_id', 'calendar_displayName', 'calendar_access_level'],
      'calendar_access_level >= 500',
      null,
      null
    )

    if (!cursor) return null
    tryImportClass(cursor)

    let calendarId = null
    if (cursor.moveToFirst()) {
      calendarId = cursor.getLong(0)
    }
    return calendarId
  } catch (err) {
    throw new Error(`读取日历账户失败: ${getCalendarErrorMessage(err)}`)
  } finally {
    safeCloseCursor(cursor)
  }
  // #endif

  // #ifndef APP-PLUS
  return null
  // #endif
}

/**
 * 查询日程
 * @param {Object} params - { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
 * @returns {Object} 查询结果
 */
function getSchedule(params) {
  const { start_date, end_date } = params
  if (!start_date || !end_date) {
    throw new Error('缺少必要参数：start_date, end_date')
  }

  // #ifdef APP-PLUS
  const { resolver } = getAndroidResolver()
  const CalendarContract = plus.android.importClass('android.provider.CalendarContract')

  const startMillis = parseToMillis(`${start_date} 00:00`)
  const endMillis = parseToMillis(`${end_date} 23:59`)

  let cursor = null
  try {
    cursor = resolverQuery(
      resolver,
      CalendarContract.Events.CONTENT_URI,
      ['_id', 'title', 'dtstart', 'dtend', 'description'],
      'dtstart >= ? AND dtstart <= ?',
      [String(startMillis), String(endMillis)],
      'dtstart ASC'
    )

    if (!cursor) {
      throw new Error('未获取到查询游标')
    }
    tryImportClass(cursor)

    const schedules = []
    while (cursor.moveToNext()) {
      const id = String(cursor.getLong(0))
      const title = cursor.getString(1) || ''
      const dtstart = cursor.getLong(2)
      const dtend = cursor.getLong(3)
      const description = cursor.getString(4) || ''

      schedules.push({
        id,
        title,
        start_time: millisToStr(dtstart),
        end_time: dtend ? millisToStr(dtend) : '',
        details: description
      })
    }

    return {
      date_range: `${start_date} 至 ${end_date}`,
      events: schedules,
      count: schedules.length
    }
  } catch (err) {
    throw new Error(`查询日程失败: ${getCalendarErrorMessage(err)}`)
  } finally {
    safeCloseCursor(cursor)
  }
  // #endif

  // #ifndef APP-PLUS
  throw new Error('当前运行环境不支持 Android 日历桥接')
  // #endif
}

/**
 * 添加日程
 * @param {Object} params - { title, start_time, end_time, details }
 * @returns {Object} 添加结果
 */
export function addSchedule(params) {
  const { title, start_time, end_time, details } = params
  if (!title || !start_time || !end_time) {
    throw new Error('缺少必要参数：title, start_time, end_time')
  }

  // #ifdef APP-PLUS
  try {
    const calendarId = getCalendarId()
    if (!calendarId) {
      throw new Error('未找到日历账户，请先在设备上添加一个日历账户')
    }

    const { resolver } = getAndroidResolver()
    const CalendarContract = plus.android.importClass('android.provider.CalendarContract')
    const ContentValues = plus.android.importClass('android.content.ContentValues')
    const TimeZoneClass = plus.android.importClass('java.util.TimeZone')

    const values = new ContentValues()
    values.put('calendar_id', calendarId)
    values.put('title', title)
    values.put('description', details || '')
    values.put('dtstart', parseToMillis(start_time))
    values.put('dtend', parseToMillis(end_time))
    values.put('eventTimezone', TimeZoneClass.getDefault().getID())
    values.put('hasAlarm', 0)

    const uri = resolverInsert(resolver, CalendarContract.Events.CONTENT_URI, values)
    if (!uri) {
      throw new Error('日历事件插入失败')
    }

    tryImportClass(uri)
    let eventId = ''
    try {
      const segmentResult = invokeCompat(uri, 'getLastPathSegment', [])
      eventId = String(segmentResult.value || '')
    } catch (err) {
      calendarDebugLog('read event id failed:', getCalendarErrorMessage(err))
    }

    return {
      id: eventId,
      title,
      start_time,
      end_time,
      details,
      message: `成功添加日程: ${title}`
    }
  } catch (err) {
    throw new Error(`添加日程失败: ${getCalendarErrorMessage(err)}`)
  }
  // #endif

  // #ifndef APP-PLUS
  throw new Error('当前运行环境不支持 Android 日历桥接')
  // #endif
}

/**
 * 删除日程
 * @param {Object} params - { schedule_id }
 * @returns {Object} 删除结果
 */
function deleteSchedule(params) {
  const { schedule_id } = params
  if (!schedule_id) {
    throw new Error('缺少必要参数：schedule_id')
  }

  // #ifdef APP-PLUS
  try {
    const { resolver } = getAndroidResolver()
    const CalendarContract = plus.android.importClass('android.provider.CalendarContract')
    const ContentUris = plus.android.importClass('android.content.ContentUris')

    const deleteUri = ContentUris.withAppendedId(
      CalendarContract.Events.CONTENT_URI,
      parseInt(schedule_id, 10)
    )
    const rows = Number(resolverDelete(resolver, deleteUri, null, null) || 0)

    if (rows === 0) {
      throw new Error(`日程不存在：${schedule_id}`)
    }

    return {
      deleted_id: schedule_id,
      message: `成功删除日程 ${schedule_id}`
    }
  } catch (err) {
    throw new Error(`删除日程失败: ${getCalendarErrorMessage(err)}`)
  }
  // #endif

  // #ifndef APP-PLUS
  throw new Error('当前运行环境不支持 Android 日历桥接')
  // #endif
}

/**
 * 更新日程
 * @param {Object} params - { schedule_id, title?, start_time?, end_time?, details? }
 * @returns {Object} 更新结果
 */
function updateSchedule(params) {
  const { schedule_id, title, start_time, end_time, details } = params
  if (!schedule_id) {
    throw new Error('缺少必要参数：schedule_id')
  }

  // #ifdef APP-PLUS
  try {
    const { resolver } = getAndroidResolver()
    const CalendarContract = plus.android.importClass('android.provider.CalendarContract')
    const ContentUris = plus.android.importClass('android.content.ContentUris')
    const ContentValues = plus.android.importClass('android.content.ContentValues')

    const updateUri = ContentUris.withAppendedId(
      CalendarContract.Events.CONTENT_URI,
      parseInt(schedule_id, 10)
    )

    const values = new ContentValues()
    if (title !== undefined && title !== null) values.put('title', title)
    if (start_time !== undefined && start_time !== null) values.put('dtstart', parseToMillis(start_time))
    if (end_time !== undefined && end_time !== null) values.put('dtend', parseToMillis(end_time))
    if (details !== undefined && details !== null) values.put('description', details)

    const rows = Number(resolverUpdate(resolver, updateUri, values, null, null) || 0)
    if (rows === 0) {
      throw new Error(`日程不存在：${schedule_id}`)
    }

    return {
      updated_id: schedule_id,
      title,
      start_time,
      end_time,
      details,
      message: `成功更新日程 ${schedule_id}`
    }
  } catch (err) {
    throw new Error(`更新日程失败: ${getCalendarErrorMessage(err)}`)
  }
  // #endif

  // #ifndef APP-PLUS
  throw new Error('当前运行环境不支持 Android 日历桥接')
  // #endif
}

/**
 * 统一调度入口 — 根据工具名执行对应日历操作
 * @param {string} toolName - 工具名称
 * @param {Object} params - 工具参数
 * @returns {Promise<{success: boolean, result?: any, error?: string}>}
 */
export async function executeCalendarTool(toolName, params) {
  // 平台检查
  const sysInfo = uni.getSystemInfoSync()
  if (sysInfo.platform !== 'android') {
    return { success: false, error: '当前运行环境不支持 Android 日历桥接' }
  }

  if (!isAndroidCalendarRuntimeAvailable()) {
    return { success: false, error: '当前运行环境不支持 Android 日历桥接' }
  }

  // 请求权限
  const hasPermission = await requestCalendarPermission()
  if (!hasPermission) {
    return { success: false, error: '用户拒绝了日历访问权限' }
  }

  try {
    const handlers = {
      get_schedule: getSchedule,
      add_schedule: addSchedule,
      delete_schedule: deleteSchedule,
      update_schedule: updateSchedule,
    }

    const handler = handlers[toolName]
    if (!handler) {
      return { success: false, error: `未知的日程工具: ${toolName}` }
    }

    calendarDebugLog('execute tool:', {
      toolName,
      hasParams: !!params,
    })

    const result = handler(params || {})
    return { success: true, result }
  } catch (err) {
    const errorMessage = getCalendarErrorMessage(err) || '日历操作失败'
    calendarDebugLog('tool failed:', {
      toolName,
      errorMessage
    })
    console.error(`Calendar tool ${toolName} failed:`, err)
    return { success: false, error: errorMessage }
  }
}
