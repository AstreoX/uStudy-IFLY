<template>
  <view v-if="visible" class="u-capsule-toast" :class="{ 'capsule-show': animationVisible, 'capsule-negative': change < 0 }" :style="positionStyle">
    <image class="capsule-icon" src="/static/icons/phosphor-icons/SVGs Flat/bold/graph-bold.svg" mode="aspectFit" />
    <text class="capsule-label">{{ nodeName }}</text>
    <text class="capsule-change" :class="changeClass">{{ changeText }}</text>
  </view>
</template>

<script>
export default {
  name: 'UCapsuleToast',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    nodeName: {
      type: String,
      default: ''
    },
    change: {
      type: Number,
      default: 0
    },
    duration: {
      type: Number,
      default: 3000
    },
    index: {
      type: Number,
      default: 0
    }
  },

  data() {
    return {
      animationVisible: false,
      timer: null
    }
  },

  computed: {
    changeText() {
      if (this.change > 0) return `+${this.change}`
      if (this.change < 0) return `${this.change}`
      return '0'
    },
    changeClass() {
      if (this.change > 0) return 'change-positive'
      if (this.change < 0) return 'change-negative'
      return ''
    },
    positionStyle() {
      const baseTop = 120
      const offset = this.index * 70
      return `top: ${baseTop + offset}rpx;`
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
    }
  }
}
</script>

<style scoped>
.u-capsule-toast {
  position: fixed;
  left: 50%;
  transform: translateX(-50%) translateY(-100%);
  opacity: 0;
  padding: 14rpx 32rpx;
  background: rgba(20, 30, 25, 0.92);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  backdrop-filter: blur(16px) saturate(180%);
  border-radius: 100rpx;
  border: 1rpx solid rgba(34, 197, 94, 0.25);
  display: flex;
  align-items: center;
  gap: 12rpx;
  z-index: 1200;
  box-shadow:
    0 4rpx 24rpx rgba(0, 0, 0, 0.35),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  transition: all 350ms cubic-bezier(0.34, 1.56, 0.64, 1);
  pointer-events: none;
  white-space: nowrap;
  max-width: 80vw;
}

.u-capsule-toast.capsule-show {
  transform: translateX(-50%) translateY(0);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-capsule-toast {
    background: rgba(20, 30, 25, 0.98);
  }
}

.capsule-icon {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(1);
}

.capsule-label {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.capsule-change {
  font-size: 26rpx;
  font-weight: 600;
  line-height: 1.3;
  flex-shrink: 0;
}

.change-positive {
  color: #86EFAC;
}

.change-negative {
  color: #FCA5A5;
}

.u-capsule-toast.capsule-negative {
  border-color: rgba(239, 68, 68, 0.25);
}
</style>
