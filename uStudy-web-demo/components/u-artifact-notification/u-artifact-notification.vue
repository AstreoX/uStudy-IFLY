<template>
  <view
    v-if="visible"
    class="artifact-notification"
    :class="{ 'notification-enter': animationVisible, 'notification-failed': isFailed }"
    :style="positionStyle"
    @mouseenter="pauseDismiss"
    @mouseleave="resumeDismiss"
    @tap="handleClick"
  >
    <view class="notification-content">
      <view class="notification-icon-wrap">
        <image
          class="notification-icon"
          mode="aspectFit"
          :src="isFailed
            ? '/static/icons/phosphor/regular/x-circle-white.svg'
            : '/static/icons/phosphor/regular/check-circle-white.svg'"
        />
      </view>
      <view class="notification-text">
        <text class="notification-title">{{ titleText }}</text>
        <text class="notification-sub">{{ subText }}</text>
      </view>
      <view class="notification-close" @tap.stop="handleClose">
        <text class="notification-close-icon">&times;</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'UArtifactNotification',
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '' },
    status: { type: String, default: 'done' },
    errorMessage: { type: String, default: '' },
    duration: { type: Number, default: 10000 },
    index: { type: Number, default: 0 }
  },

  emits: ['close', 'click'],

  data() {
    return {
      animationVisible: false,
      dismissTimer: null,
      remainingTime: 0,
      pausedAt: 0
    }
  },

  computed: {
    isFailed() {
      return this.status === 'failed'
    },
    titleText() {
      if (this.isFailed) return '生成失败'
      return '交互演示已生成'
    },
    subText() {
      const name = this.title || '交互演示'
      if (this.isFailed) return `${this.errorMessage || name} - 点击查看`
      return `${name} - 点击查看`
    },
    positionStyle() {
      return {
        bottom: `${24 + this.index * 76}px`
      }
    }
  },

  watch: {
    visible(val) {
      if (val) {
        this.startToast()
      } else {
        this.clearDismiss()
      }
    }
  },

  mounted() {
    if (this.visible) {
      this.startToast()
    }
  },

  beforeUnmount() {
    this.clearDismiss()
  },

  methods: {
    startToast() {
      this.animationVisible = false
      this.remainingTime = this.duration
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this.animationVisible = true
        })
      })
      this.scheduleDismiss(this.duration)
    },

    scheduleDismiss(delay) {
      this.clearDismiss()
      this.pausedAt = Date.now()
      this.dismissTimer = setTimeout(() => {
        this.$emit('close')
      }, delay)
    },

    clearDismiss() {
      if (this.dismissTimer) {
        clearTimeout(this.dismissTimer)
        this.dismissTimer = null
      }
    },

    pauseDismiss() {
      if (this.dismissTimer) {
        const elapsed = Date.now() - this.pausedAt
        this.remainingTime = Math.max(0, this.remainingTime - elapsed)
        this.clearDismiss()
      }
    },

    resumeDismiss() {
      if (this.remainingTime > 0) {
        this.scheduleDismiss(this.remainingTime)
      }
    },

    handleClick() {
      this.$emit('click')
    },

    handleClose() {
      this.$emit('close')
    }
  }
}
</script>

<style scoped>
.artifact-notification {
  position: fixed;
  right: 24px;
  z-index: 999;
  min-width: 280px;
  max-width: 380px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.25);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  cursor: pointer;
  opacity: 0;
  transform: translateX(100%) scale(0.95);
  transition: opacity 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  user-select: none;
}

.artifact-notification.notification-failed {
  border-color: rgba(255, 50, 66, 0.3);
}

.artifact-notification.notification-enter {
  opacity: 1;
  transform: translateX(0) scale(1);
}

.notification-content {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
}

.notification-icon-wrap {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.15);
}

.notification-failed .notification-icon-wrap {
  background: rgba(255, 50, 66, 0.15);
}

.notification-icon {
  width: 18px;
  height: 18px;
  opacity: 0.9;
}

.notification-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.notification-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(138, 180, 248, 0.95);
  line-height: 1.3;
}

.notification-failed .notification-title {
  color: #FF3242;
}

.notification-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notification-close {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}

.notification-close:hover {
  background: rgba(255, 255, 255, 0.1);
}

.notification-close-icon {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1;
}
</style>
