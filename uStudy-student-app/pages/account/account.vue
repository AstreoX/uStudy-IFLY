<template>
  <view class="account-page" :class="pageThemeClass">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="account-nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">账户</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <!-- Profile Card -->
      <view class="profile-card">
        <view class="avatar-container" @click="handleChangeAvatar">
          <view class="avatar" :style="avatarStyle">
            <image v-if="user?.avatar_url" class="avatar-image" :src="fullAvatarUrl" mode="aspectFill"></image>
            <text v-else class="avatar-text">{{ userInitial }}</text>
          </view>
          <view class="avatar-edit-badge">
            <text class="edit-badge-icon">+</text>
          </view>
        </view>
        <text class="nickname">{{ user?.nickname || '用户' }}</text>
        <text class="email">{{ maskedEmail }}</text>
        <view class="subscription-badge" :class="subscriptionClass">
          <text class="badge-text">{{ subscriptionLabel }}</text>
        </view>
      </view>

      <!-- Account Settings Section -->
      <view class="settings-section">
        <view class="settings-card">
          <view class="settings-item" @click="handleChangeNickname">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit"></image>
            <text class="item-label">修改昵称</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleChangePassword">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/lock.svg" mode="aspectFit"></image>
            <text class="item-label">修改密码</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleSearchSettings">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
            <text class="item-label">搜索设置</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleCalendarSync">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/calendar-check.svg" mode="aspectFit"></image>
            <text class="item-label">同步日历到设备</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleSubscription">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/crown.svg" mode="aspectFit"></image>
            <text class="item-label">订阅管理</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>

      <!-- App Info Section -->
      <view class="info-section">
        <view class="settings-card">
          <view class="settings-item" @click="handleAbout">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/info.svg" mode="aspectFit"></image>
            <text class="item-label">关于 uStudy</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleCheckUpdate">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/arrow-up.svg" mode="aspectFit"></image>
            <text class="item-label">检查更新</text>
            <text class="item-value">v{{ appVersion }}</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleAnnouncements">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/megaphone.svg" mode="aspectFit"></image>
            <text class="item-label">更新公告</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handlePrivacy">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/shield-check.svg" mode="aspectFit"></image>
            <text class="item-label">隐私政策</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>

      <!-- Logout Button -->
      <view class="logout-section">
        <button class="btn logout-btn" @click="handleLogout">
          <text class="logout-text">退出登录</text>
        </button>
      </view>

    </view>

    <!-- 头像选择 Action Sheet -->
    <u-action-sheet
      :visible="showAvatarSheet"
      :items="[
        { text: '从相册选择', icon: 'image' },
        { text: '拍摄照片', icon: 'camera' }
      ]"
      @select="onAvatarSourceSelect"
      @close="showAvatarSheet = false"
    />

    <!-- 修改昵称 Modal -->
    <u-input-modal
      :visible="showNicknameModal"
      title="修改昵称"
      placeholder="请输入新昵称（2-20个字符）"
      :value="nicknameInput"
      :max-length="20"
      :min-length="2"
      :multiline="false"
      @confirm="onNicknameConfirm"
      @close="showNicknameModal = false"
    />

    <!-- 关于信息 Modal -->
    <u-modal
      :visible="showAboutModal"
      title="关于 uStudy"
      :content="aboutContent"
      :show-cancel="false"
      confirm-text="确定"
      @close="showAboutModal = false"
    />

    <!-- 退出登录确认 Modal -->
    <u-modal
      :visible="showLogoutModal"
      title="退出登录"
      content="确定要退出登录吗？"
      confirm-text="退出"
      confirm-type="danger"
      @confirm="doLogout"
      @close="showLogoutModal = false"
    />

    <!-- 更新弹窗 -->
    <update-dialog
      :visible="updateStore.showUpdateDialog"
      :version-name="updateStore.manifest?.latestVersion?.versionName || ''"
      :file-size-mb="updateStore.displayFileSizeMB"
      :is-forced="updateStore.isForced"
      :changelog="updateStore.changelogContent"
      :is-downloading="updateStore.isDownloading"
      :download-progress="updateStore.downloadProgress"
      :download-complete="updateStore.downloadComplete"
      :download-error="updateStore.downloadError"
      :is-wgt-update="updateStore.isWgtUpdate"
      @skip="updateStore.skipThisVersion()"
      @later="updateStore.dismissUpdate()"
      @update="updateStore.startUpdate()"
      @install="updateStore.installUpdate()"
      @browser="updateStore.fallbackToBrowser()"
    />

    <!-- Toast -->
    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />

  </view>
</template>

<script>
import { useUserStore } from '@/store/user'
import { useUpdateStore } from '@/store/update'
import { updateNickname } from '@/api/auth'
import { uploadAvatar } from '@/api/user'
import config from '@/config'
import UModal from '@/components/u-modal/u-modal.vue'
import UActionSheet from '@/components/u-action-sheet/u-action-sheet.vue'
import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import UpdateDialog from '@/components/update-dialog/update-dialog.vue'
import { goBack } from '@/utils/navigation'
import { syncWebCalendarToDevice } from '@/utils/calendarSync'
import { ensureCameraPermission, isPermissionDenied, guideToSettings } from '@/utils/permission'
import { getStoredThemeMode } from '@/utils/themeMode'

export default {
  components: {
    UModal,
    UActionSheet,
    UInputModal,
    UToast,
    UpdateDialog
  },

  data() {
    return {
      homeThemeMode: 'dark',
      avatarGradients: [
        'linear-gradient(135deg, #0F6FFF 0%, #B1DD8B 100%)',
        'linear-gradient(135deg, #A18CD1 0%, #FBC2EB 100%)',
        'linear-gradient(135deg, #FA709A 0%, #FEE140 100%)',
        'linear-gradient(135deg, #84FAB0 0%, #38F9D7 100%)',
        'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      ],
      // 弹窗状态
      showAvatarSheet: false,
      showNicknameModal: false,
      showAboutModal: false,
      showLogoutModal: false,
      // 昵称输入
      nicknameInput: '',
      // Toast 状态
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  created() {
    this.restoreThemeMode()
  },

  onShow() {
    this.restoreThemeMode()
  },

  computed: {
    isLightTheme() {
      return this.homeThemeMode === 'light'
    },

    pageThemeClass() {
      return this.isLightTheme ? 'theme-light' : 'theme-dark'
    },

    updateStore() {
      return useUpdateStore()
    },

    user() {
      const userStore = useUserStore()
      return userStore.user
    },

    userInitial() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      return nickname.charAt(0).toUpperCase()
    },

    avatarGradient() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      const index = nickname.charCodeAt(0) % this.avatarGradients.length
      return this.avatarGradients[index]
    },

    fullAvatarUrl() {
      if (!this.user?.avatar_url) return ''
      if (this.user.avatar_url.startsWith('http')) {
        return this.user.avatar_url
      }
      return `${config.API_BASE_URL}${this.user.avatar_url}`
    },

    avatarStyle() {
      if (this.user?.avatar_url) {
        return {}
      }
      return { background: this.avatarGradient }
    },

    maskedEmail() {
      const email = this.user?.email || ''
      if (!email) return ''
      const atIndex = email.indexOf('@')
      if (atIndex <= 0) return email
      const local = email.substring(0, atIndex)
      const domain = email.substring(atIndex)
      const masked = local.charAt(0) + '***'
      return `${masked}${domain}`
    },

    subscriptionClass() {
      const tier = this.user?.subscription_tier || 'FREE'
      return `badge-${tier.toLowerCase()}`
    },

    subscriptionLabel() {
      const tier = this.user?.subscription_tier || 'FREE'
      const labels = {
        FREE: 'Free',
        BASIC: 'Plus',
        PREMIUM: 'Ultra',
        ALPHA: 'Alpha',
        ULTRA: 'Ultra'
      }
      return labels[tier] || tier
    },

    appVersion() {
      return config.APP_VERSION_NAME
    },

    aboutContent() {
      return `uStudy v${config.APP_VERSION_NAME}\n\n您的智能学习助手`
    }
  },

  methods: {
    restoreThemeMode() {
      this.homeThemeMode = getStoredThemeMode('dark')
      this.syncThemeSystemUi(this.homeThemeMode)
    },

    syncThemeSystemUi(mode) {
      // #ifdef APP-PLUS
      try {
        if (typeof plus !== 'undefined' && plus.navigator) {
          plus.navigator.setStatusBarStyle(mode === 'light' ? 'dark' : 'light')
          if (typeof plus.navigator.setStatusBarBackground === 'function') {
            plus.navigator.setStatusBarBackground(mode === 'light' ? '#F3EDE3' : '#0A0A12')
          }
        }
      } catch (_) {}
      // #endif
    },

    // Toast 辅助方法
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    // 头像选择
    handleChangeAvatar() {
      this.showAvatarSheet = true
    },

    onAvatarSourceSelect(index) {
      const sourceType = index === 0 ? ['album'] : ['camera']
      this.chooseAndUploadImage(sourceType)
    },

    async chooseAndUploadImage(sourceType) {
      try {
        // 拍照时先请求相机权限
        if (sourceType.includes('camera')) {
          const permitted = await ensureCameraPermission()
          if (!permitted) return
        }

        // 选择图片
        const chooseRes = await new Promise((resolve, reject) => {
          uni.chooseImage({
            count: 1,
            sizeType: ['compressed'],
            sourceType,
            success: resolve,
            fail: reject
          })
        })

        const filePath = chooseRes.tempFilePaths[0]

        // 验证文件大小 (< 2MB)
        const fileInfo = await new Promise((resolve) => {
          uni.getFileInfo({
            filePath,
            success: resolve,
            fail: () => resolve({ size: 0 })
          })
        })

        if (fileInfo.size > 2 * 1024 * 1024) {
          this.showCustomToast('图片大小不能超过2MB', 'error')
          return
        }

        uni.showLoading({ title: '上传中...' })

        // 上传图片
        const result = await uploadAvatar(filePath)

        // 更新 store
        const userStore = useUserStore()
        userStore.updateAvatarUrl(result.avatar_url)

        uni.hideLoading()
        this.showCustomToast('头像已更新', 'success')
      } catch (error) {
        uni.hideLoading()
        if (error.errMsg && error.errMsg.includes('cancel')) {
          return // 用户取消，不显示错误
        }
        if (isPermissionDenied(error)) {
          const isCamera = sourceType.includes('camera')
          guideToSettings(
            isCamera ? '需要相机权限' : '需要相册权限',
            isCamera ? '拍照需要相机权限，请在设置中开启' : '选择图片需要访问相册权限，请在设置中开启'
          )
          return
        }
        this.showCustomToast(error.message || '上传失败，请重试', 'error')
      }
    },

    goBack() {
      goBack()
    },

    // 修改昵称
    handleChangeNickname() {
      this.nicknameInput = this.user?.nickname || ''
      this.showNicknameModal = true
    },

    async onNicknameConfirm(newNickname) {
      // 验证长度
      if (newNickname.length < 2 || newNickname.length > 20) {
        this.showCustomToast('昵称长度应为2-20个字符', 'error')
        return
      }

      // 验证字符（允许中文、英文、数字、下划线、连字符）
      const safePattern = /^[\u4e00-\u9fa5a-zA-Z0-9_\-\s]+$/
      if (!safePattern.test(newNickname)) {
        this.showCustomToast('昵称包含非法字符', 'error')
        return
      }

      try {
        await updateNickname(newNickname)
        const userStore = useUserStore()
        userStore.updateNickname(newNickname)
        this.showCustomToast('昵称已更新', 'success')
      } catch (error) {
        this.showCustomToast('昵称更新失败，请重试', 'error')
      }
    },

    handleChangePassword() {
      uni.navigateTo({
        url: '/pages/forgotPassword/forgotPassword'
      })
    },

    handleSearchSettings() {
      uni.navigateTo({ url: '/pages/searchSettings/searchSettings' })
    },

    async handleCalendarSync() {
      // #ifndef APP-PLUS
      this.showCustomToast('日历同步仅支持 Android 设备', 'info')
      return
      // #endif

      // #ifdef APP-PLUS
      try {
        uni.showLoading({ title: '正在同步日历...' })
        const result = await syncWebCalendarToDevice((current, total, title) => {
          uni.showLoading({ title: `同步中 ${current}/${total}` })
        })
        uni.hideLoading()

        if (result.total === 0) {
          this.showCustomToast('未找到日历事件', 'info')
        } else if (result.synced === 0 && result.failed === 0) {
          this.showCustomToast('所有日历事件已同步，无需操作', 'success')
        } else if (result.failed === 0) {
          this.showCustomToast(`成功同步 ${result.synced} 个事件`, 'success')
        } else {
          this.showCustomToast(`同步 ${result.synced} 个，失败 ${result.failed} 个`, 'error')
        }
      } catch (err) {
        uni.hideLoading()
        this.showCustomToast(err.message || '日历同步失败', 'error')
      }
      // #endif
    },

    handleSubscription() {
      uni.navigateTo({ url: '/pages/subscription/subscription' })
    },

    // 关于弹窗
    handleAbout() {
      this.showAboutModal = true
    },

    async handleCheckUpdate() {
      uni.showLoading({ title: '检查中...' })
      try {
        const updateStore = useUpdateStore()
        const hasUpdate = await updateStore.checkForUpdatesManual()
        uni.hideLoading()
        if (!hasUpdate) {
          this.showCustomToast('已是最新版本', 'success')
        }
      } catch (_) {
        uni.hideLoading()
        this.showCustomToast('检查更新失败，请稍后重试', 'error')
      }
    },

    handleAnnouncements() {
      uni.navigateTo({
        url: '/pages/announcementHistory/announcementHistory'
      })
    },

    handlePrivacy() {
      this.showCustomToast('即将推出', 'info')
    },

    // 退出登录
    handleLogout() {
      this.showLogoutModal = true
    },

    doLogout() {
      const userStore = useUserStore()
      userStore.clear()
      uni.reLaunch({
        url: '/pages/login/login'
      })
    }
  }
}
</script>

<style>
.account-page {
  --account-page-bg: #0A0A12;
  --account-aurora-blue-core: #1A6AFF;
  --account-aurora-blue-mid: rgba(26, 106, 255, 0.3);
  --account-aurora-orange-core: #FF6A1A;
  --account-aurora-orange-mid: rgba(255, 106, 26, 0.3);
  --account-aurora-blend-core: #FF9F45;
  --account-aurora-blend-mid: rgba(255, 159, 69, 0.15);
  --account-nav-btn-bg: rgba(255, 255, 255, 0.06);
  --account-nav-btn-border: rgba(255, 255, 255, 0.1);
  --account-nav-btn-outline: rgba(255, 255, 255, 0.04);
  --account-nav-title: #ffffff;
  --account-icon-filter: brightness(0) invert(1);
  --account-surface: rgba(255, 255, 255, 0.08);
  --account-surface-fallback: rgba(80, 80, 95, 0.65);
  --account-surface-pressed: rgba(255, 255, 255, 0.05);
  --account-border: rgba(255, 255, 255, 0.15);
  --account-border-soft: rgba(255, 255, 255, 0.1);
  --account-text-primary: #ffffff;
  --account-text-secondary: rgba(255, 255, 255, 0.6);
  --account-text-muted: rgba(255, 255, 255, 0.35);
  --account-avatar-edit-bg: rgba(0, 122, 255, 0.9);
  --account-avatar-edit-border: #0A0A12;
  --account-badge-free-bg: rgba(255, 255, 255, 0.1);
  --account-badge-free-text: rgba(255, 255, 255, 0.6);
  --account-badge-basic-bg: rgba(0, 122, 255, 0.2);
  --account-badge-basic-text: #007AFF;
  --account-badge-premium-bg: rgba(147, 51, 234, 0.2);
  --account-badge-premium-text: #A855F7;
  --account-badge-alpha-bg: rgba(255, 255, 255, 0.1);
  --account-badge-alpha-text: rgba(255, 255, 255, 0.6);
  --account-badge-ultra-bg: rgba(147, 51, 234, 0.2);
  --account-badge-ultra-text: #A855F7;
  --account-danger-bg: rgba(239, 68, 68, 0.15);
  --account-danger-border: rgba(239, 68, 68, 0.3);
  --account-danger-text: #EF4444;
  --account-nav-btn-highlight: rgba(255, 255, 255, 0.08);
  --account-nav-btn-shadow: rgba(0, 0, 0, 0.25);
  --account-shadow: rgba(0, 0, 0, 0.3);
  --account-avatar-text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.2);
  --account-avatar-edit-icon: #ffffff;
  width: 100%;
  min-height: 100vh;
  background-color: var(--account-page-bg);
  position: relative;
  overflow: hidden;
}

.account-page.theme-light {
  --account-page-bg: #F3EDE3;
  --account-aurora-blue-core: #9AB9FF;
  --account-aurora-blue-mid: rgba(154, 185, 255, 0.24);
  --account-aurora-orange-core: #F5BB73;
  --account-aurora-orange-mid: rgba(245, 187, 115, 0.22);
  --account-aurora-blend-core: #FFD08C;
  --account-aurora-blend-mid: rgba(255, 208, 140, 0.16);
  --account-nav-btn-bg: rgba(255, 255, 255, 0.82);
  --account-nav-btn-border: rgba(63, 53, 42, 0.1);
  --account-nav-btn-outline: rgba(63, 53, 42, 0.04);
  --account-nav-title: #1F1A16;
  --account-icon-filter: brightness(0) saturate(100%);
  --account-surface: rgba(255, 255, 255, 0.84);
  --account-surface-fallback: rgba(255, 249, 241, 0.96);
  --account-surface-pressed: rgba(63, 53, 42, 0.05);
  --account-border: rgba(63, 53, 42, 0.12);
  --account-border-soft: rgba(63, 53, 42, 0.1);
  --account-text-primary: #1F1A16;
  --account-text-secondary: rgba(31, 26, 22, 0.64);
  --account-text-muted: rgba(31, 26, 22, 0.42);
  --account-avatar-edit-bg: #2F6EEA;
  --account-avatar-edit-border: #F3EDE3;
  --account-badge-free-bg: rgba(63, 53, 42, 0.08);
  --account-badge-free-text: rgba(63, 53, 42, 0.72);
  --account-badge-basic-bg: rgba(47, 110, 234, 0.14);
  --account-badge-basic-text: #2F6EEA;
  --account-badge-premium-bg: rgba(124, 58, 237, 0.14);
  --account-badge-premium-text: #7C3AED;
  --account-badge-alpha-bg: rgba(63, 53, 42, 0.08);
  --account-badge-alpha-text: rgba(63, 53, 42, 0.72);
  --account-badge-ultra-bg: rgba(124, 58, 237, 0.14);
  --account-badge-ultra-text: #7C3AED;
  --account-danger-bg: rgba(209, 79, 79, 0.12);
  --account-danger-border: rgba(209, 79, 79, 0.22);
  --account-danger-text: #D14F4F;
  --account-nav-btn-highlight: rgba(255, 255, 255, 0.68);
  --account-nav-btn-shadow: rgba(118, 101, 80, 0.14);
  --account-shadow: rgba(118, 101, 80, 0.18);
  --account-avatar-text-shadow: 0 2rpx 8rpx rgba(118, 101, 80, 0.12);
  --account-avatar-edit-icon: #ffffff;
}

/* Aurora Background (Blue-Orange) */
.aurora-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120rpx);
  will-change: transform, opacity;
}

/* 蓝色光晕 - 左上 */
.aurora-blob-1 {
  width: 900rpx;
  height: 900rpx;
  background: radial-gradient(circle, var(--account-aurora-blue-core) 0%, var(--account-aurora-blue-mid) 40%, transparent 70%);
  top: -250rpx;
  left: -200rpx;
  animation: aurora-blue 14s ease-in-out infinite;
}

/* 橙色光晕 - 右下 */
.aurora-blob-2 {
  width: 850rpx;
  height: 850rpx;
  background: radial-gradient(circle, var(--account-aurora-orange-core) 0%, var(--account-aurora-orange-mid) 40%, transparent 70%);
  bottom: -200rpx;
  right: -200rpx;
  animation: aurora-orange 16s ease-in-out infinite;
}

/* 过渡融合 - 中部 */
.aurora-blob-3 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, var(--account-aurora-blend-core) 0%, var(--account-aurora-blend-mid) 40%, transparent 70%);
  top: 40%;
  left: 25%;
  animation: aurora-blend 18s ease-in-out infinite;
}

@keyframes aurora-blue {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.55; }
  33% { transform: translate(60rpx, 80rpx) scale(1.15); opacity: 0.7; }
  66% { transform: translate(-30rpx, 40rpx) scale(1.05); opacity: 0.6; }
}

@keyframes aurora-orange {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
  33% { transform: translate(-70rpx, -60rpx) scale(1.1); opacity: 0.65; }
  66% { transform: translate(40rpx, -80rpx) scale(1.2); opacity: 0.55; }
}

@keyframes aurora-blend {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.2; }
  50% { transform: translate(50rpx, -40rpx) scale(1.3); opacity: 0.35; }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
}

/* Navigation Bar */
.account-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: var(--account-nav-btn-bg);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid var(--account-nav-btn-border);
  outline: 1rpx solid var(--account-nav-btn-outline);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx var(--account-nav-btn-highlight),
    0 2rpx 12rpx var(--account-nav-btn-shadow);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-left {
    background: var(--account-surface-fallback);
  }
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: var(--account-icon-filter);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--account-nav-title);
}

/* Content Area */
.content-area {
  position: relative;
  z-index: 1;
  width: 100%;
  padding-top: calc(100vh * 3.5 / 26);
  padding-bottom: calc(48rpx + env(safe-area-inset-bottom));
}

/* Profile Card */
.profile-card {
  margin: 0 calc(100vw / 24);
  padding: 40rpx 30rpx;
  background: var(--account-surface);
  border: 1rpx solid var(--account-border);
  border-radius: 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .profile-card {
    background: var(--account-surface-fallback);
  }
}

.avatar-container {
  position: relative;
  margin-bottom: 20rpx;
}

.avatar {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 8rpx 32rpx var(--account-shadow);
  overflow: hidden;
}

.avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.avatar-text {
  font-size: 64rpx;
  font-weight: 700;
  color: var(--account-text-primary);
  text-shadow: var(--account-avatar-text-shadow);
}

.avatar-edit-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 48rpx;
  height: 48rpx;
  background: var(--account-avatar-edit-bg);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3rpx solid var(--account-avatar-edit-border);
  box-shadow: 0 2rpx 8rpx var(--account-shadow);
}

.edit-badge-icon {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--account-avatar-edit-icon);
  line-height: 1;
}

.nickname {
  font-size: 40rpx;
  font-weight: 600;
  color: var(--account-text-primary);
  margin-bottom: 8rpx;
}

.email {
  font-size: 28rpx;
  color: var(--account-text-secondary);
  margin-bottom: 20rpx;
}

.subscription-badge {
  padding: 8rpx 24rpx;
  border-radius: 20rpx;
}

.badge-free {
  background: var(--account-badge-free-bg);
}

.badge-free .badge-text {
  color: var(--account-badge-free-text);
}

.badge-basic {
  background: var(--account-badge-basic-bg);
}

.badge-basic .badge-text {
  color: var(--account-badge-basic-text);
}

.badge-premium {
  background: var(--account-badge-premium-bg);
}

.badge-premium .badge-text {
  color: var(--account-badge-premium-text);
}

.badge-alpha {
  background: var(--account-badge-alpha-bg);
}

.badge-alpha .badge-text {
  color: var(--account-badge-alpha-text);
}

.badge-ultra {
  background: var(--account-badge-ultra-bg);
}

.badge-ultra .badge-text {
  color: var(--account-badge-ultra-text);
}

.badge-text {
  font-size: 24rpx;
  font-weight: 500;
}

/* Settings Section */
.settings-section {
  margin: 32rpx calc(100vw / 24) 0;
}

.info-section {
  margin: 32rpx calc(100vw / 24) 0;
}

.settings-card {
  background: var(--account-surface);
  border: 1rpx solid var(--account-border);
  border-radius: 24rpx;
  overflow: hidden;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .settings-card {
    background: var(--account-surface-fallback);
  }
}

.settings-item {
  display: flex;
  align-items: center;
  padding: 32rpx;
}

.settings-item:active {
  background: var(--account-surface-pressed);
}

.item-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 24rpx;
  filter: var(--account-icon-filter);
}

.item-label {
  flex: 1;
  font-size: 32rpx;
  color: var(--account-text-primary);
}

.item-value {
  font-size: 26rpx;
  color: var(--account-text-muted);
  margin-right: 8rpx;
}

.item-arrow {
  width: 32rpx;
  height: 32rpx;
  filter: var(--account-icon-filter);
  opacity: 0.4;
}

.settings-divider {
  height: 1rpx;
  background: var(--account-border-soft);
  margin-left: 100rpx;
}

/* Logout Section */
.logout-section {
  margin: 48rpx calc(100vw / 24) 0;
}

.btn {
  width: 100%;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  transition: opacity 0.2s ease, transform 0.15s ease;
}

.btn::after {
  border: none;
}

.btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

.logout-btn {
  background-color: var(--account-danger-bg);
  border: 1rpx solid var(--account-danger-border);
}

.logout-text {
  font-size: 34rpx;
  font-weight: 500;
  color: var(--account-danger-text);
}

</style>
