<template>
  <view v-if="visible" class="u-snackbar-wrapper" :style="{ bottom: bottomOffset }">
    <view class="u-snackbar-container" :class="{ 'snackbar-show': animationVisible }">
      <text class="u-snackbar-message">{{ message }}</text>
      <view v-if="actionText" class="u-snackbar-action" @click="handleAction">
        <text class="u-snackbar-action-text">{{ actionText }}</text>
        <image
          v-if="actionIcon"
          class="u-snackbar-action-icon"
          :src="actionIcon"
          mode="aspectFit"
        ></image>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'USnackbar',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    message: {
      type: String,
      default: ''
    },
    actionText: {
      type: String,
      default: ''
    },
    actionIcon: {
      type: String,
      default: ''
    },
    duration: {
      type: Number,
      default: 3000
    },
    bottomOffset: {
      type: String,
      default: 'calc(100vh * 3 / 26)'
    }
  },

  data() {
    return {
      animationVisible: false,
      timer: null
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

  beforeDestroy() {
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
      }, 300)
    },

    handleAction() {
      this.$emit('action')
    }
  }
}
</script>

<style scoped>
.u-snackbar-wrapper {
  position: fixed;
  left: 0;
  right: 0;
  z-index: 1000;
  display: flex;
  justify-content: center;
  pointer-events: none;
  padding: 0 calc(100vw / 24);
}

.u-snackbar-container {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  background: rgba(50, 50, 50, 0.92);
  border-radius: 8rpx;
  pointer-events: auto;
  transform: translateY(40rpx);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-snackbar-container.snackbar-show {
  transform: translateY(0);
  opacity: 1;
}

.u-snackbar-message {
  font-size: 28rpx;
  color: #ffffff;
  line-height: 1.4;
}

.u-snackbar-action {
  margin-left: 24rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.u-snackbar-action-text {
  font-size: 28rpx;
  color: #ffffff;
  font-weight: 600;
  text-transform: uppercase;
}

.u-snackbar-action-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
}
</style>
