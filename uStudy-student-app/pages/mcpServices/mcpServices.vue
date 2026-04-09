<template>
  <view class="mcp-services-page" :class="pageThemeClass">
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
      <text class="nav-title">MCP 服务</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <view class="section-desc">连接外部 MCP 服务（如 Notion、飞书等），让 AI 调用更多工具</view>

      <!-- Loading -->
      <view v-if="isLoading" class="loading-wrapper">
        <text class="loading-text">加载中...</text>
      </view>

      <!-- Empty State -->
      <view v-else-if="services.length === 0" class="empty-state">
        <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit"></image>
        <text class="empty-title">还没有 MCP 服务</text>
        <text class="empty-desc">添加后 AI 可使用外部工具</text>
      </view>

      <!-- Service List -->
      <view v-else class="services-list">
        <view
          v-for="service in services"
          :key="service.id"
          class="service-card"
          @click="editService(service)"
        >
          <view class="service-info">
            <view class="service-header">
              <text class="service-name">{{ service.name }}</text>
              <view
                v-if="service.tools_count > 0"
                class="tools-badge"
              >
                <text class="tools-badge-text">{{ service.tools_count }} 个工具</text>
              </view>
              <view v-else class="tools-badge tools-badge-warn">
                <text class="tools-badge-text">连接失败</text>
              </view>
            </view>
            <text class="service-url">{{ service.url }}</text>
          </view>
          <view class="service-actions" @click.stop>
            <view
              class="toggle-switch"
              :class="{ 'toggle-on': service.enabled }"
              @click="toggleService(service)"
            >
              <view class="toggle-thumb"></view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Bottom Add Button -->
    <view class="bottom-bar">
      <view class="add-btn" @click="addService">
        <text class="add-btn-text">+ 添加 MCP 服务</text>
      </view>
    </view>
  </view>
</template>

<script>
import { getMcpServices, updateMcpService, deleteMcpService } from '@/api/mcp'
import { getStoredThemeMode } from '@/utils/themeMode'
import { goBack } from '@/utils/navigation'

export default {
  data() {
    return {
      homeThemeMode: 'dark',
      services: [],
      isLoading: false
    }
  },

  computed: {
    isLightTheme() {
      return this.homeThemeMode === 'light'
    },

    pageThemeClass() {
      return this.isLightTheme ? 'theme-light' : 'theme-dark'
    }
  },

  onLoad() {
    this.restoreThemeMode()
    this.loadServices()
  },

  onShow() {
    this.restoreThemeMode()
    this.loadServices()
  },

  methods: {
    restoreThemeMode() {
      this.homeThemeMode = getStoredThemeMode('dark')
      this.syncThemeSystemUi(this.homeThemeMode)
    },

    syncThemeSystemUi(mode) {
      // #ifdef APP-PLUS
      try {
        plus.navigator.setStatusBarStyle(mode === 'light' ? 'dark' : 'light')
        plus.navigator.setStatusBarBackground(mode === 'light' ? '#F3EDE3' : '#0A0A12')
      } catch (_) {}
      // #endif
    },

    goBack() {
      goBack()
    },

    async loadServices() {
      try {
        this.isLoading = true
        const res = await getMcpServices()
        this.services = res?.services || []
      } catch (error) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.isLoading = false
      }
    },

    async toggleService(service) {
      const newEnabled = !service.enabled
      // Optimistic update
      const idx = this.services.findIndex(s => s.id === service.id)
      if (idx !== -1) {
        this.services = this.services.map((s, i) =>
          i === idx ? { ...s, enabled: newEnabled } : s
        )
      }

      try {
        await updateMcpService(service.id, { enabled: newEnabled })
      } catch (error) {
        // Revert on failure
        this.services = this.services.map((s, i) =>
          i === idx ? { ...s, enabled: !newEnabled } : s
        )
        uni.showToast({ title: '更新失败', icon: 'none' })
      }
    },

    addService() {
      uni.navigateTo({ url: '/pages/mcpServiceDetail/mcpServiceDetail' })
    },

    editService(service) {
      uni.navigateTo({
        url: `/pages/mcpServiceDetail/mcpServiceDetail?service_id=${service.id}`
      })
    }
  }
}
</script>

<style scoped>
.mcp-services-page {
  min-height: 100vh;
  background: #0A0A12;
  position: relative;
  overflow: hidden;
  padding-bottom: 140rpx;
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
  filter: brightness(0) invert(1);
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

.section-desc {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 32rpx;
  line-height: 1.5;
}

/* Loading */
.loading-wrapper {
  display: flex;
  justify-content: center;
  padding: 80rpx 0;
}

.loading-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.4);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0 80rpx;
}

.empty-icon {
  width: 96rpx;
  height: 96rpx;
  filter: brightness(0) invert(1);
  opacity: 0.2;
  margin-bottom: 24rpx;
}

.empty-title {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
  margin-bottom: 8rpx;
}

.empty-desc {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.3);
}

/* Service Cards */
.services-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.service-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 28rpx 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.service-info {
  flex: 1;
  min-width: 0;
  margin-right: 20rpx;
}

.service-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.service-name {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

.tools-badge {
  background: rgba(139, 92, 246, 0.2);
  border-radius: 8rpx;
  padding: 2rpx 12rpx;
  flex-shrink: 0;
}

.tools-badge-text {
  font-size: 20rpx;
  color: rgba(139, 92, 246, 0.9);
}

.tools-badge-warn {
  background: rgba(245, 158, 11, 0.15);
}

.tools-badge-warn .tools-badge-text {
  color: rgba(245, 158, 11, 0.85);
}

.service-url {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-actions {
  flex-shrink: 0;
}

/* Toggle Switch */
.toggle-switch {
  width: 88rpx;
  height: 48rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.12);
  position: relative;
  transition: background 0.25s ease;
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

/* Bottom Bar */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20rpx 32rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  z-index: 10;
}

.add-btn {
  background: rgba(139, 92, 246, 0.85);
  border-radius: 20rpx;
  padding: 24rpx 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.add-btn-text {
  font-size: 30rpx;
  color: #fff;
  font-weight: 600;
}

/* ===== Light Theme ===== */
.mcp-services-page.theme-light {
  background: #F3EDE3;
}

.mcp-services-page.theme-light .aurora-blob-1 {
  background: rgba(47, 110, 234, 0.18);
}

.mcp-services-page.theme-light .aurora-blob-2 {
  background: rgba(199, 119, 22, 0.14);
}

.mcp-services-page.theme-light .nav-icon,
.mcp-services-page.theme-light .empty-icon {
  filter: brightness(0) saturate(100%);
}

.mcp-services-page.theme-light .nav-title {
  color: #1F1A16;
}

.mcp-services-page.theme-light .section-desc {
  color: rgba(31, 26, 22, 0.58);
}

.mcp-services-page.theme-light .loading-text {
  color: rgba(31, 26, 22, 0.4);
}

.mcp-services-page.theme-light .empty-title {
  color: rgba(31, 26, 22, 0.5);
}

.mcp-services-page.theme-light .empty-desc {
  color: rgba(31, 26, 22, 0.35);
}

.mcp-services-page.theme-light .service-card {
  background: rgba(255, 250, 244, 0.88);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 8rpx 24rpx rgba(118, 101, 80, 0.1);
}

.mcp-services-page.theme-light .service-name {
  color: #1F1A16;
}

.mcp-services-page.theme-light .service-url {
  color: rgba(31, 26, 22, 0.45);
}

.mcp-services-page.theme-light .tools-badge {
  background: rgba(47, 110, 234, 0.12);
}

.mcp-services-page.theme-light .tools-badge-text {
  color: rgba(47, 110, 234, 0.85);
}

.mcp-services-page.theme-light .tools-badge-warn {
  background: rgba(217, 119, 6, 0.1);
}

.mcp-services-page.theme-light .tools-badge-warn .tools-badge-text {
  color: rgba(217, 119, 6, 0.85);
}

.mcp-services-page.theme-light .toggle-switch {
  background: rgba(63, 53, 42, 0.12);
}

.mcp-services-page.theme-light .toggle-switch.toggle-on {
  background: #2F6EEA;
}

.mcp-services-page.theme-light .add-btn {
  background: #2F6EEA;
}
</style>
