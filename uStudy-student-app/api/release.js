import config from '@/config'

const { GITEE_RAW_BASE } = config

function giteeGet(url) {
  return new Promise((resolve, reject) => {
    uni.request({
      url,
      method: 'GET',
      timeout: 10000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || 'Network error'))
      }
    })
  })
}

export function fetchReleaseManifest() {
  const url = `${GITEE_RAW_BASE}/release.json?t=${Date.now()}`
  return giteeGet(url)
}

export function fetchMarkdownContent(relativePath) {
  const url = `${GITEE_RAW_BASE}/${relativePath}?t=${Date.now()}`
  return giteeGet(url)
}
