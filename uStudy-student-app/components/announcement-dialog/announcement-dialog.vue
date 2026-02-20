<template>
  <view v-if="visible" class="ann-dialog-wrapper" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="ann-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleClose(false)"
    ></view>

    <!-- Dialog Container -->
    <view class="ann-container" :class="{ 'dialog-show': animationVisible }">
      <!-- Type Badge -->
      <view class="ann-header">
        <view class="type-badge" :class="'badge-' + type">
          <text class="type-badge-text">{{ typeLabel }}</text>
        </view>
        <text class="ann-title">{{ title }}</text>
        <text class="ann-date">{{ date }}</text>
      </view>

      <!-- Body -->
      <view class="ann-body">
        <scroll-view scroll-y class="ann-scroll">
          <markdown-render v-if="body" :content="body" />
          <text v-else class="ann-empty">暂无内容</text>
        </scroll-view>
      </view>

      <!-- Footer -->
      <view class="ann-footer">
        <view class="checkbox-row" @click="toggleDontShow">
          <view class="checkbox" :class="{ 'checkbox-checked': dontShowAgain }">
            <text v-if="dontShowAgain" class="checkbox-icon">✓</text>
          </view>
          <text class="checkbox-label">不再显示</text>
        </view>
        <view class="btn-confirm" @click="handleClose(dontShowAgain)">
          <text class="btn-confirm-text">我知道了</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'

const TYPE_LABELS = {
  maintenance: '维护通知',
  feature: '功能更新',
  notice: '系统公告'
}

export default {
  name: 'AnnouncementDialog',
  components: { MarkdownRender },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '' },
    date: { type: String, default: '' },
    type: { type: String, default: 'notice' },
    body: { type: String, default: '' }
  },
  emits: ['close'],

  data() {
    return {
      animationVisible: false,
      dontShowAgain: false
    }
  },

  computed: {
    typeLabel() {
      return TYPE_LABELS[this.type] || '公告'
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(val) {
        if (val) {
          this.dontShowAgain = false
          this.$nextTick(() => {
            setTimeout(() => { this.animationVisible = true }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  methods: {
    toggleDontShow() {
      this.dontShowAgain = !this.dontShowAgain
    },

    handleClose(dontShow) {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close', { dontShowAgain: dontShow })
      }, 200)
    }
  }
}
</script>

<style scoped>
.ann-dialog-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ann-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 300ms ease;
}

.ann-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.75);
}

.ann-container {
  position: relative;
  width: 620rpx;
  max-height: 75vh;
  background: rgba(18, 18, 28, 0.88);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  overflow: hidden;
  transform: translateY(60rpx) scale(0.9);
  opacity: 0;
  transition: all 350ms cubic-bezier(0.34, 1.56, 0.64, 1);
  display: flex;
  flex-direction: column;
}

.ann-container.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .ann-container {
    background: rgba(18, 18, 28, 0.98);
  }
}

/* Header */
.ann-header {
  padding: 40rpx 40rpx 24rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.type-badge {
  align-self: flex-start;
  padding: 6rpx 18rpx;
  border-radius: 8rpx;
}

.badge-maintenance {
  background: rgba(251, 146, 60, 0.15);
  border: 1rpx solid rgba(251, 146, 60, 0.4);
}

.badge-maintenance .type-badge-text {
  color: #FB923C;
}

.badge-feature {
  background: rgba(34, 197, 94, 0.15);
  border: 1rpx solid rgba(34, 197, 94, 0.4);
}

.badge-feature .type-badge-text {
  color: #22C55E;
}

.badge-notice {
  background: rgba(0, 136, 255, 0.15);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
}

.badge-notice .type-badge-text {
  color: #0088FF;
}

.type-badge-text {
  font-size: 22rpx;
  font-weight: 600;
}

.ann-title {
  font-size: 38rpx;
  font-weight: 600;
  color: #ffffff;
}

.ann-date {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
}

/* Body */
.ann-body {
  margin: 0 40rpx;
  height: 400rpx;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 16rpx;
  overflow: hidden;
}

.ann-scroll {
  width: 100%;
  height: 100%;
  padding: 24rpx;
  box-sizing: border-box;
  overflow-wrap: break-word;
  word-break: break-word;
  white-space: normal;
}

.ann-empty {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.35);
}

/* Footer */
.ann-footer {
  padding: 28rpx 40rpx 36rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.checkbox {
  width: 36rpx;
  height: 36rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.25);
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 200ms ease;
}

.checkbox-checked {
  background: rgba(0, 136, 255, 0.8);
  border-color: rgba(0, 136, 255, 0.8);
}

.checkbox-icon {
  font-size: 22rpx;
  color: #ffffff;
  font-weight: 700;
}

.checkbox-label {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
}

.btn-confirm {
  padding: 16rpx 40rpx;
  background: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  border-radius: 16rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 136, 255, 0.25);
  transition: all 150ms ease;
}

.btn-confirm:active {
  transform: scale(0.97);
}

.btn-confirm-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}
</style>
