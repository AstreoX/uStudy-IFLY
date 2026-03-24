<template>
  <view v-if="visible" class="u-toast-wrapper">
    <view class="u-toast-container" :class="[themeClass, typeClass, { 'toast-show': animationVisible }]">
      <!-- Icon -->
      <view v-if="showIcon" class="u-toast-icon">
        <image v-if="type === 'success'" class="icon-image" src="/static/icons/phosphor-icons/SVGs/regular/check-circle.svg" mode="aspectFit"></image>
        <image v-else-if="type === 'error'" class="icon-image" src="/static/icons/phosphor-icons/SVGs/regular/x-circle.svg" mode="aspectFit"></image>
        <image v-else class="icon-image" src="/static/icons/phosphor-icons/SVGs/regular/info.svg" mode="aspectFit"></image>
      </view>
      <!-- Message -->
      <text class="u-toast-message">{{ message }}</text>
    </view>
  </view>
</template>

<script>
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

export default {
  name: 'UToast',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    message: {
      type: String,
      default: ''
    },
    type: {
      type: String,
      default: 'info',
      validator: (value) => ['success', 'error', 'info'].includes(value)
    },
    duration: {
      type: Number,
      default: 2000
    },
    showIcon: {
      type: Boolean,
      default: true
    },
    themeMode: {
      type: String,
      default: ''
    }
  },

  data() {
    return {
      internalThemeMode: 'dark',
      animationVisible: false,
      timer: null
    }
  },

  computed: {
    resolvedThemeMode() {
      return this.themeMode ? normalizeThemeMode(this.themeMode) : this.internalThemeMode
    },
    themeClass() {
      return this.resolvedThemeMode === 'light' ? 'theme-light' : 'theme-dark'
    },
    typeClass() {
      return `toast-${this.type}`
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.refreshThemeMode()
          this.show()
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  created() {
    this.refreshThemeMode()
  },

  beforeDestroy() {
    if (this.timer) {
      clearTimeout(this.timer)
    }
  },

  methods: {
    refreshThemeMode() {
      this.internalThemeMode = getStoredThemeMode('dark')
    },

    show() {
      if (this.timer) {
        clearTimeout(this.timer)
      }

      this.$nextTick(() => {
        setTimeout(() => {
          this.animationVisible = true
        }, 10)
      })

      if (this.duration > 0) {
        this.timer = setTimeout(() => {
          this.hide()
        }, this.duration)
      }
    },

    hide() {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close')
      }, 200)
    }
  }
}
</script>

<style scoped>
.u-toast-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.u-toast-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 240rpx;
  max-width: 480rpx;
  padding: 32rpx 48rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 20rpx;
  box-shadow:
    0 8rpx 32rpx rgba(0, 0, 0, 0.4),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  transform: scale(0.8);
  opacity: 0;
  transition: all 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-toast-container.theme-light {
  background: rgba(255, 250, 244, 0.94);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow:
    0 14rpx 40rpx rgba(118, 101, 80, 0.18),
    0 0 0 1rpx rgba(255, 255, 255, 0.78) inset;
}

.u-toast-container.toast-show {
  transform: scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-toast-container {
    background: rgba(30, 30, 45, 0.98);
  }
}

.u-toast-icon {
  width: 72rpx;
  height: 72rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-image {
  width: 72rpx;
  height: 72rpx;
}

/* Success type */
.toast-success .icon-image {
  filter: brightness(0) saturate(100%) invert(85%) sepia(27%) saturate(541%) hue-rotate(67deg) brightness(95%) contrast(87%);
}

.toast-success .u-toast-message {
  color: #86EFAC;
}

/* Error type */
.toast-error .icon-image {
  filter: brightness(0) saturate(100%) invert(54%) sepia(98%) saturate(1834%) hue-rotate(331deg) brightness(99%) contrast(89%);
}

.toast-error .u-toast-message {
  color: #FCA5A5;
}

/* Info type */
.toast-info .icon-image {
  filter: brightness(0) saturate(100%) invert(66%) sepia(89%) saturate(1105%) hue-rotate(176deg) brightness(100%) contrast(101%);
}

.toast-info .u-toast-message {
  color: #93C5FD;
}

.theme-light.toast-success .u-toast-message {
  color: #1d7a43;
}

.theme-light.toast-error .u-toast-message {
  color: #c2410c;
}

.theme-light.toast-info .u-toast-message {
  color: #2F6EEA;
}

.u-toast-message {
  font-size: 30rpx;
  font-weight: 500;
  text-align: center;
  line-height: 1.4;
  word-break: break-word;
}

.theme-light .u-toast-message {
  color: #1F1A16;
}
</style>
