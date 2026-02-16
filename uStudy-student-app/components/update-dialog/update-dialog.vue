<template>
  <view v-if="visible" class="update-dialog-wrapper" @touchmove.stop.prevent>
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
          <text class="version-badge-text">NEW</text>
        </view>
        <text class="update-title">发现新版本 v{{ versionName }}</text>
        <text class="update-size">{{ fileSizeMb }} MB</text>
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
          <view v-if="!isForced" class="btn btn-ghost" @click="$emit('skip')">
            <text class="btn-text-ghost">跳过</text>
          </view>
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
    downloadError: { type: String, default: '' }
  },
  emits: ['skip', 'later', 'update', 'install', 'browser'],

  data() {
    return {
      animationVisible: false
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(val) {
        if (val) {
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
  background: rgba(0, 0, 0, 0.8);
}

.update-container {
  position: relative;
  width: 620rpx;
  max-height: 80vh;
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

.update-container.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .update-container {
    background: rgba(18, 18, 28, 0.98);
  }
}

.update-glow {
  position: absolute;
  top: -100rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 400rpx;
  height: 200rpx;
  background: radial-gradient(ellipse, rgba(0, 136, 255, 0.3) 0%, transparent 70%);
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
  background: linear-gradient(135deg, rgba(0, 136, 255, 0.3) 0%, rgba(0, 170, 255, 0.15) 100%);
  border: 1rpx solid rgba(0, 170, 255, 0.4);
  border-radius: 100rpx;
}

.version-badge-text {
  font-size: 22rpx;
  font-weight: 700;
  color: #00AAFF;
  letter-spacing: 2rpx;
}

.update-title {
  font-size: 38rpx;
  font-weight: 600;
  color: #ffffff;
}

.update-size {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.45);
}

/* Changelog */
.changelog-area {
  margin: 0 40rpx;
  max-height: 360rpx;
  background: rgba(0, 0, 0, 0.3);
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
  color: rgba(255, 255, 255, 0.35);
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
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6rpx;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0088FF, #00AAFF);
  border-radius: 6rpx;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.7);
  min-width: 80rpx;
  text-align: right;
}

/* Error */
.error-section {
  padding: 12rpx 40rpx 0;
}

.error-text {
  font-size: 24rpx;
  color: #F87171;
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

.btn-ghost {
  flex: 0.6;
  background: transparent;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.btn-text-ghost {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.45);
}

.btn-secondary {
  flex: 0.8;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.btn-text-secondary {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.btn-primary {
  background: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  box-shadow: 0 8rpx 24rpx rgba(0, 136, 255, 0.3);
}

.btn-text-primary {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.btn-disabled {
  background: rgba(0, 136, 255, 0.25);
}

.btn-text-disabled {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.5);
}
</style>
