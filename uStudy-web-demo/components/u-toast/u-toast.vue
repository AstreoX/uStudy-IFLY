<template>
  <view v-if="visible" class="u-toast-wrapper">
    <view class="u-toast-container" :class="[typeClass, { 'toast-show': animationVisible }]">
      <text v-if="showIcon" class="u-toast-icon">{{ iconText }}</text>
      <text class="u-toast-message">{{ message }}</text>
    </view>
  </view>
</template>

<script>
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
    }
  },
  data() {
    return {
      animationVisible: false,
      timer: null
    }
  },
  computed: {
    typeClass() {
      return `toast-${this.type}`
    },
    iconText() {
      if (this.type === 'success') return '✓'
      if (this.type === 'error') return '×'
      return 'i'
    }
  },
  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.show()
        } else {
          this.animationVisible = false
        }
      }
    }
  },
  beforeUnmount() {
    if (this.timer) {
      clearTimeout(this.timer)
    }
  },
  methods: {
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
  position: absolute;
  inset: 0;
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.u-toast-container {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  min-width: 220rpx;
  max-width: calc(100% - 32px);
  padding: 22rpx 30rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 16rpx;
  box-shadow:
    0 8rpx 32rpx rgba(0, 0, 0, 0.4),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  transform: scale(0.92);
  opacity: 0;
  transition: all 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-toast-container.toast-show {
  transform: scale(1);
  opacity: 1;
}

.u-toast-icon {
  font-size: 34rpx;
  font-weight: 700;
  line-height: 1;
}

.u-toast-message {
  font-size: 28rpx;
  font-weight: 500;
  text-align: left;
  line-height: 1.4;
  word-break: break-word;
}

.toast-success .u-toast-icon,
.toast-success .u-toast-message {
  color: #86efac;
}

.toast-error .u-toast-icon,
.toast-error .u-toast-message {
  color: #fca5a5;
}

.toast-info .u-toast-icon,
.toast-info .u-toast-message {
  color: #93c5fd;
}
</style>
