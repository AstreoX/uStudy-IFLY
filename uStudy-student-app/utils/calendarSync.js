import { requestCalendarPermission, addSchedule } from '@/utils/calendar'
import { getCalendarEvents, updateCalendarEvent } from '@/api/calendarEvents'

/**
 * Format ISO datetime string to "YYYY-MM-DD HH:MM" in local timezone
 */
function isoToLocalStr(isoString) {
  const d = new Date(isoString)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * Sync web calendar events (from backend DB) to Android system calendar.
 * Only syncs events that don't yet have an external_id (not already on device).
 *
 * @param {Function} onProgress - callback(current, total, title)
 * @returns {Promise<{synced: number, failed: number, skipped: number, total: number, errors: string[]}>}
 */
export async function syncWebCalendarToDevice(onProgress) {
  // Platform check
  // #ifndef APP-PLUS
  throw new Error('日历同步仅支持 Android 设备')
  // #endif

  // #ifdef APP-PLUS
  const hasPermission = await requestCalendarPermission()
  if (!hasPermission) {
    throw new Error('用户拒绝了日历访问权限')
  }

  const now = new Date()
  const past30 = new Date(now.getTime() - 30 * 86400000).toISOString()
  const future365 = new Date(now.getTime() + 365 * 86400000).toISOString()

  const events = await getCalendarEvents(past30, future365)
  const allEvents = events || []
  const toSync = allEvents.filter(e => !e.external_id)

  const result = { synced: 0, failed: 0, skipped: allEvents.length - toSync.length, total: allEvents.length, errors: [] }

  for (let i = 0; i < toSync.length; i++) {
    const ev = toSync[i]
    if (onProgress) onProgress(i + 1, toSync.length, ev.title)

    try {
      const scheduleResult = addSchedule({
        title: ev.title,
        start_time: isoToLocalStr(ev.start_time),
        end_time: isoToLocalStr(ev.end_time),
        details: ev.details || ''
      })

      const deviceEventId = scheduleResult?.id
      if (deviceEventId) {
        try {
          await updateCalendarEvent(ev.id, { external_id: String(deviceEventId) })
        } catch (_) {
          // best-effort: device calendar is primary
        }
      }
      result.synced++
    } catch (err) {
      result.failed++
      result.errors.push(`${ev.title}: ${err.message || err}`)
    }
  }

  return result
  // #endif
}
