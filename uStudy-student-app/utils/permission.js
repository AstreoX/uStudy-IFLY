/**
 * 权限检查与请求工具
 * 统一处理 Android / iOS 运行时权限，拒绝后引导用户前往系统设置
 */

/**
 * 检查 Android 权限是否已授予
 * @param {string} permission - 完整权限名，如 'android.permission.CAMERA'
 * @returns {boolean}
 */
function isAndroidPermissionGranted(permission) {
	try {
		const main = plus.android.runtimeMainActivity()
		const ContextCompat = plus.android.importClass('androidx.core.content.ContextCompat')
		return ContextCompat.checkSelfPermission(main, permission) === 0
	} catch (e) {
		return false
	}
}

/**
 * 请求 Android 权限
 * @param {string[]} permissions
 * @returns {Promise<{granted: boolean}>}
 */
function requestAndroidPermissions(permissions) {
	return new Promise((resolve) => {
		plus.android.requestPermissions(
			permissions,
			(result) => {
				const granted = result && result.granted && result.granted.length > 0
				resolve({ granted })
			},
			() => {
				resolve({ granted: false })
			}
		)
	})
}

/**
 * 弹窗引导用户前往系统设置开启权限
 * @param {string} title - 弹窗标题，如 "需要相册权限"
 * @param {string} content - 弹窗描述
 */
export function guideToSettings(title, content) {
	uni.showModal({
		title,
		content,
		confirmText: '去设置',
		success: (res) => {
			if (res.confirm) {
				// #ifdef APP-PLUS
				if (plus.os.name === 'iOS') {
					plus.runtime.openURL('app-settings:')
				} else {
					const Intent = plus.android.importClass('android.content.Intent')
					const Settings = plus.android.importClass('android.provider.Settings')
					const Uri = plus.android.importClass('android.net.Uri')
					const main = plus.android.runtimeMainActivity()
					const intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
					intent.setData(Uri.parse('package:' + main.getPackageName()))
					main.startActivity(intent)
				}
				// #endif
				// #ifndef APP-PLUS
				uni.openSetting()
				// #endif
			}
		}
	})
}

/**
 * 判断错误信息是否属于权限拒绝
 * @param {object|string} err
 * @returns {boolean}
 */
export function isPermissionDenied(err) {
	const msg = typeof err === 'string' ? err : (err?.errMsg || err?.message || '')
	return /deny|denied|authorize|permission|权限/i.test(msg)
}

/**
 * 确保相册写入权限（保存图片前调用）
 * @returns {Promise<boolean>} true = 权限已授予
 */
export async function ensureAlbumWritePermission() {
	// #ifdef APP-PLUS
	if (plus.os.name === 'Android') {
		const Build = plus.android.importClass('android.os.Build')
		const sdk = Build.VERSION.SDK_INT

		// Android 13+ 用 READ_MEDIA_IMAGES；更低版本用 WRITE_EXTERNAL_STORAGE
		const perm = sdk >= 33
			? 'android.permission.READ_MEDIA_IMAGES'
			: 'android.permission.WRITE_EXTERNAL_STORAGE'

		if (isAndroidPermissionGranted(perm)) return true

		const result = await requestAndroidPermissions([perm])
		if (!result.granted) {
			guideToSettings('需要存储权限', '保存图片需要访问相册权限，请在设置中开启')
			return false
		}
		return true
	}
	// iOS: saveImageToPhotosAlbum 会自动弹权限，失败后引导即可
	return true
	// #endif
	// #ifndef APP-PLUS
	return true
	// #endif
}

/**
 * 确保相机权限（拍照前调用）
 * @returns {Promise<boolean>} true = 权限已授予
 */
export async function ensureCameraPermission() {
	// #ifdef APP-PLUS
	if (plus.os.name === 'Android') {
		const perm = 'android.permission.CAMERA'
		if (isAndroidPermissionGranted(perm)) return true

		const result = await requestAndroidPermissions([perm])
		if (!result.granted) {
			guideToSettings('需要相机权限', '拍照需要相机权限，请在设置中开启')
			return false
		}
		return true
	}
	return true
	// #endif
	// #ifndef APP-PLUS
	return true
	// #endif
}

/**
 * 确保通知权限（Android 13+）
 * @returns {Promise<boolean>}
 */
export async function ensureNotificationPermission() {
	// #ifdef APP-PLUS
	if (plus.os.name === 'Android') {
		const Build = plus.android.importClass('android.os.Build')
		if (Build.VERSION.SDK_INT < 33) return true

		const perm = 'android.permission.POST_NOTIFICATIONS'
		if (isAndroidPermissionGranted(perm)) return true

		const result = await requestAndroidPermissions([perm])
		if (!result.granted) {
			guideToSettings('需要通知权限', '开启通知权限后才能收到消息提醒，请在设置中开启')
			return false
		}
		return true
	}
	return true
	// #endif
	// #ifndef APP-PLUS
	return true
	// #endif
}
