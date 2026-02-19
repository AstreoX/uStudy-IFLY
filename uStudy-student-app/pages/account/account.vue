<template>
  <view class="account-page">
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
import { updateNickname } from '@/api/auth'
import { uploadAvatar } from '@/api/user'
import config from '@/config'
import UModal from '@/components/u-modal/u-modal.vue'
import UActionSheet from '@/components/u-action-sheet/u-action-sheet.vue'
import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import { goBack } from '@/utils/navigation'

export default {
  components: {
    UModal,
    UActionSheet,
    UInputModal,
    UToast
  },

  data() {
    return {
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

  computed: {
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
        BASIC: 'Basic',
        PREMIUM: 'Premium',
        ALPHA: 'Alpha'
      }
      return labels[tier] || tier
    },

    aboutContent() {
      return `uStudy v${config.APP_VERSION_NAME}\n\n您的智能学习助手`
    }
  },

  methods: {
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

    handleSubscription() {
      this.showCustomToast('即将推出', 'info')
    },

    // 关于弹窗
    handleAbout() {
      this.showAboutModal = true
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
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A12;
  position: relative;
  overflow: hidden;
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
  background: radial-gradient(circle, #1A6AFF 0%, rgba(26, 106, 255, 0.3) 40%, transparent 70%);
  top: -250rpx;
  left: -200rpx;
  animation: aurora-blue 14s ease-in-out infinite;
}

/* 橙色光晕 - 右下 */
.aurora-blob-2 {
  width: 850rpx;
  height: 850rpx;
  background: radial-gradient(circle, #FF6A1A 0%, rgba(255, 106, 26, 0.3) 40%, transparent 70%);
  bottom: -200rpx;
  right: -200rpx;
  animation: aurora-orange 16s ease-in-out infinite;
}

/* 过渡融合 - 中部 */
.aurora-blob-3 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, #FF9F45 0%, rgba(255, 159, 69, 0.15) 40%, transparent 70%);
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
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-left {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
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
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .profile-card {
    background: rgba(80, 80, 95, 0.65);
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
  box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.3);
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
  color: #ffffff;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.2);
}

.avatar-edit-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 48rpx;
  height: 48rpx;
  background: rgba(0, 122, 255, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3rpx solid #0A0A12;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
}

.edit-badge-icon {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
  line-height: 1;
}

.nickname {
  font-size: 40rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 8rpx;
}

.email {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 20rpx;
}

.subscription-badge {
  padding: 8rpx 24rpx;
  border-radius: 20rpx;
}

.badge-free {
  background: rgba(255, 255, 255, 0.1);
}

.badge-free .badge-text {
  color: rgba(255, 255, 255, 0.6);
}

.badge-basic {
  background: rgba(0, 122, 255, 0.2);
}

.badge-basic .badge-text {
  color: #007AFF;
}

.badge-premium {
  background: rgba(255, 215, 0, 0.2);
}

.badge-premium .badge-text {
  color: #FFD700;
}

.badge-alpha {
  background: rgba(255, 255, 255, 0.1);
}

.badge-alpha .badge-text {
  color: rgba(255, 255, 255, 0.6);
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
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  overflow: hidden;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .settings-card {
    background: rgba(80, 80, 95, 0.65);
  }
}

.settings-item {
  display: flex;
  align-items: center;
  padding: 32rpx;
}

.settings-item:active {
  background: rgba(255, 255, 255, 0.05);
}

.item-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 24rpx;
  filter: brightness(0) invert(1);
}

.item-label {
  flex: 1;
  font-size: 32rpx;
  color: #ffffff;
}

.item-arrow {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
}

.settings-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.1);
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
  background-color: rgba(239, 68, 68, 0.15);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
}

.logout-text {
  font-size: 34rpx;
  font-weight: 500;
  color: #EF4444;
}

</style>
