<template>
  <view class="search-settings-page">
    <!-- Aurora Background -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">搜索设置</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <view class="section-title">搜索渠道</view>
      <view class="section-desc">选择 AI 对话中可用的搜索渠道，关闭后 AI 将不会调用对应的搜索工具</view>

      <view class="settings-card">
        <!-- 联网搜索 -->
        <view class="settings-item">
          <view class="item-left">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
            <view class="item-text">
              <text class="item-label">联网搜索</text>
              <text class="item-desc">DuckDuckGo 通用网页搜索</text>
            </view>
          </view>
          <view class="toggle-switch" :class="{ 'toggle-on': settings.web_search_enabled }"
            @click="toggleChannel('web_search_enabled')">
            <view class="toggle-thumb"></view>
          </view>
        </view>

        <view class="settings-divider"></view>

        <!-- 学术搜索 -->
        <view class="settings-item">
          <view class="item-left">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/graduation-cap.svg" mode="aspectFit"></image>
            <view class="item-text">
              <text class="item-label">学术搜索</text>
              <text class="item-desc">Semantic Scholar 学术论文</text>
            </view>
          </view>
          <view class="toggle-switch" :class="{ 'toggle-on': settings.academic_search_enabled }"
            @click="toggleChannel('academic_search_enabled')">
            <view class="toggle-thumb"></view>
          </view>
        </view>

        <view class="settings-divider"></view>

        <!-- 百科搜索 -->
        <view class="settings-item">
          <view class="item-left">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/books.svg" mode="aspectFit"></image>
            <view class="item-text">
              <text class="item-label">百科搜索</text>
              <text class="item-desc">维基百科中英文词条</text>
            </view>
          </view>
          <view class="toggle-switch" :class="{ 'toggle-on': settings.encyclopedia_search_enabled }"
            @click="toggleChannel('encyclopedia_search_enabled')">
            <view class="toggle-thumb"></view>
          </view>
        </view>

        <view class="settings-divider"></view>

        <!-- 课程搜索 -->
        <view class="settings-item">
          <view class="item-left">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/globe.svg" mode="aspectFit"></image>
            <view class="item-text">
              <text class="item-label">课程搜索</text>
              <text class="item-desc">B站教育视频与课程</text>
            </view>
          </view>
          <view class="toggle-switch" :class="{ 'toggle-on': settings.course_search_enabled }"
            @click="toggleChannel('course_search_enabled')">
            <view class="toggle-thumb"></view>
          </view>
        </view>
      </view>

      <view class="settings-note">
        <text class="note-text">所有搜索渠道均免费，无需额外配置。更改即时生效。</text>
      </view>
    </view>
  </view>
</template>

<script>
import { getSearchSettings, updateSearchSettings } from '@/api/searchSettings'

export default {
  data() {
    return {
      settings: {
        web_search_enabled: true,
        academic_search_enabled: true,
        encyclopedia_search_enabled: true,
        course_search_enabled: true
      },
      isLoading: false
    }
  },

  onLoad() {
    this.loadSettings()
  },

  methods: {
    goBack() {
      uni.navigateBack()
    },

    async loadSettings() {
      try {
        this.isLoading = true
        const res = await getSearchSettings()
        if (res) {
          this.settings = {
            web_search_enabled: res.web_search_enabled ?? true,
            academic_search_enabled: res.academic_search_enabled ?? true,
            encyclopedia_search_enabled: res.encyclopedia_search_enabled ?? true,
            course_search_enabled: res.course_search_enabled ?? true
          }
        }
      } catch (error) {
        console.error('Failed to load search settings:', error)
      } finally {
        this.isLoading = false
      }
    },

    async toggleChannel(key) {
      const newValue = !this.settings[key]
      // Optimistic update
      this.settings = { ...this.settings, [key]: newValue }

      try {
        await updateSearchSettings({ [key]: newValue })
      } catch (error) {
        // Revert on failure
        this.settings = { ...this.settings, [key]: !newValue }
        uni.showToast({ title: '更新失败，请重试', icon: 'none' })
      }
    }
  }
}
</script>

<style scoped>
.search-settings-page {
  min-height: 100vh;
  background: #0A0A12;
  position: relative;
  overflow: hidden;
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 0;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120rpx);
  opacity: 0.15;
}

.aurora-blob-1 {
  width: 400rpx;
  height: 400rpx;
  background: #8b5cf6;
  top: -100rpx;
  right: -100rpx;
}

.aurora-blob-2 {
  width: 300rpx;
  height: 300rpx;
  background: #3b82f6;
  bottom: 200rpx;
  left: -80rpx;
}

/* Navigation */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24rpx;
  height: 88rpx;
  padding-top: var(--status-bar-height);
  position: relative;
  z-index: 1;
}

.nav-left {
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-icon {
  width: 40rpx;
  height: 40rpx;
  opacity: 0.7;
}

.nav-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.nav-right-placeholder {
  width: 60rpx;
}

/* Content */
.content-area {
  padding: 24rpx 32rpx;
  position: relative;
  z-index: 1;
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  margin-bottom: 8rpx;
}

.section-desc {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 24rpx;
  line-height: 1.5;
}

.settings-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 0 24rpx;
  overflow: hidden;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.item-icon {
  width: 40rpx;
  height: 40rpx;
  opacity: 0.6;
  flex-shrink: 0;
}

.item-text {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.item-label {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

.item-desc {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

.settings-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.06);
}

/* Toggle Switch */
.toggle-switch {
  width: 88rpx;
  height: 48rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.12);
  position: relative;
  transition: background 0.25s ease;
  flex-shrink: 0;
}

.toggle-switch.toggle-on {
  background: rgba(139, 92, 246, 0.7);
}

.toggle-thumb {
  width: 40rpx;
  height: 40rpx;
  border-radius: 20rpx;
  background: #fff;
  position: absolute;
  top: 4rpx;
  left: 4rpx;
  transition: transform 0.25s ease;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.2);
}

.toggle-on .toggle-thumb {
  transform: translateX(40rpx);
}

/* Note */
.settings-note {
  margin-top: 24rpx;
  padding: 0 8rpx;
}

.note-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
  line-height: 1.5;
}
</style>
