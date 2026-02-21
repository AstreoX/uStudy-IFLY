<template>
  <view class="activation-page">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <view class="content-card">
      <text class="title">激活内测资格</text>
      <text class="subtitle">使用激活码开通 Alpha 权限</text>

      <view class="status-row">
        <text class="status-label">当前状态</text>
        <text class="status-value" :class="{ active: isActivated }">
          {{ isActivated ? '已激活' : '未激活' }}
        </text>
      </view>

      <view v-if="isActivated && user?.subscription_expires_at" class="expiry-row">
        <text class="expiry-label">到期时间</text>
        <text class="expiry-value">{{ formatTime(user.subscription_expires_at) }}</text>
      </view>

      <view class="actions">
        <button
          v-if="!isActivated"
          class="activate-btn"
          @tap="showActivationModal = true"
        >
          输入激活码
        </button>
        <button class="home-btn" @tap="goHome">返回首页</button>
      </view>
    </view>

    <ActivationModal
      :visible="showActivationModal"
      :mandatory="false"
      @success="handleActivationSuccess"
      @cancel="showActivationModal = false"
      @close="showActivationModal = false"
    />
  </view>
</template>

<script>
import ActivationModal from '@/components/activation-modal/activation-modal.vue'
import { getMe } from '@/api/auth'
import { useUserStore } from '@/store/user'
import { getTokens } from '@/utils/storage'

export default {
  components: {
    ActivationModal
  },
  data() {
    return {
      user: null,
      showActivationModal: false
    }
  },
  computed: {
    isActivated() {
      const tier = this.user?.subscription_tier
      return typeof tier === 'string' && tier.toUpperCase() === 'ALPHA'
    }
  },
  onShow() {
    this.loadUser()
  },
  methods: {
    async loadUser() {
      const tokens = getTokens()
      if (!tokens || !tokens.access_token) {
        uni.reLaunch({ url: '/pages/login/login' })
        return
      }

      try {
        const user = await getMe()
        this.user = user
        const userStore = useUserStore()
        userStore.setUser(user)
      } catch (error) {
        this.user = null
      }
    },
    handleActivationSuccess(response) {
      const userStore = useUserStore()
      userStore.updateSubscription(
        response.subscription_tier,
        response.subscription_expires_at
      )
      this.user = {
        ...(this.user || {}),
        subscription_tier: response.subscription_tier,
        subscription_expires_at: response.subscription_expires_at
      }
      this.showActivationModal = false
      uni.showToast({
        title: '激活成功',
        icon: 'none'
      })
    },
    formatTime(value) {
      if (!value) return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      const yyyy = date.getFullYear()
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      const dd = String(date.getDate()).padStart(2, '0')
      const hh = String(date.getHours()).padStart(2, '0')
      const min = String(date.getMinutes()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd} ${hh}:${min}`
    },
    goHome() {
      uni.reLaunch({
        url: '/pages/index/index'
      })
    }
  }
}
</script>

<style scoped>
.activation-page {
  min-height: 100vh;
  background: #0a0a12;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  box-sizing: border-box;
}

.aurora-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 760px;
  height: 760px;
  top: -25%;
  left: -10%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, rgba(59, 130, 246, 0.1) 45%, transparent 75%);
}

.aurora-blob-2 {
  width: 680px;
  height: 680px;
  bottom: -25%;
  right: -10%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(249, 115, 22, 0.22) 0%, rgba(249, 115, 22, 0.08) 45%, transparent 75%);
}

.aurora-blob-3 {
  width: 560px;
  height: 560px;
  top: 20%;
  left: 40%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(79, 70, 229, 0.2) 0%, rgba(79, 70, 229, 0.08) 45%, transparent 75%);
}

.content-card {
  width: 100%;
  max-width: 520px;
  position: relative;
  z-index: 1;
  padding: 28px;
  border-radius: 20px;
  background: rgba(18, 18, 28, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.title {
  font-size: 30px;
  line-height: 1.2;
  font-weight: 700;
  color: #fff;
  display: block;
}

.subtitle {
  margin-top: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  display: block;
}

.status-row,
.expiry-row {
  margin-top: 20px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.status-label,
.expiry-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.status-value,
.expiry-value {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}

.status-value.active {
  color: #34d399;
}

.actions {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.activate-btn,
.home-btn {
  height: 42px;
  border-radius: 10px;
  border: none;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.activate-btn::after,
.home-btn::after {
  border: none;
}

.activate-btn {
  background: linear-gradient(135deg, #0088ff 0%, #0066dd 100%);
}

.home-btn {
  background: rgba(255, 255, 255, 0.12);
}
</style>
