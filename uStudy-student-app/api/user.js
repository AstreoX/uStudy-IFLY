/**
 * 用户相关 API
 */
import config from '@/config'
import { getTokens } from '@/utils/storage'
import { ensureFreshToken } from '@/utils/request'

const { API_BASE_URL } = config

function doUpload(filePath, token) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${API_BASE_URL}/api/upload/avatar`,
      filePath,
      name: 'file',
      header: {
        Authorization: `Bearer ${token}`
      },
      success: (res) => {
        if (res.statusCode === 200) {
          try {
            resolve(JSON.parse(res.data))
          } catch {
            reject(new Error('响应解析失败'))
          }
        } else if (res.statusCode === 401) {
          reject({ statusCode: 401 })
        } else {
          try {
            const error = JSON.parse(res.data)
            reject(new Error(error.detail || '上传失败'))
          } catch {
            reject(new Error('上传失败'))
          }
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

/**
 * 上传用户头像
 * @param {string} filePath - 图片文件路径
 * @returns {Promise<{success: boolean, avatar_url: string}>}
 */
export async function uploadAvatar(filePath) {
  const tokens = getTokens()
  const token = tokens?.access_token
  try {
    return await doUpload(filePath, token)
  } catch (err) {
    if (err?.statusCode === 401) {
      const newToken = await ensureFreshToken()
      return await doUpload(filePath, newToken)
    }
    throw err
  }
}
