<template>
  <view
    v-if="visible"
    class="mastery-toast"
    :class="[changeClass, { 'toast-enter': animationVisible }]"
    :style="positionStyle"
  >
    <image class="mastery-toast-icon" mode="aspectFit" src="/static/icons/phosphor/regular/chart-line-up-white.svg" />
    <text class="mastery-toast-name">{{ nodeName }}</text>
    <text class="mastery-toast-change">{{ changeLabel }}</text>
  </view>
</template>

<script>
export default {
  props: {
    visible: { type: Boolean, default: false },
    nodeName: { type: String, default: '' },
    change: { type: Number, default: 0 },
    duration: { type: Number, default: 3000 },
    index: { type: Number, default: 0 }
  },

  emits: ['close'],

  data() {
    return {
      animationVisible: false,
      dismissTimer: null
    }
  },

  computed: {
    changeClass() {
      return this.change >= 0 ? 'mastery-toast-positive' : 'mastery-toast-negative'
    },
    changeLabel() {
      return this.change >= 0 ? `+${this.change}` : `${this.change}`
    },
    positionStyle() {
      return {
        top: `${60 + this.index * 36}px`
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
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this.animationVisible = true
        })
      })
      this.clearDismiss()
      this.dismissTimer = setTimeout(() => {
        this.$emit('close')
      }, this.duration)
    },

    clearDismiss() {
      if (this.dismissTimer) {
        clearTimeout(this.dismissTimer)
        this.dismissTimer = null
      }
    }
  }
}
</script>

<style scoped>
.mastery-toast {
  position: absolute;
  left: 50%;
  transform: translateX(-50%) translateY(-8px) scale(0.95);
  z-index: 20;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  white-space: nowrap;
}

.mastery-toast.toast-enter {
  opacity: 1;
  transform: translateX(-50%) translateY(0) scale(1);
}

.mastery-toast-positive {
  border: 1px solid rgba(73, 255, 170, 0.3);
}
.mastery-toast-positive .mastery-toast-change {
  color: #49FFAA;
}

.mastery-toast-negative {
  border: 1px solid rgba(255, 50, 66, 0.3);
}
.mastery-toast-negative .mastery-toast-change {
  color: #FF3242;
}

.mastery-toast-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.7;
}

.mastery-toast-name {
  font-size: 12px;
  font-weight: 600;
  color: #E2E8F0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 28px;
}

.mastery-toast-change {
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 28px;
}
</style>
