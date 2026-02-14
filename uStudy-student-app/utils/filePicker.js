function normalizeExtensions(extension) {
  if (!Array.isArray(extension)) return []
  return extension
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .map((ext) => (ext.startsWith('.') ? ext.slice(1) : ext))
}

function getErrorMessage(err) {
  if (!err) return ''
  if (typeof err === 'string') return err
  if (err.errMsg) return String(err.errMsg)
  if (err.message) return String(err.message)
  try {
    return JSON.stringify(err)
  } catch (e) {
    return String(err)
  }
}

function isAppPlusAndroidNativeAvailable() {
  try {
    return (
      typeof plus !== 'undefined' &&
      plus &&
      plus.os &&
      plus.os.name === 'Android' &&
      plus.android &&
      typeof plus.android.runtimeMainActivity === 'function'
    )
  } catch (e) {
    return false
  }
}

function extensionAllowed(filename, extension) {
  if (!filename || !Array.isArray(extension) || extension.length === 0) return true
  const ext = String(filename).split('.').pop()?.toLowerCase()
  if (!ext) return true
  return extension.includes(ext)
}

function getResultCodeOk() {
  // Android Activity.RESULT_OK === -1
  return -1
}

function queryAndroidUriMeta(main, uri) {
  let name = ''
  let size = 0
  let dataPath = ''

  try {
    const resolver = main.getContentResolver()
    plus.android.importClass(resolver)
    const cursor = resolver.query(uri, ['_data', '_display_name', '_size'], null, null, null)
    if (cursor) {
      plus.android.importClass(cursor)
      if (cursor.moveToFirst()) {
        const dataIdx = cursor.getColumnIndex('_data')
        const nameIdx = cursor.getColumnIndex('_display_name')
        const sizeIdx = cursor.getColumnIndex('_size')
        if (dataIdx >= 0) dataPath = cursor.getString(dataIdx) || ''
        if (nameIdx >= 0) name = cursor.getString(nameIdx) || ''
        if (sizeIdx >= 0) {
          try {
            size = Number(cursor.getLong(sizeIdx)) || 0
          } catch (e) {
            size = 0
          }
        }
      }
      cursor.close()
    }
  } catch (e) {
    console.warn('[FilePicker] query uri meta failed:', getErrorMessage(e))
  }

  return { name, size, dataPath }
}

function resolveAndroidUri(main, uri) {
  plus.android.importClass(uri)
  const scheme = String(uri.getScheme() || '').toLowerCase()

  if (scheme === 'file') {
    const path = uri.getPath() || ''
    return {
      path,
      name: getBasename(path, `file_${Date.now()}`),
      size: 0
    }
  }

  const meta = queryAndroidUriMeta(main, uri)
  const path = meta.dataPath || uri.toString()
  const name = meta.name || getBasename(path, `file_${Date.now()}`)

  return {
    path,
    name,
    size: meta.size || 0
  }
}

function pickFilesByNativeAndroid(options = {}) {
  const count = Number(options.count) > 0 ? Number(options.count) : 1
  const extension = normalizeExtensions(options.extension || [])

  return new Promise((resolve, reject) => {
    try {
      if (!isAppPlusAndroidNativeAvailable()) {
        reject({ errMsg: 'chooseFile:fail native android picker unavailable' })
        return
      }

      const main = plus.android.runtimeMainActivity()
      const Intent = plus.android.importClass('android.content.Intent')
      const CODE_REQUEST = 0x5f00 + Math.floor(Math.random() * 0xff)
      const oldOnActivityResult = main.onActivityResult
      let handled = false

      const finish = (type, payload) => {
        if (handled) return
        handled = true
        main.onActivityResult = oldOnActivityResult
        if (type === 'resolve') resolve(payload)
        else reject(payload)
      }

      main.onActivityResult = function(requestCode, resultCode, data) {
        try {
          if (requestCode !== CODE_REQUEST) {
            if (typeof oldOnActivityResult === 'function') {
              oldOnActivityResult(requestCode, resultCode, data)
            }
            return
          }

          if (resultCode !== getResultCodeOk() || !data) {
            finish('reject', { errMsg: 'chooseFile:fail cancel' })
            return
          }

          const files = []
          const clipData = data.getClipData && data.getClipData()
          if (clipData && count > 1) {
            plus.android.importClass(clipData)
            const total = Math.min(Number(clipData.getItemCount()) || 0, count)
            for (let i = 0; i < total; i++) {
              const item = clipData.getItemAt(i)
              if (!item) continue
              const uri = item.getUri()
              if (!uri) continue
              const file = resolveAndroidUri(main, uri)
              if (extensionAllowed(file.name, extension)) {
                files.push(file)
              }
            }
          } else {
            const uri = data.getData && data.getData()
            if (!uri) {
              finish('reject', { errMsg: 'chooseFile:fail invalid uri' })
              return
            }
            const file = resolveAndroidUri(main, uri)
            if (!extensionAllowed(file.name, extension)) {
              finish('reject', { errMsg: 'chooseFile:fail invalid file type' })
              return
            }
            files.push(file)
          }

          if (files.length === 0) {
            finish('reject', { errMsg: 'chooseFile:fail no valid files' })
            return
          }

          finish('resolve', files)
        } catch (e) {
          finish('reject', { errMsg: `chooseFile:fail native parse error: ${getErrorMessage(e)}` })
        }
      }

      const intent = new Intent(Intent.ACTION_GET_CONTENT)
      intent.addCategory(Intent.CATEGORY_OPENABLE)
      intent.setType('*/*')
      if (count > 1) {
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
      }
      const chooser = Intent.createChooser(intent, '选择文件')
      main.startActivityForResult(chooser, CODE_REQUEST)
    } catch (e) {
      reject({ errMsg: `chooseFile:fail native start error: ${getErrorMessage(e)}` })
    }
  })
}

function getBasename(path, fallbackName) {
  if (!path) return fallbackName
  const parts = String(path).split(/[\\/]/)
  const name = parts[parts.length - 1]
  return name || fallbackName
}

function normalizePickedFiles(result) {
  const files = []
  const tempFiles = Array.isArray(result && result.tempFiles) ? result.tempFiles : []
  const tempFilePaths = Array.isArray(result && result.tempFilePaths) ? result.tempFilePaths : []

  if (tempFiles.length > 0) {
    tempFiles.forEach((file, index) => {
      const path = file.path || file.tempFilePath || file.filePath || ''
      const fallbackName = `file_${index + 1}`
      files.push({
        ...file,
        path,
        name: file.name || getBasename(path, fallbackName),
        size: typeof file.size === 'number' ? file.size : 0
      })
    })
    return files
  }

  if (tempFilePaths.length > 0) {
    tempFilePaths.forEach((path, index) => {
      const fallbackName = `file_${index + 1}`
      files.push({
        path,
        name: getBasename(path, fallbackName),
        size: 0
      })
    })
  }

  return files
}

function callPicker(api, options) {
  return new Promise((resolve, reject) => {
    api({
      ...options,
      success: resolve,
      fail: reject
    })
  })
}

export async function chooseLocalFiles(options = {}) {
  const count = Number(options.count) > 0 ? Number(options.count) : 1
  const extension = normalizeExtensions(options.extension || [])

  if (typeof uni === 'undefined') {
    throw new Error('uni is not available')
  }

  console.log('[FilePicker] API availability:', {
    chooseMessageFile: typeof uni.chooseMessageFile === 'function',
    chooseFile: typeof uni.chooseFile === 'function'
  })

  const attempts = []

  if (typeof uni.chooseMessageFile === 'function') {
    attempts.push(() => callPicker(uni.chooseMessageFile, {
      count,
      type: 'file',
      extension
    }))
    attempts.push(() => callPicker(uni.chooseMessageFile, {
      count,
      type: 'file'
    }))
  }

  if (typeof uni.chooseFile === 'function') {
    attempts.push(() => callPicker(uni.chooseFile, {
      count,
      type: 'all',
      extension
    }))
    attempts.push(() => callPicker(uni.chooseFile, {
      count,
      type: 'all'
    }))
  }

  let lastErr = null
  for (const attempt of attempts) {
    try {
      const res = await attempt()
      return normalizePickedFiles(res)
    } catch (err) {
      if (isPickerCancel(err)) {
        throw err
      }
      console.warn('[FilePicker] picker attempt failed:', getErrorMessage(err))
      lastErr = err
    }
  }

  if (isAppPlusAndroidNativeAvailable()) {
    try {
      console.log('[FilePicker] fallback to native Android intent picker')
      const nativeFiles = await pickFilesByNativeAndroid({ count, extension })
      return nativeFiles
    } catch (err) {
      if (isPickerCancel(err)) {
        throw err
      }
      console.warn('[FilePicker] native android picker failed:', getErrorMessage(err))
      lastErr = err
    }
  }

  throw lastErr || { errMsg: 'chooseFile:fail not supported' }
}

export function isPickerCancel(err) {
  const msg = err && err.errMsg ? String(err.errMsg) : ''
  return /cancel/i.test(msg)
}

export function getPickerErrorMessage(err) {
  return getErrorMessage(err)
}
