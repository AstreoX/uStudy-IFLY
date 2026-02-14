import config from '@/config'
import { getTokens, setTokens, clearAuth } from './storage'

const { API_BASE_URL } = config

let isRefreshing = false
let refreshSubscribers = []
let requestSeq = 0

function extractErrorMessage(payload) {
  if (!payload) return ''
  if (typeof payload === 'string') return payload
  return payload.detail || payload.message || payload.msg || payload.error || ''
}

function resolveUrl(url) {
  if (url.startsWith('http')) {
    return url
  }
  return `${API_BASE_URL}${url}`
}

function rawRequest(options) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: resolveUrl(options.url),
      method: options.method || 'GET',
      data: options.data || {},
      header: options.header || {},
      timeout: options.timeout || 10000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject({
            statusCode: res.statusCode,
            data: res.data,
            message: extractErrorMessage(res.data) || `请求失败(${res.statusCode})`
          })
        }
      },
      fail: (err) => {
        reject({
          statusCode: 0,
          data: err,
          message: err?.errMsg || '网络请求失败，请检查网络连接'
        })
      }
    })
  })
}

function onRefreshed(token) {
  refreshSubscribers.forEach((callback) => callback(token))
  refreshSubscribers = []
}

function addRefreshSubscriber(callback) {
  refreshSubscribers.push(callback)
}

async function refreshAccessToken() {
  const tokens = getTokens()
  if (!tokens || !tokens.refresh_token) {
    throw new Error('No refresh token')
  }

  const data = await rawRequest({
    url: '/api/auth/refresh',
    method: 'POST',
    data: { refresh_token: tokens.refresh_token },
    header: { 'Content-Type': 'application/json' }
  })

  setTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token
  })

  return data.access_token
}

function retryRequest(options, token) {
  return request({
    ...options,
    header: {
      ...(options.header || {}),
      Authorization: `Bearer ${token}`
    },
    skipRefresh: true
  })
}

export function request(options) {
  const tokens = getTokens()
  const requestId = ++requestSeq
  const method = options.method || 'GET'
  const startAt = Date.now()
  const headers = {
    'Content-Type': 'application/json',
    ...(options.header || {})
  }

  // 开发环境调试日志
  // #ifdef H5 || APP-PLUS
  console.log(`[Request:${requestId}] ->`, method, options.url, {
    hasAccessToken: !!tokens?.access_token,
    hasRefreshToken: !!tokens?.refresh_token,
    skipAuth: !!options.skipAuth
  })
  // #endif

  if (!options.skipAuth && tokens && tokens.access_token) {
    headers.Authorization = `Bearer ${tokens.access_token}`
  }

  return new Promise((resolve, reject) => {
    rawRequest({
      ...options,
      header: headers
    })
      .then((data) => {
        // #ifdef H5 || APP-PLUS
        console.log(`[Request:${requestId}] <-`, method, options.url, {
          status: 'ok',
          elapsedMs: Date.now() - startAt
        })
        // #endif
        resolve(data)
      })
      .catch(async (err) => {
        // #ifdef H5 || APP-PLUS
        console.log(`[Request:${requestId}] xx`, method, options.url, {
          statusCode: err?.statusCode || 0,
          elapsedMs: Date.now() - startAt,
          message: err?.message || '',
          data: err?.data
        })
        // #endif

        if (
          err.statusCode === 401 &&
          !options.skipRefresh &&
          tokens &&
          tokens.refresh_token
        ) {
          // #ifdef H5
          console.log('[Request] 401 detected, attempting token refresh...')
          // #endif

          try {
            if (!isRefreshing) {
              isRefreshing = true
              const newToken = await refreshAccessToken()
              isRefreshing = false
              onRefreshed(newToken)
              // #ifdef H5
              console.log('[Request] Token refreshed, retrying request...')
              // #endif
              const result = await retryRequest(options, newToken)
              resolve(result)
              return
            }

            const result = await new Promise((innerResolve, innerReject) => {
              addRefreshSubscriber((token) => {
                retryRequest(options, token).then(innerResolve).catch(innerReject)
              })
            })
            resolve(result)
            return
          } catch (refreshError) {
            // #ifdef H5
            console.log('[Request] Token refresh failed, redirecting to login...')
            // #endif
            isRefreshing = false
            refreshSubscribers = []
            clearAuth()
            uni.reLaunch({
              url: '/pages/login/login'
            })
            reject(refreshError)
            return
          }
        }

        if (err.statusCode === 0 && !err.message) {
          err.message = err?.data?.errMsg || '网络连接失败，请稍后重试'
        }

        reject(err)
      })
  })
}
