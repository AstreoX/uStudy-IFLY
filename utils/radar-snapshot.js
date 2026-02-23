const STORAGE_KEY = 'radar_weekly_snapshot'

function getMonday(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  const day = d.getDay()
  const diff = day === 0 ? 6 : day - 1
  d.setDate(d.getDate() - diff)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

function readStorage() {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (raw && typeof raw === 'object') return raw
    return null
  } catch (_e) {
    return null
  }
}

function writeStorage(data) {
  try {
    uni.setStorageSync(STORAGE_KEY, data)
  } catch (_e) {
    // Storage write failed silently
  }
}

export function saveRadarSnapshot(values) {
  if (!Array.isArray(values) || values.length === 0) return

  const thisMonday = getMonday(new Date())
  const stored = readStorage()

  if (!stored) {
    writeStorage({
      currentWeekStart: thisMonday,
      currentValues: [...values],
      lastWeekStart: null,
      lastWeekValues: null
    })
    return
  }

  if (stored.currentWeekStart < thisMonday) {
    writeStorage({
      currentWeekStart: thisMonday,
      currentValues: [...values],
      lastWeekStart: stored.currentWeekStart,
      lastWeekValues: stored.currentValues ? [...stored.currentValues] : null
    })
  } else {
    writeStorage({
      ...stored,
      currentValues: [...values]
    })
  }
}

export function getLastWeekSnapshot() {
  const stored = readStorage()
  if (!stored || !stored.lastWeekValues || !stored.lastWeekStart) return null

  const thisMonday = getMonday(new Date())
  const expectedLastMonday = getMonday(
    new Date(new Date(thisMonday).getTime() - 7 * 24 * 60 * 60 * 1000)
  )

  if (stored.lastWeekStart !== expectedLastMonday) return null

  return [...stored.lastWeekValues]
}
