import config from '@/config'
import { getTokens } from './storage'

const {
  PENDING_NAVIGATION_KEY,
  APP_SCHEME
} = config

const LOGIN_URL = '/pages/login/login'
const HOME_URL = '/pages/index/index'
const QUIZ_URL = '/pages/test/test'
const QUIZ_RESULT_URL = '/pages/testResult/testResult'
const ANNOUNCEMENT_URL = '/pages/announcementHistory/announcementHistory'
const AUTH_ROUTE_SET = new Set([
  'pages/login/login',
  'pages/emailLogin/emailLogin',
  'pages/register/register'
])
const PENDING_TTL_MS = 30 * 60 * 1000

let lastLaunchSignature = ''

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function safeDecode(value) {
  if (value === undefined || value === null) return ''
  const normalized = String(value).replace(/\+/g, '%20')
  try {
    return decodeURIComponent(normalized)
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

function encodeQuery(query = {}) {
  const entries = Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== '')
  if (!entries.length) return ''
  return entries.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`).join('&')
}

function normalizeInternalUrl(url) {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (raw.startsWith('/')) return raw
  if (raw.startsWith('pages/')) return `/${raw}`
  return raw
}

function createTarget(url, options = {}) {
  return {
    url: normalizeInternalUrl(url),
    requireAuth: options.requireAuth !== false,
    openType: options.openType || 'navigateTo'
  }
}

function buildQuizTarget(quizId, options = {}) {
  const normalized = String(quizId || '').trim()
  if (!normalized) return null
  return createTarget(
    `${QUIZ_URL}?quizId=${encodeURIComponent(normalized)}`,
    options
  )
}

function buildQuizResultTarget(quizId, options = {}) {
  const normalized = String(quizId || '').trim()
  if (!normalized) return null
  const query = encodeQuery({
    quizId: normalized,
    fromList: options.fromList === false ? undefined : 'true'
  })
  return createTarget(`${QUIZ_RESULT_URL}?${query}`, options)
}

function extractQuizId(source) {
  if (!source) return ''
  return String(
    source.quizId ||
    source.quiz_id ||
    source.id ||
    ''
  ).trim()
}

function parseMaybeJson(raw) {
  const text = String(raw || '').trim()
  if (!text) return null
  if (!(text.startsWith('{') || text.startsWith('['))) return null
  try {
    return JSON.parse(text)
  } catch (_) {
    return null
  }
}

function buildUrlFromRouteAndQuery(route, query = {}) {
  const normalizedRoute = normalizeInternalUrl(route)
  if (!normalizedRoute) return ''
  const queryString = encodeQuery(query)
  return queryString ? `${normalizedRoute}?${queryString}` : normalizedRoute
}

function parseRouteTarget(route, query = {}, options = {}) {
  const normalizedRoute = normalizeInternalUrl(route)
  const normalizedQuery = isPlainObject(query) ? query : {}

  if (normalizedQuery.quizId || normalizedQuery.quiz_id) {
    const targetBuilder = normalizedRoute.includes(QUIZ_RESULT_URL)
      ? buildQuizResultTarget
      : buildQuizTarget
    return targetBuilder(
      normalizedQuery.quizId || normalizedQuery.quiz_id,
      options
    )
  }

  if (normalizedRoute === ANNOUNCEMENT_URL) {
    return createTarget(ANNOUNCEMENT_URL, options)
  }

  if (!normalizedRoute.startsWith('/pages/')) return null
  if (AUTH_ROUTE_SET.has(normalizedRoute.replace(/^\//, ''))) return null
  return createTarget(buildUrlFromRouteAndQuery(normalizedRoute, normalizedQuery), options)
}

function resolveFromQuery(query = {}, options = {}) {
  const normalizedQuery = isPlainObject(query) ? query : {}

  const kind = String(normalizedQuery.target || normalizedQuery.kind || '').toLowerCase()
  if (kind === 'quiz_result' || kind === 'result') {
    return buildQuizResultTarget(
      normalizedQuery.quizId || normalizedQuery.quiz_id,
      options
    )
  }
  if (kind === 'quiz' || normalizedQuery.quizId || normalizedQuery.quiz_id) {
    return buildQuizTarget(
      normalizedQuery.quizId || normalizedQuery.quiz_id,
      options
    )
  }
  return null
}

function resolveFromUrl(rawUrl, options = {}) {
  const text = String(rawUrl || '').trim()
  if (!text) return null

  try {
    const url = new URL(text)
    const query = Object.fromEntries(url.searchParams.entries())
    const hash = String(url.hash || '')
    const routeKey = [url.hostname, url.pathname]
      .join('/')
      .replace(/\/+/g, '/')
      .replace(/^\/|\/$/g, '')
      .toLowerCase()

    if (hash.startsWith('#/')) {
      const [hashPath, hashQueryString] = hash.slice(1).split('?')
      const hashQuery = parseQueryString(hashQueryString || '')
      const hashTarget = parseRouteTarget(hashPath, hashQuery, options)
      if (hashTarget) return hashTarget
      const fallbackHashTarget = resolveFromQuery(hashQuery, options)
      if (fallbackHashTarget) return fallbackHashTarget
    }

    const scheme = url.protocol.replace(':', '').toLowerCase()
    if (scheme === APP_SCHEME) {
      if (routeKey.includes('quiz-result') || routeKey.includes('result')) {
        return buildQuizResultTarget(query.quizId || query.quiz_id, options)
      }
      if (routeKey.includes('quiz') || query.quizId || query.quiz_id) {
        return buildQuizTarget(query.quizId || query.quiz_id, options)
      }
    }

    const routeTarget = parseRouteTarget(url.pathname, query, options)
    if (routeTarget) return routeTarget

    return resolveFromQuery(query, options)
  } catch (_) {
    const rawQueryTarget = resolveFromQuery(parseQueryString(text), options)
    if (rawQueryTarget) return rawQueryTarget
    return null
  }
}

function shouldSkipDuplicateLaunch(signature, force = false) {
  if (!signature) return false
  if (!force && signature === lastLaunchSignature) {
    return true
  }
  lastLaunchSignature = signature
  return false
}

export function savePendingNavigation(target) {
  const normalized = target?.url ? createTarget(target.url, target) : null
  if (!normalized?.url) return
  uni.setStorageSync(PENDING_NAVIGATION_KEY, JSON.stringify({
    ...normalized,
    savedAt: Date.now()
  }))
}

export function getPendingNavigation() {
  try {
    const raw = uni.getStorageSync(PENDING_NAVIGATION_KEY)
    if (!raw) return null
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!parsed?.url || !parsed?.savedAt) return null
    if (Date.now() - Number(parsed.savedAt) > PENDING_TTL_MS) {
      clearPendingNavigation()
      return null
    }
    return createTarget(parsed.url, parsed)
  } catch (_) {
    return null
  }
}

export function clearPendingNavigation() {
  uni.removeStorageSync(PENDING_NAVIGATION_KEY)
}

export function clearPendingNavigationIfMatches(url) {
  const pending = getPendingNavigation()
  if (!pending?.url) return
  if (normalizeInternalUrl(pending.url) === normalizeInternalUrl(url)) {
    clearPendingNavigation()
  }
}

export function consumePendingNavigation() {
  const target = getPendingNavigation()
  clearPendingNavigation()
  return target
}

export function getCurrentPageNavigationTarget() {
  try {
    const pages = getCurrentPages()
    const currentPage = pages[pages.length - 1]
    if (!currentPage?.route) return null
    if (AUTH_ROUTE_SET.has(currentPage.route)) return null
    return parseRouteTarget(currentPage.route, currentPage.options || {}, { openType: 'reLaunch' })
  } catch (_) {
    return null
  }
}

export function redirectToLogin(options = {}) {
  if (options.saveCurrentPage && !getPendingNavigation()) {
    const currentTarget = getCurrentPageNavigationTarget()
    if (currentTarget) {
      savePendingNavigation(currentTarget)
    }
  }
  uni.reLaunch({ url: LOGIN_URL })
}

export function navigateToTarget(target, options = {}) {
  const normalized = target?.url ? createTarget(target.url, target) : null
  if (!normalized?.url) return false

  const replace = options.replace ?? normalized.openType === 'reLaunch'
  const delayMs = options.delayMs ?? 0
  const tokens = getTokens()

  if (normalized.requireAuth && !tokens?.access_token) {
    savePendingNavigation({ ...normalized, openType: 'reLaunch' })
    redirectToLogin()
    return false
  }

  const executor = () => {
    if (replace) {
      uni.reLaunch({ url: normalized.url })
      return
    }
    uni.navigateTo({
      url: normalized.url,
      fail: () => {
        uni.reLaunch({ url: normalized.url })
      }
    })
  }

  if (delayMs > 0) {
    setTimeout(executor, delayMs)
  } else {
    executor()
  }
  return true
}

export function resolveNotificationTarget(payload) {
  const source = isPlainObject(payload?.data) ? { ...payload, ...payload.data } : (payload || {})
  const notificationType = String(source.type || '').toLowerCase()
  const action = String(source.action || '').toLowerCase()

  if (notificationType === 'quiz_evaluation') {
    return buildQuizResultTarget(extractQuizId(source), { openType: 'navigateTo' })
  }

  if (
    action === 'start_quiz' ||
    notificationType === 'review_quiz_ready'
  ) {
    return buildQuizTarget(extractQuizId(source), { openType: 'navigateTo' })
  }

  if (action === 'go_review') {
    return createTarget(HOME_URL, { openType: 'reLaunch' })
  }

  if (notificationType === 'system_announcement') {
    return createTarget(ANNOUNCEMENT_URL, { openType: 'navigateTo' })
  }

  const conversationId = String(source.conversationId || source.conversation_id || '').trim()
  if (!conversationId) return null

  const chatMode = String(source.chatMode || source.chat_mode || '').toLowerCase()
  if (chatMode === 'quick_chat') {
    return createTarget(
      `/pages/quickChat/quickChat?conversationId=${encodeURIComponent(conversationId)}`,
      { openType: 'navigateTo' }
    )
  }

  return createTarget(
    buildUrlFromRouteAndQuery('/pages/spaceChat/spaceChat', {
      conversationId,
      spaceId: source.spaceId || source.space_id,
      spaceTitle: source.spaceTitle || source.space_title
    }),
    { openType: 'navigateTo' }
  )
}

export function resolveAppLaunchTarget(options = {}) {
  const launchQueryTarget = resolveFromQuery(options.launchOptions?.query, { openType: 'reLaunch' })
  if (launchQueryTarget) return launchQueryTarget

  const launchPathTarget = parseRouteTarget(
    options.launchOptions?.path,
    options.launchOptions?.query,
    { openType: 'reLaunch' }
  )
  if (launchPathTarget) return launchPathTarget

  const runtimeArgs = String(options.runtimeArguments || '').trim()
  if (!runtimeArgs) return null

  const signature = `${options.launcher || ''}::${runtimeArgs}`
  if (shouldSkipDuplicateLaunch(signature, options.force)) {
    return null
  }

  const parsedJson = parseMaybeJson(runtimeArgs)
  if (parsedJson) {
    const notificationTarget = resolveNotificationTarget(parsedJson)
    if (notificationTarget) return { ...notificationTarget, openType: 'reLaunch' }

    const directTarget = resolveFromQuery(parsedJson, { openType: 'reLaunch' })
    if (directTarget) return directTarget
  }

  return resolveFromUrl(runtimeArgs, { openType: 'reLaunch' })
}
