<template>
  <view v-if="visible" class="u-modal-wrapper" @touchmove.stop.prevent>
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
    closeOnClickOverlay: {
      type: Boolean,
      default: true
    }
  },

  data() {
    return {
      animationVisible: false
    }
  },

  computed: {
    formattedContent() {
      return this.content.replace(/&#10;/g, '\n')
    },
    confirmButtonClass() {
      return this.confirmType === 'danger' ? 'btn-danger' : 'btn-primary'
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
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

  methods: {
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
  background: rgba(0, 0, 0, 0.6);
}

.u-modal-container {
  position: relative;
  width: 560rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  box-shadow:
    0 16rpx 48rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
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
    background: rgba(30, 30, 45, 0.98);
  }
}

.u-modal-title {
  padding: 40rpx 40rpx 0;
  text-align: center;
}

.u-modal-title text {
  font-size: 36rpx;
  font-weight: 600;
  color: #ffffff;
}

.u-modal-content {
  padding: 32rpx 40rpx 40rpx;
  text-align: center;
}

.u-modal-content-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.75);
  line-height: 1.6;
  white-space: pre-wrap;
}

.u-modal-buttons {
  display: flex;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
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
  background: rgba(255, 255, 255, 0.08);
}

.btn-cancel {
  color: rgba(255, 255, 255, 0.7);
  border-right: 1rpx solid rgba(255, 255, 255, 0.1);
}

.btn-confirm.btn-primary {
  color: #00AAFF;
}

.btn-confirm.btn-danger {
  color: #EF4444;
}
</style>
