<template>
  <view class="history-page" :class="pageThemeClass">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="history-nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">更新公告</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <scroll-view scroll-y class="content-area">
      <!-- Loading State -->
      <view v-if="loading" class="loading-state">
        <text class="loading-text">加载中...</text>
      </view>

      <template v-else>
        <!-- Version History Section -->
        <view v-if="versionHistory.length > 0" class="section">
          <text class="section-title">版本更新</text>
          <view class="card-list">
            <view
              v-for="ver in versionHistory"
              :key="ver.versionName"
              class="history-card"
              @click="showVersionDetail(ver)"
            >
              <view class="card-row">
                <view class="card-left">
                  <text class="card-version">v{{ ver.versionName }}</text>
                  <text class="card-date">{{ ver.releaseDate }}</text>
                </view>
                <image class="card-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
              </view>
            </view>
          </view>
        </view>

        <!-- Announcements Section -->
        <view v-if="announcements.length > 0" class="section">
          <text class="section-title">通知公告</text>
          <view class="card-list">
            <view
              v-for="ann in announcements"
              :key="ann.id"
              class="history-card"
              @click="showAnnouncementDetail(ann)"
            >
              <view class="card-row">
                <view class="card-left">
                  <view class="card-tag" :class="'tag-' + ann.type">
                    <text class="card-tag-text">{{ getTypeLabel(ann.type) }}</text>
                  </view>
                  <text class="card-title">{{ ann.title }}</text>
                  <text class="card-date">{{ ann.date }}</text>
                </view>
                <image class="card-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
              </view>
            </view>
          </view>
        </view>

        <!-- Empty State -->
        <view v-if="versionHistory.length === 0 && announcements.length === 0" class="empty-state">
          <text class="empty-text">暂无更新公告</text>
        </view>
      </template>
    </scroll-view>

    <!-- Detail Overlay -->
    <view v-if="showDetail" class="detail-overlay" @touchmove.stop.prevent>
      <view class="detail-backdrop" :class="{ 'backdrop-show': detailAnimated }" @click="closeDetail"></view>
      <view class="detail-card" :class="{ 'detail-show': detailAnimated }">
        <view class="detail-header">
          <text class="detail-title">{{ detailTitle }}</text>
          <view class="detail-close" @click="closeDetail">
            <text class="detail-close-icon">×</text>
          </view>
        </view>
        <scroll-view scroll-y class="detail-body">
          <markdown-render v-if="detailContent" :content="detailContent" :theme-mode="homeThemeMode" />
          <text v-else class="detail-loading">加载中...</text>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script>
import { useUpdateStore } from '@/store/update'
import { fetchReleaseManifest, fetchMarkdownContent } from '@/api/release'
import { goBack } from '@/utils/navigation'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import { getStoredThemeMode } from '@/utils/themeMode'

const TYPE_LABELS = {
  maintenance: '维护通知',
  feature: '功能更新',
  notice: '系统公告'
}

export default {
  components: { MarkdownRender },

  data() {
    return {
      loading: true,
      versionHistory: [],
      announcements: [],
      homeThemeMode: 'dark',
      showDetail: false,
      detailAnimated: false,
      detailTitle: '',
      detailContent: ''
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

  async onShow() {
    this.restoreThemeMode()
    await this.loadData()
  },

  methods: {
    restoreThemeMode() {
      this.homeThemeMode = getStoredThemeMode('dark')
      this.syncThemeSystemUi(this.homeThemeMode)
    },

    syncThemeSystemUi(mode) {
      const isLight = mode === 'light'
      // #ifdef APP-PLUS
      plus.navigator.setStatusBarStyle(isLight ? 'dark' : 'light')
      plus.navigator.setStatusBarBackground(isLight ? '#F3EDE3' : '#1D1E20')
      // #endif
    },

    goBack() {
      goBack()
    },

    getTypeLabel(type) {
      return TYPE_LABELS[type] || '公告'
    },

    async loadData() {
      this.loading = true
      try {
        const updateStore = useUpdateStore()
        let manifest = updateStore.manifest

        if (!manifest) {
          manifest = await fetchReleaseManifest()
          updateStore.setManifest(manifest)
        }

        // Build version history: latest + history entries
        const history = []
        if (manifest.latestVersion) {
          history.push({
            versionName: manifest.latestVersion.versionName,
            versionCode: manifest.latestVersion.versionCode,
            releaseDate: manifest.latestVersion.releaseDate,
            changelog: manifest.latestVersion.changelog
          })
        }
        if (manifest.versionHistory) {
          history.push(...manifest.versionHistory)
        }
        this.versionHistory = history
        this.announcements = manifest.announcements || []
      } catch (error) {
        this.versionHistory = []
        this.announcements = []
      } finally {
        this.loading = false
      }
    },

    async showVersionDetail(ver) {
      this.detailTitle = `v${ver.versionName} 更新日志`
      this.detailContent = ''
      this.showDetail = true
      this.$nextTick(() => {
        setTimeout(() => { this.detailAnimated = true }, 10)
      })

      try {
        this.detailContent = await fetchMarkdownContent(ver.changelog)
      } catch (error) {
        this.detailContent = '加载失败'
      }
    },

    async showAnnouncementDetail(ann) {
      this.detailTitle = ann.title
      this.detailContent = ''
      this.showDetail = true
      this.$nextTick(() => {
        setTimeout(() => { this.detailAnimated = true }, 10)
      })

      try {
        this.detailContent = await fetchMarkdownContent(ann.body)
      } catch (error) {
        this.detailContent = '加载失败'
      }
    },

    closeDetail() {
      this.detailAnimated = false
      setTimeout(() => {
        this.showDetail = false
        this.detailContent = ''
      }, 250)
    }
  }
}
</script>

<style>
.history-page {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A12;
  position: relative;
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120rpx);
}

.aurora-blob-1 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, #1A6AFF 0%, transparent 70%);
  top: -200rpx;
  left: -100rpx;
  opacity: 0.35;
}

.aurora-blob-2 {
  width: 550rpx;
  height: 550rpx;
  background: radial-gradient(circle, #FF6A1A 0%, transparent 70%);
  bottom: 10%;
  right: -100rpx;
  opacity: 0.3;
}

.aurora-blob-3 {
  width: 400rpx;
  height: 400rpx;
  background: radial-gradient(circle, #FF9F45 0%, transparent 70%);
  top: 40%;
  left: 20%;
  opacity: 0.2;
}

/* Navigation Bar */
.history-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08), 0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

/* Content */
.content-area {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100vh;
  padding-top: calc(100vh * 3.5 / 26);
  padding-bottom: calc(48rpx + env(safe-area-inset-bottom));
}

.loading-state {
  display: flex;
  justify-content: center;
  padding-top: 120rpx;
}

.loading-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.4);
}

/* Section */
.section {
  margin: 0 calc(100vw / 24) 32rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 20rpx;
  display: block;
}

.card-list {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 24rpx;
  overflow: hidden;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

.history-card {
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
}

.history-card:last-child {
  border-bottom: none;
}

.history-card:active {
  background: rgba(255, 255, 255, 0.04);
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.card-version {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
}

.card-title {
  font-size: 30rpx;
  font-weight: 500;
  color: #ffffff;
}

.card-date {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
}

.card-tag {
  align-self: flex-start;
  padding: 4rpx 14rpx;
  border-radius: 6rpx;
  margin-bottom: 4rpx;
}

.tag-maintenance {
  background: rgba(251, 146, 60, 0.15);
}

.tag-maintenance .card-tag-text {
  color: #FB923C;
}

.tag-feature {
  background: rgba(34, 197, 94, 0.15);
}

.tag-feature .card-tag-text {
  color: #22C55E;
}

.tag-notice {
  background: rgba(0, 136, 255, 0.15);
}

.tag-notice .card-tag-text {
  color: #0088FF;
}

.card-tag-text {
  font-size: 20rpx;
  font-weight: 600;
}

.card-arrow {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  flex-shrink: 0;
  margin-left: 16rpx;
}

/* Empty State */
.empty-state {
  display: flex;
  justify-content: center;
  padding-top: 120rpx;
}

.empty-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.35);
}

/* Detail Overlay */
.detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 250ms ease;
}

.detail-backdrop.backdrop-show {
  background: rgba(0, 0, 0, 0.7);
}

.detail-card {
  position: relative;
  width: 88%;
  max-height: 72vh;
  background: rgba(18, 18, 28, 0.92);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 28rpx;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transform: translateY(60rpx) scale(0.92);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.detail-card.detail-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.detail-header {
  padding: 32rpx 36rpx 20rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
  flex: 1;
}

.detail-close {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 50%;
  flex-shrink: 0;
  margin-left: 16rpx;
}

.detail-close-icon {
  font-size: 36rpx;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1;
}

.detail-body {
  flex: 1;
  padding: 0 36rpx 36rpx;
  max-height: 55vh;
  box-sizing: border-box;
  overflow-wrap: break-word;
}

.detail-loading {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.4);
}

.history-page.theme-light {
  background-color: #F3EDE3;
}

.history-page.theme-light .aurora-blob-1 {
  background: radial-gradient(circle, rgba(47, 110, 234, 0.2) 0%, transparent 72%);
  opacity: 0.9;
}

.history-page.theme-light .aurora-blob-2 {
  background: radial-gradient(circle, rgba(199, 119, 22, 0.18) 0%, transparent 72%);
  opacity: 0.82;
}

.history-page.theme-light .aurora-blob-3 {
  background: radial-gradient(circle, rgba(111, 150, 236, 0.12) 0%, transparent 70%);
  opacity: 0.72;
}

.history-page.theme-light .nav-left,
.history-page.theme-light .card-list,
.history-page.theme-light .detail-card,
.history-page.theme-light .detail-close {
  background: rgba(255, 250, 244, 0.88);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 16rpx 40rpx rgba(118, 101, 80, 0.14);
}

.history-page.theme-light .nav-icon,
.history-page.theme-light .card-arrow {
  filter: brightness(0) saturate(100%);
}

.history-page.theme-light .nav-title,
.history-page.theme-light .card-version,
.history-page.theme-light .card-title,
.history-page.theme-light .detail-title {
  color: #1F1A16;
}

.history-page.theme-light .loading-text,
.history-page.theme-light .section-title,
.history-page.theme-light .card-date,
.history-page.theme-light .empty-text,
.history-page.theme-light .detail-loading,
.history-page.theme-light .detail-close-icon {
  color: rgba(31, 26, 22, 0.58);
}

.history-page.theme-light .history-card {
  border-bottom-color: rgba(63, 53, 42, 0.08);
}

.history-page.theme-light .history-card:active {
  background: rgba(63, 53, 42, 0.04);
}

.history-page.theme-light .detail-backdrop.backdrop-show {
  background: rgba(61, 46, 30, 0.22);
}
</style>
