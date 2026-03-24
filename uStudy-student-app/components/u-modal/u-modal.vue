<template>
  <view v-if="visible" class="u-modal-wrapper" :class="themeClass" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="u-modal-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleOverlayClick"
    ></view>

    <!-- Modal Container -->
    <view class="u-modal-container" :class="{ 'modal-show': animationVisible }">
      <!-- Title -->
      <view v-if="title" class="u-modal-title">
        <text>{{ title }}</text>
      </view>

      <!-- Content -->
      <view class="u-modal-content">
        <text class="u-modal-content-text">{{ formattedContent }}</text>
      </view>

      <!-- Buttons -->
      <view class="u-modal-buttons" :class="{ 'single-button': !showCancel }">
        <button
          v-if="showCancel"
          class="u-modal-btn btn-cancel"
          @click="handleCancel"
        >
          {{ cancelText }}
        </button>
        <button
          class="u-modal-btn btn-confirm"
          :class="confirmButtonClass"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

export default {
  name: 'UModal',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    title: {
      type: String,
      default: ''
    },
    content: {
      type: String,
      default: ''
    },
    showCancel: {
      type: Boolean,
      default: true
    },
    cancelText: {
      type: String,
      default: '取消'
    },
    confirmText: {
      type: String,
      default: '确定'
    },
    confirmType: {
      type: String,
      default: 'primary',
      validator: (value) => ['primary', 'danger'].includes(value)
    },
    themeMode: {
      type: String,
      default: ''
    },
    closeOnClickOverlay: {
      type: Boolean,
      default: true
    }
  },

  data() {
    return {
      animationVisible: false,
      localThemeMode: 'dark'
    }
  },

  computed: {
    formattedContent() {
      return this.content.replace(/&#10;/g, '\n')
    },
    confirmButtonClass() {
      return this.confirmType === 'danger' ? 'btn-danger' : 'btn-primary'
    },
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode || this.localThemeMode)}`
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.refreshThemeMode()
          this.$nextTick(() => {
            setTimeout(() => {
              this.animationVisible = true
            }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  created() {
    this.refreshThemeMode()
  },

  methods: {
    refreshThemeMode() {
      this.localThemeMode = getStoredThemeMode('dark')
    },

    handleOverlayClick() {
      if (this.closeOnClickOverlay) {
        this.close()
      }
    },

    handleCancel() {
      this.$emit('cancel')
      this.close()
    },

    handleConfirm() {
      this.$emit('confirm')
      this.close()
    },

    close() {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close')
      }, 200)
    }
  }
}
</script>

<style scoped>
.u-modal-wrapper {
  --u-modal-overlay: rgba(0, 0, 0, 0.6);
  --u-modal-surface: rgba(20, 20, 30, 0.92);
  --u-modal-surface-fallback: rgba(30, 30, 45, 0.98);
  --u-modal-border: rgba(255, 255, 255, 0.15);
  --u-modal-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.5);
  --u-modal-highlight: rgba(255, 255, 255, 0.05);
  --u-modal-title: #ffffff;
  --u-modal-text: rgba(255, 255, 255, 0.75);
  --u-modal-divider: rgba(255, 255, 255, 0.1);
  --u-modal-btn-active: rgba(255, 255, 255, 0.08);
  --u-modal-cancel: rgba(255, 255, 255, 0.7);
  --u-modal-primary: #00AAFF;
  --u-modal-danger: #EF4444;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.u-modal-wrapper.theme-light {
  --u-modal-overlay: rgba(61, 46, 30, 0.22);
  --u-modal-surface: rgba(255, 249, 241, 0.96);
  --u-modal-surface-fallback: rgba(255, 249, 241, 0.99);
  --u-modal-border: rgba(63, 53, 42, 0.12);
  --u-modal-shadow: 0 16rpx 48rpx rgba(118, 101, 80, 0.18);
  --u-modal-highlight: rgba(255, 255, 255, 0.78);
  --u-modal-title: #1F1A16;
  --u-modal-text: rgba(31, 26, 22, 0.72);
  --u-modal-divider: rgba(63, 53, 42, 0.1);
  --u-modal-btn-active: rgba(63, 53, 42, 0.06);
  --u-modal-cancel: rgba(31, 26, 22, 0.62);
  --u-modal-primary: #2F6EEA;
  --u-modal-danger: #D14F4F;
}

.u-modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 200ms ease;
}

.u-modal-overlay.overlay-show {
  background: var(--u-modal-overlay);
}

.u-modal-container {
  position: relative;
  width: 560rpx;
  background: var(--u-modal-surface);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid var(--u-modal-border);
  border-radius: 24rpx;
  box-shadow:
    var(--u-modal-shadow),
    0 0 0 1rpx var(--u-modal-highlight) inset;
  overflow: hidden;
  transform: translateY(40rpx) scale(0.95);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-modal-container.modal-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-modal-container {
    background: var(--u-modal-surface-fallback);
  }
}

.u-modal-title {
  padding: 40rpx 40rpx 0;
  text-align: center;
}

.u-modal-title text {
  font-size: 36rpx;
  font-weight: 600;
  color: var(--u-modal-title);
}

.u-modal-content {
  padding: 32rpx 40rpx 40rpx;
  text-align: center;
}

.u-modal-content-text {
  font-size: 30rpx;
  color: var(--u-modal-text);
  line-height: 1.6;
  white-space: pre-wrap;
}

.u-modal-buttons {
  display: flex;
  border-top: 1rpx solid var(--u-modal-divider);
}

.u-modal-buttons.single-button {
  justify-content: center;
}

.u-modal-btn {
  flex: 1;
  height: 100rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  font-weight: 500;
  background: transparent;
  border: none;
  border-radius: 0;
  transition: background 150ms ease;
}

.u-modal-btn::after {
  border: none;
}

.u-modal-btn:active {
  background: var(--u-modal-btn-active);
}

.btn-cancel {
  color: var(--u-modal-cancel);
  border-right: 1rpx solid var(--u-modal-divider);
}

.btn-confirm.btn-primary {
  color: var(--u-modal-primary);
}

.btn-confirm.btn-danger {
  color: var(--u-modal-danger);
}
</style>
