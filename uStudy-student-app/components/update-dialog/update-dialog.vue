<template>
  <view v-if="visible" class="update-dialog-wrapper" :class="themeClass" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="update-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleOverlayClick"
    ></view>

    <!-- Dialog Container -->
    <view class="update-container" :class="{ 'dialog-show': animationVisible }">
      <!-- Glow effect -->
      <view class="update-glow"></view>

      <!-- Header -->
      <view class="update-header">
        <view class="version-badge">
          <text class="version-badge-text">{{ isWgtUpdate ? '热更新' : 'NEW' }}</text>
        </view>
        <text class="update-title">发现新版本 v{{ versionName }}</text>
        <text class="update-size">{{ fileSizeMb }} MB · {{ isWgtUpdate ? '热更新' : '完整更新' }}</text>
      </view>

      <!-- Changelog Area -->
      <view class="changelog-area">
        <scroll-view scroll-y class="changelog-scroll">
          <markdown-render v-if="changelog" :content="changelog" />
          <text v-else class="changelog-empty">暂无更新说明</text>
        </scroll-view>
      </view>

      <!-- Progress Bar (downloading) -->
      <view v-if="isDownloading || downloadComplete" class="progress-section">
        <view class="progress-track">
          <view class="progress-fill" :style="{ width: downloadProgress + '%' }"></view>
        </view>
        <text class="progress-text">
          {{ downloadComplete ? '下载完成' : `${downloadProgress}%` }}
        </text>
      </view>

      <!-- Error message -->
      <view v-if="downloadError" class="error-section">
        <text class="error-text">{{ downloadError }}</text>
      </view>

      <!-- Buttons -->
      <view class="button-section">
        <template v-if="downloadComplete">
          <view class="btn btn-primary btn-full" @click="$emit('install')">
            <text class="btn-text-primary">立即安装</text>
          </view>
        </template>
        <template v-else-if="isDownloading">
          <view class="btn btn-disabled btn-full">
            <text class="btn-text-disabled">下载中...</text>
          </view>
        </template>
        <template v-else-if="downloadError">
          <view class="btn btn-secondary" @click="$emit('browser')">
            <text class="btn-text-secondary">浏览器下载</text>
          </view>
          <view class="btn btn-primary" @click="$emit('update')">
            <text class="btn-text-primary">重试</text>
          </view>
        </template>
        <template v-else>
          <view v-if="!isForced" class="btn btn-secondary" @click="$emit('later')">
            <text class="btn-text-secondary">稍后</text>
          </view>
          <view class="btn btn-primary" :class="{ 'btn-full': isForced }" @click="$emit('update')">
            <text class="btn-text-primary">立即更新</text>
          </view>
        </template>
      </view>
    </view>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

export default {
  name: 'UpdateDialog',
  components: { MarkdownRender },
  props: {
    visible: { type: Boolean, default: false },
    versionName: { type: String, default: '' },
    fileSizeMb: { type: Number, default: 0 },
    isForced: { type: Boolean, default: false },
    changelog: { type: String, default: '' },
    isDownloading: { type: Boolean, default: false },
    downloadProgress: { type: Number, default: 0 },
    downloadComplete: { type: Boolean, default: false },
    downloadError: { type: String, default: '' },
    isWgtUpdate: { type: Boolean, default: false },
    themeMode: { type: String, default: '' }
  },
  emits: ['skip', 'later', 'update', 'install', 'browser'],

  data() {
    return {
      animationVisible: false,
      localThemeMode: 'dark'
    }
  },

  computed: {
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

    handleOverlayClick() {
      if (!this.isForced && !this.isDownloading) {
        this.$emit('later')
      }
    }
  }
}
</script>

<style scoped>
.update-dialog-wrapper {
  --update-overlay: rgba(0, 0, 0, 0.8);
  --update-surface: rgba(18, 18, 28, 0.88);
  --update-surface-fallback: rgba(18, 18, 28, 0.98);
  --update-border: rgba(255, 255, 255, 0.08);
  --update-glow: radial-gradient(ellipse, rgba(0, 136, 255, 0.3) 0%, transparent 70%);
  --update-badge-bg: linear-gradient(135deg, rgba(0, 136, 255, 0.3) 0%, rgba(0, 170, 255, 0.15) 100%);
  --update-badge-border: rgba(0, 170, 255, 0.4);
  --update-badge-text: #00AAFF;
  --update-title: #ffffff;
  --update-meta: rgba(255, 255, 255, 0.45);
  --update-panel: rgba(0, 0, 0, 0.3);
  --update-empty: rgba(255, 255, 255, 0.35);
  --update-progress-bg: rgba(255, 255, 255, 0.1);
  --update-progress-fill: linear-gradient(90deg, #0088FF, #00AAFF);
  --update-progress-text: rgba(255, 255, 255, 0.7);
  --update-error: #F87171;
  --update-btn-secondary-bg: rgba(255, 255, 255, 0.08);
  --update-btn-secondary-border: rgba(255, 255, 255, 0.12);
  --update-btn-secondary-text: rgba(255, 255, 255, 0.7);
  --update-btn-primary-bg: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  --update-btn-primary-shadow: 0 8rpx 24rpx rgba(0, 136, 255, 0.3);
  --update-btn-primary-text: #ffffff;
  --update-btn-disabled-bg: rgba(0, 136, 255, 0.25);
  --update-btn-disabled-text: rgba(255, 255, 255, 0.5);
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

.update-dialog-wrapper.theme-light {
  --update-overlay: rgba(61, 46, 30, 0.22);
  --update-surface: rgba(255, 249, 241, 0.96);
  --update-surface-fallback: rgba(255, 249, 241, 0.99);
  --update-border: rgba(63, 53, 42, 0.1);
  --update-glow: radial-gradient(ellipse, rgba(47, 110, 234, 0.18) 0%, transparent 70%);
  --update-badge-bg: linear-gradient(135deg, rgba(47, 110, 234, 0.16) 0%, rgba(47, 110, 234, 0.08) 100%);
  --update-badge-border: rgba(47, 110, 234, 0.18);
  --update-badge-text: #2F6EEA;
  --update-title: #1F1A16;
  --update-meta: rgba(31, 26, 22, 0.5);
  --update-panel: rgba(63, 53, 42, 0.06);
  --update-empty: rgba(31, 26, 22, 0.4);
  --update-progress-bg: rgba(63, 53, 42, 0.08);
  --update-progress-fill: linear-gradient(90deg, #2F6EEA, #1F56C6);
  --update-progress-text: rgba(31, 26, 22, 0.62);
  --update-error: #D14F4F;
  --update-btn-secondary-bg: rgba(255, 255, 255, 0.82);
  --update-btn-secondary-border: rgba(63, 53, 42, 0.12);
  --update-btn-secondary-text: rgba(31, 26, 22, 0.68);
  --update-btn-primary-bg: linear-gradient(135deg, #2F6EEA 0%, #1F56C6 100%);
  --update-btn-primary-shadow: 0 8rpx 24rpx rgba(47, 110, 234, 0.18);
  --update-btn-primary-text: #ffffff;
  --update-btn-disabled-bg: rgba(47, 110, 234, 0.18);
  --update-btn-disabled-text: rgba(31, 26, 22, 0.42);
}

.update-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 300ms ease;
}

.update-overlay.overlay-show {
  background: var(--update-overlay);
}

.update-container {
  position: relative;
  width: 620rpx;
  max-height: 80vh;
  background: var(--update-surface);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid var(--update-border);
  border-radius: 32rpx;
  overflow: hidden;
  transform: translateY(60rpx) scale(0.9);
  opacity: 0;
  transition: all 350ms cubic-bezier(0.34, 1.56, 0.64, 1);
  display: flex;
  flex-direction: column;
}

.update-container.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .update-container {
    background: var(--update-surface-fallback);
  }
}

.update-glow {
  position: absolute;
  top: -100rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 400rpx;
  height: 200rpx;
  background: var(--update-glow);
  pointer-events: none;
}

/* Header */
.update-header {
  padding: 48rpx 40rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
}

.version-badge {
  padding: 6rpx 20rpx;
  background: var(--update-badge-bg);
  border: 1rpx solid var(--update-badge-border);
  border-radius: 100rpx;
}

.version-badge-text {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--update-badge-text);
  letter-spacing: 2rpx;
}

.update-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--update-title);
}

.update-size {
  font-size: 24rpx;
  color: var(--update-meta);
}

/* Changelog */
.changelog-area {
  margin: 0 40rpx;
  max-height: 360rpx;
  background: var(--update-panel);
  border-radius: 16rpx;
  overflow: hidden;
}

.changelog-scroll {
  height: 360rpx;
  padding: 24rpx;
  box-sizing: border-box;
  overflow-wrap: break-word;
}

.changelog-empty {
  font-size: 28rpx;
  color: var(--update-empty);
}

/* Progress */
.progress-section {
  padding: 24rpx 40rpx 0;
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.progress-track {
  flex: 1;
  height: 12rpx;
  background: var(--update-progress-bg);
  border-radius: 6rpx;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--update-progress-fill);
  border-radius: 6rpx;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 24rpx;
  color: var(--update-progress-text);
  min-width: 80rpx;
  text-align: right;
}

/* Error */
.error-section {
  padding: 12rpx 40rpx 0;
}

.error-text {
  font-size: 24rpx;
  color: var(--update-error);
}

/* Buttons */
.button-section {
  padding: 32rpx 40rpx 40rpx;
  display: flex;
  gap: 20rpx;
}

.btn {
  flex: 1;
  height: 92rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
  transition: all 150ms ease;
}

.btn:active {
  transform: scale(0.97);
}

.btn-full {
  flex: none;
  width: 100%;
}

.btn-secondary {
  flex: 1;
  background: var(--update-btn-secondary-bg);
  border: 1rpx solid var(--update-btn-secondary-border);
}

.btn-text-secondary {
  font-size: 26rpx;
  color: var(--update-btn-secondary-text);
  font-weight: 500;
}

.btn-primary {
  background: var(--update-btn-primary-bg);
  box-shadow: var(--update-btn-primary-shadow);
}

.btn-text-primary {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--update-btn-primary-text);
}

.btn-disabled {
  background: var(--update-btn-disabled-bg);
}

.btn-text-disabled {
  font-size: 28rpx;
  color: var(--update-btn-disabled-text);
}
</style>
