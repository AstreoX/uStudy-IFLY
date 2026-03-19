import config from '@/config'

const { GITEE_RAW_BASE } = config

export function getCurrentVersionCode() {
  return config.APP_VERSION_CODE || 0
}

export function getCurrentVersionName() {
  return config.APP_VERSION_NAME || '0.0.0'
}

export function isUpdateAvailable(manifest) {
  if (!manifest || !manifest.latestVersion) return false
  // #ifdef APP-PLUS
  const info = uni.getSystemInfoSync()
  if (info.platform === 'ios') return false
  // #endif
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
  const browser = manifest.latestVersion.browserDownloadUrl?.android
  if (browser) return browser
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
    let settled = false

    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true
        try { task.abort() } catch (e) { /* ignore */ }
        reject(new Error('下载超时'))
      }
    }, 60000)

    const task = plus.downloader.createDownload(url, {
      filename: '_downloads/uStudy-update.apk'
    }, (download, status) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      if (status === 200) {
        resolve(download.filename)
      } else {
        reject(new Error(`下载失败 (HTTP ${status})`))
      }
    })

    task.addEventListener('statechanged', (download) => {
      if (settled) return
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
  return new Promise((resolve, reject) => {
    // #ifdef APP-PLUS
    plus.runtime.install(filePath, { force: true }, () => {
      resolve()
      plus.runtime.restart()
    }, (err) => {
      reject(new Error(err.message || 'Install failed'))
    })
    // #endif

    // #ifndef APP-PLUS
    reject(new Error('Install not supported on this platform'))
    // #endif
  })
}

export function getNativeVersionCode() {
  return config.NATIVE_VERSION_CODE || 0
}

export function canUseWgtUpdate(manifest) {
  if (!manifest || !manifest.latestVersion) return false
  const latest = manifest.latestVersion
  if (!latest.wgtUrl) return false
  if (!latest.minNativeVersionCode) return false
  return getNativeVersionCode() >= latest.minNativeVersionCode
}

export function getWgtDownloadUrl(manifest) {
  if (!manifest || !manifest.latestVersion) return null
  const relative = manifest.latestVersion.wgtUrl
  if (!relative) return null
  return `${GITEE_RAW_BASE}/${relative}`
}

export function downloadWgt(url, onProgress) {
  return new Promise((resolve, reject) => {
    // #ifdef APP-PLUS
    let settled = false

    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true
        try { task.abort() } catch (e) { /* ignore */ }
        reject(new Error('下载超时'))
      }
    }, 60000)

    const task = plus.downloader.createDownload(url, {
      filename: '_downloads/uStudy-update.wgt'
    }, (download, status) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      if (status === 200) {
        resolve(download.filename)
      } else {
        reject(new Error(`下载失败 (HTTP ${status})`))
      }
    })

    task.addEventListener('statechanged', (download) => {
      if (settled) return
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

export function installWgt(filePath) {
  return new Promise((resolve, reject) => {
    // #ifdef APP-PLUS
    plus.runtime.install(filePath, { force: true }, () => {
      resolve()
      plus.runtime.restart()
    }, (err) => {
      reject(new Error(err.message || 'WGT install failed'))
    })
    // #endif

    // #ifndef APP-PLUS
    reject(new Error('Install not supported on this platform'))
    // #endif
  })
}

export function openInBrowser(url) {
  // #ifdef APP-PLUS
  plus.runtime.openURL(url)
  // #endif

  // #ifndef APP-PLUS
  window.open(url, '_blank')
  // #endif
}
