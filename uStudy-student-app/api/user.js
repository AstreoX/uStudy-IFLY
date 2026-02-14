/**
 * 用户相关 API
 */
import config from '@/config'
import { getTokens } from '@/utils/storage'

const { API_BASE_URL } = config

/**
 * 上传用户头像
 * @param {string} filePath - 图片文件路径
 * @returns {Promise<{success: boolean, avatar_url: string}>}
 */
export function uploadAvatar(filePath) {
  const tokens = getTokens()

  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${API_BASE_URL}/api/upload/avatar`,
      filePath,
      name: 'file',
      header: {
        Authorization: `Bearer ${tokens?.access_token}`
      },
      success: (res) => {
        if (res.statusCode === 200) {
          try {
            const data = JSON.parse(res.data)
            resolve(data)
          } catch {
            reject(new Error('响应解析失败'))
          }
        } else if (res.statusCode === 401) {
          reject(new Error('请重新登录'))
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
