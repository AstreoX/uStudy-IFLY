import config from '@/config'

const { GITEE_RAW_BASE } = config

export function getCurrentVersionCode() {
  // #ifdef APP-PLUS
  return Number(plus.runtime.versionCode) || 0
  // #endif
  // #ifndef APP-PLUS
  return 0
  // #endif
}

export function getCurrentVersionName() {
  // #ifdef APP-PLUS
  return plus.runtime.version || '0.0.0'
  // #endif
  // #ifndef APP-PLUS
  return '0.0.0'
  // #endif
}

export function isUpdateAvailable(manifest) {
  if (!manifest || !manifest.latestVersion) return false
  const current = getCurrentVersionCode()
  return manifest.latestVersion.versionCode > current
}

export function isForceUpdate(manifest) {
  if (!manifest || !manifest.latestVersion) return false
  const current = getCurrentVersionCode()
  const latest = manifest.latestVersion
  if (latest.forceUpdate) return true
  if (latest.forceUpdateBelow && current < latest.forceUpdateBelow) return true
  return false
}

export function getDownloadUrl(manifest) {
  if (!manifest || !manifest.latestVersion) return null
  const relative = manifest.latestVersion.downloadUrl?.android
  if (!relative) return null
  return `${GITEE_RAW_BASE}/${relative}`
}

export function getBrowserDownloadUrl(manifest) {
  if (!manifest || !manifest.latestVersion) return null
  return manifest.latestVersion.browserDownloadUrl?.android || null
}

export function downloadApk(url, onProgress) {
  return new Promise((resolve, reject) => {
    // #ifdef APP-PLUS
    const task = plus.downloader.createDownload(url, {
      filename: '_downloads/uStudy-update.apk'
    }, (download, status) => {
      if (status === 200) {
        resolve(download.filename)
      } else {
        reject(new Error(`Download failed: ${status}`))
      }
    })

    task.addEventListener('statechanged', (download) => {
      if (download.state === 3 && download.totalSize > 0) {
        const progress = Math.round((download.downloadedSize / download.totalSize) * 100)
        if (onProgress) onProgress(progress)
      }
    })

    task.start()
    // #endif

    // #ifndef APP-PLUS
    reject(new Error('Download not supported on this platform'))
    // #endif
  })
}

export function installApk(filePath) {
  // #ifdef APP-PLUS
  plus.runtime.install(filePath, { force: true }, () => {
    plus.runtime.restart()
  }, (err) => {
    throw new Error(err.message || 'Install failed')
  })
  // #endif
}

export function openInBrowser(url) {
  // #ifdef APP-PLUS
  plus.runtime.openURL(url)
  // #endif

  // #ifndef APP-PLUS
  window.open(url, '_blank')
  // #endif
}
