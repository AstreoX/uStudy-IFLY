import { getUser } from '@/utils/storage'

export const TEACHER_SPACE_TOOLS = Object.freeze({
  DASHBOARD: 'dashboard',
  ASSIGNMENTS: 'assignments',
  PRESENTATIONS: 'presentations'
})

const STORAGE_PREFIX = 'ustudy_teacher_space'
const TEACHER_SPACE_ROLES = new Set(['owner', 'teacher'])

function normalizedId(value) {
  return value === undefined || value === null ? '' : String(value).trim()
}

function currentUserId(explicitUserId = '') {
  const userId = normalizedId(explicitUserId)
  if (userId) return userId
  return normalizedId(getUser()?.id)
}

function storageKey(tool, userId = '') {
  const ownerId = currentUserId(userId)
  if (!ownerId || !tool) return ''
  return `${STORAGE_PREFIX}:${tool}:${ownerId}`
}

export function isTeacherSpace(space) {
  const role = String(space?.user_role || '').trim().toLowerCase()
  return !!normalizedId(space?.id) && TEACHER_SPACE_ROLES.has(role)
}

export function getTeacherSpaces(spaces) {
  return Array.isArray(spaces)
    ? spaces.filter(isTeacherSpace)
    : []
}

export function readRememberedTeacherSpace(tool, userId = '') {
  const key = storageKey(tool, userId)
  if (!key) return ''
  try {
    return normalizedId(uni.getStorageSync(key))
  } catch (_) {
    return ''
  }
}

export function rememberTeacherSpace(tool, spaceId, userId = '') {
  const key = storageKey(tool, userId)
  const value = normalizedId(spaceId)
  if (!key || !value) return
  try {
    uni.setStorageSync(key, value)
  } catch (_) {}
}

export function resolveTeacherSpace({ spaces, requestedSpaceId, tool, userId = '' }) {
  const available = getTeacherSpaces(spaces)
  const requestedId = normalizedId(requestedSpaceId)
  const rememberedId = readRememberedTeacherSpace(tool, userId)
  const byId = id => available.find(space => normalizedId(space.id) === id) || null

  const requested = requestedId ? byId(requestedId) : null
  const remembered = rememberedId ? byId(rememberedId) : null
  const space = requested || remembered || available[0] || null

  if (space) rememberTeacherSpace(tool, space.id, userId)

  return {
    space,
    spaces: available,
    invalidRequested: !!requestedId && !requested,
    shouldCanonicalize: !!space && requestedId !== normalizedId(space.id)
  }
}
