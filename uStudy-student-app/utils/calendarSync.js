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

  console.log('[CalendarSync] Fetching events from API...', { past30, future365 })
  const events = await getCalendarEvents(past30, future365)
  console.log('[CalendarSync] API returned:', JSON.stringify(events).substring(0, 500))

  const allEvents = Array.isArray(events) ? events : []
  const toSync = allEvents.filter(e => !e.external_id)

  console.log('[CalendarSync] Total events:', allEvents.length, 'To sync:', toSync.length, 'Already synced:', allEvents.length - toSync.length)

  const result = { synced: 0, failed: 0, skipped: allEvents.length - toSync.length, total: allEvents.length, errors: [] }

  for (let i = 0; i < toSync.length; i++) {
    const ev = toSync[i]
    if (onProgress) onProgress(i + 1, toSync.length, ev.title)

    const localStart = isoToLocalStr(ev.start_time)
    const localEnd = isoToLocalStr(ev.end_time)
    console.log(`[CalendarSync] [${i + 1}/${toSync.length}] "${ev.title}" | ${ev.start_time} -> ${localStart} | ${ev.end_time} -> ${localEnd}`)

    try {
      const scheduleResult = addSchedule({
        title: ev.title,
        start_time: localStart,
        end_time: localEnd,
        details: ev.details || ''
      })

      console.log(`[CalendarSync] addSchedule result:`, JSON.stringify(scheduleResult))

      const deviceEventId = scheduleResult?.id
      if (deviceEventId) {
        try {
          await updateCalendarEvent(ev.id, { external_id: String(deviceEventId) })
          console.log(`[CalendarSync] external_id written back: ${deviceEventId}`)
        } catch (backErr) {
          console.warn('[CalendarSync] external_id writeback failed:', backErr)
        }
      } else {
        console.warn('[CalendarSync] addSchedule returned no id, external_id not written back')
      }
      result.synced++
    } catch (err) {
      console.error(`[CalendarSync] Failed to sync "${ev.title}":`, err)
      result.failed++
      result.errors.push(`${ev.title}: ${err.message || err}`)
    }
  }

  console.log('[CalendarSync] Done:', JSON.stringify(result))
  return result
  // #endif
}
