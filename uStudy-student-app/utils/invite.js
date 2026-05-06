const PENDING_INVITE_KEY = 'ustudy_pending_invite_code'

function safeDecode(value) {
  if (value === undefined || value === null) return ''
  try {
    return decodeURIComponent(String(value).replace(/\+/g, '%20'))
  } catch (_) {
    return String(value)
  }
}

function parseQueryString(raw) {
  const input = String(raw || '').replace(/^[?#]/, '')
  if (!input) return {}
  return input.split('&').reduce((acc, segment) => {
    if (!segment) return acc
    const [rawKey, ...rest] = segment.split('=')
    const key = safeDecode(rawKey)
    if (!key) return acc
    acc[key] = safeDecode(rest.join('='))
    return acc
  }, {})
}

export function normalizeInviteCode(raw) {
  return String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/\s+/g, '')
    .replace(/-/g, '')
    .slice(0, 16)
}

export function extractInviteCode(options = {}) {
  const direct = options.invite_code || options.invite || options.ref || options.code
  if (direct) return normalizeInviteCode(direct)

  // #ifdef H5
  try {
    const searchQuery = parseQueryString(window.location.search)
    const hashQuery = parseQueryString(String(window.location.hash || '').split('?')[1] || '')
    return normalizeInviteCode(
      searchQuery.invite_code ||
      searchQuery.invite ||
      searchQuery.ref ||
      hashQuery.invite_code ||
      hashQuery.invite ||
      hashQuery.ref
    )
  } catch (_) {}
  // #endif

  return ''
}

export function savePendingInviteCode(code) {
  const normalized = normalizeInviteCode(code)
  if (!normalized) return ''
  uni.setStorageSync(PENDING_INVITE_KEY, normalized)
  return normalized
}

export function getPendingInviteCode() {
  return normalizeInviteCode(uni.getStorageSync(PENDING_INVITE_KEY))
}

export function clearPendingInviteCode() {
  uni.removeStorageSync(PENDING_INVITE_KEY)
}

