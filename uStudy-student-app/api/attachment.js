import { getTokens } from '@/utils/storage'
import config from '@/config'

const { API_BASE_URL } = config

/**
 * 上传附件（图片或文件）
 * @param {string} filePath - 文件本地路径
 * @param {Function} onProgress - 上传进度回调 (progress: 0-100)
 * @returns {Promise<Object>} AttachmentResponse
 */
export function uploadAttachment(filePath, onProgress) {
  return new Promise((resolve, reject) => {
    const token = getTokens()?.access_token
    if (!token) {
      reject(new Error('未登录'))
      return
    }

    const uploadTask = uni.uploadFile({
      url: `${API_BASE_URL}/api/attachments/upload`,
      filePath: filePath,
      name: 'file',
      header: {
        Authorization: `Bearer ${token}`
      },
      success: (res) => {
        if (res.statusCode === 200) {
          try {
            const result = JSON.parse(res.data)
            if (result.success && result.attachment) {
              // 🔧 修复: 转换URL为完整路径
              const attachment = result.attachment
              attachment.file_url = getAttachmentUrl(attachment.file_url)
              if (attachment.thumbnail_url) {
                attachment.thumbnail_url = getAttachmentUrl(attachment.thumbnail_url)
              }
              resolve(attachment)
            } else {
              reject(new Error(result.message || '上传失败'))
            }
          } catch (e) {
            reject(new Error('解析响应失败'))
          }
        } else if (res.statusCode === 400) {
          try {
            const error = JSON.parse(res.data)
            reject(new Error(error.detail || '文件验证失败'))
          } catch (e) {
            reject(new Error('上传失败'))
          }
        } else {
          reject(new Error(`上传失败 (${res.statusCode})`))
        }
      },
      fail: (err) => {
        console.error('Upload failed:', err)
        reject(new Error(err.errMsg || '网络错误'))
      }
    })

    // 监听上传进度
    if (onProgress) {
      uploadTask.onProgressUpdate((progress) => {
        onProgress(progress.progress)
      })
    }
  })
}

/**
 * 删除孤儿附件（未关联到消息的附件）
 * @param {string} attachmentId - 附件ID
 * @returns {Promise<void>}
 */
export function deleteAttachment(attachmentId) {
  return new Promise((resolve, reject) => {
    const token = getTokens()?.access_token
    if (!token) {
      reject(new Error('未登录'))
      return
    }

    uni.request({
      url: `${API_BASE_URL}/api/attachments/${attachmentId}`,
      method: 'DELETE',
      header: {
        Authorization: `Bearer ${token}`
      },
      success: (res) => {
        if (res.statusCode === 204) {
          resolve()
        } else if (res.statusCode === 400) {
          reject(new Error(res.data?.detail || '无法删除已关联的附件'))
        } else if (res.statusCode === 404) {
          reject(new Error('附件不存在'))
        } else if (res.statusCode === 403) {
          reject(new Error('无权删除此附件'))
        } else {
          reject(new Error(`删除失败 (${res.statusCode})`))
        }
      },
      fail: (err) => {
        console.error('Delete attachment failed:', err)
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的大小 (如 "1.5 MB")
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

/**
 * 将后端返回的相对路径转换为完整URL
 * @param {string} relativePath - 相对路径 (如 /uploads/attachments/images/xxx.webp)
 * @returns {string} 完整URL (如 http://localhost:8000/uploads/...)
 */
export function getAttachmentUrl(relativePath) {
  if (!relativePath) return ''

  // 如果已经是完整URL,直接返回
  if (relativePath.startsWith('http://') || relativePath.startsWith('https://')) {
    return relativePath
  }

  // 拼接API_BASE_URL
  return `${API_BASE_URL}${relativePath}`
}
