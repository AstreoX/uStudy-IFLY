<template>
  <view v-if="visible" class="ann-dialog-wrapper" :class="themeClass" @touchmove.stop.prevent>
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
          <markdown-render v-if="body" :content="body" :theme-mode="themeMode || localThemeMode" />
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
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

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
    body: { type: String, default: '' },
    themeMode: { type: String, default: '' }
  },
  emits: ['close'],

  data() {
    return {
      animationVisible: false,
      dontShowAgain: false,
      localThemeMode: 'dark'
    }
  },

  computed: {
    typeLabel() {
      return TYPE_LABELS[this.type] || '公告'
    },
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode || this.localThemeMode)}`
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(val) {
        if (val) {
          this.refreshThemeMode()
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

  created() {
    this.refreshThemeMode()
  },

  methods: {
    refreshThemeMode() {
      this.localThemeMode = getStoredThemeMode('dark')
    },

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
  --ann-overlay: rgba(0, 0, 0, 0.75);
  --ann-surface: rgba(18, 18, 28, 0.88);
  --ann-surface-fallback: rgba(18, 18, 28, 0.98);
  --ann-border: rgba(255, 255, 255, 0.08);
  --ann-title: #ffffff;
  --ann-date: rgba(255, 255, 255, 0.4);
  --ann-body-bg: rgba(0, 0, 0, 0.25);
  --ann-empty: rgba(255, 255, 255, 0.35);
  --ann-checkbox-border: rgba(255, 255, 255, 0.25);
  --ann-checkbox-bg: rgba(0, 136, 255, 0.8);
  --ann-checkbox-label: rgba(255, 255, 255, 0.5);
  --ann-confirm-bg: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  --ann-confirm-shadow: 0 4rpx 16rpx rgba(0, 136, 255, 0.25);
  --ann-confirm-text: #ffffff;
  --ann-maintenance-bg: rgba(251, 146, 60, 0.15);
  --ann-maintenance-border: rgba(251, 146, 60, 0.4);
  --ann-maintenance-text: #FB923C;
  --ann-feature-bg: rgba(34, 197, 94, 0.15);
  --ann-feature-border: rgba(34, 197, 94, 0.4);
  --ann-feature-text: #22C55E;
  --ann-notice-bg: rgba(0, 136, 255, 0.15);
  --ann-notice-border: rgba(0, 136, 255, 0.4);
  --ann-notice-text: #0088FF;
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

.ann-dialog-wrapper.theme-light {
  --ann-overlay: rgba(61, 46, 30, 0.22);
  --ann-surface: rgba(255, 249, 241, 0.96);
  --ann-surface-fallback: rgba(255, 249, 241, 0.99);
  --ann-border: rgba(63, 53, 42, 0.1);
  --ann-title: #1F1A16;
  --ann-date: rgba(31, 26, 22, 0.44);
  --ann-body-bg: rgba(63, 53, 42, 0.06);
  --ann-empty: rgba(31, 26, 22, 0.4);
  --ann-checkbox-border: rgba(63, 53, 42, 0.22);
  --ann-checkbox-bg: #2F6EEA;
  --ann-checkbox-label: rgba(31, 26, 22, 0.56);
  --ann-confirm-bg: linear-gradient(135deg, #2F6EEA 0%, #1F56C6 100%);
  --ann-confirm-shadow: 0 4rpx 16rpx rgba(47, 110, 234, 0.2);
  --ann-confirm-text: #ffffff;
  --ann-maintenance-bg: rgba(192, 122, 24, 0.14);
  --ann-maintenance-border: rgba(192, 122, 24, 0.22);
  --ann-maintenance-text: #A86412;
  --ann-feature-bg: rgba(47, 143, 98, 0.14);
  --ann-feature-border: rgba(47, 143, 98, 0.22);
  --ann-feature-text: #2F8F62;
  --ann-notice-bg: rgba(47, 110, 234, 0.12);
  --ann-notice-border: rgba(47, 110, 234, 0.18);
  --ann-notice-text: #2F6EEA;
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
  background: var(--ann-overlay);
}

.ann-container {
  position: relative;
  width: 620rpx;
  max-height: 75vh;
  background: var(--ann-surface);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid var(--ann-border);
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
    background: var(--ann-surface-fallback);
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
  background: var(--ann-maintenance-bg);
  border: 1rpx solid var(--ann-maintenance-border);
}

.badge-maintenance .type-badge-text {
  color: var(--ann-maintenance-text);
}

.badge-feature {
  background: var(--ann-feature-bg);
  border: 1rpx solid var(--ann-feature-border);
}

.badge-feature .type-badge-text {
  color: var(--ann-feature-text);
}

.badge-notice {
  background: var(--ann-notice-bg);
  border: 1rpx solid var(--ann-notice-border);
}

.badge-notice .type-badge-text {
  color: var(--ann-notice-text);
}

.type-badge-text {
  font-size: 22rpx;
  font-weight: 600;
}

.ann-title {
  font-size: 38rpx;
  font-weight: 600;
  color: var(--ann-title);
}

.ann-date {
  font-size: 24rpx;
  color: var(--ann-date);
}

/* Body */
.ann-body {
  margin: 0 40rpx;
  height: 400rpx;
  background: var(--ann-body-bg);
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
  color: var(--ann-empty);
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
  border: 2rpx solid var(--ann-checkbox-border);
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 200ms ease;
}

.checkbox-checked {
  background: var(--ann-checkbox-bg);
  border-color: var(--ann-checkbox-bg);
}

.checkbox-icon {
  font-size: 22rpx;
  color: #ffffff;
  font-weight: 700;
}

.checkbox-label {
  font-size: 26rpx;
  color: var(--ann-checkbox-label);
}

.btn-confirm {
  padding: 16rpx 40rpx;
  background: var(--ann-confirm-bg);
  border-radius: 16rpx;
  box-shadow: var(--ann-confirm-shadow);
  transition: all 150ms ease;
}

.btn-confirm:active {
  transform: scale(0.97);
}

.btn-confirm-text {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--ann-confirm-text);
}
</style>
