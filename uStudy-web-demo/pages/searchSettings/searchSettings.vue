<template>
  <view class="settings-page">
    <!-- Aurora Background -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Sidebar -->
    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @select-space="handleSelectSpace"
      @create-space="() => {}"
    />

    <!-- Main Content -->
    <view class="settings-main">
      <view class="settings-layout">
        <!-- Left navigation -->
        <view class="settings-nav">
          <view class="nav-header">
            <text class="nav-header-title">设置</text>
          </view>
          <view
            v-for="tab in tabs"
            :key="tab.id"
            class="nav-tab"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            <view class="nav-tab-indicator"></view>
            <view class="nav-tab-icon" v-html="tab.icon"></view>
            <text class="nav-tab-label">{{ tab.label }}</text>
          </view>
        </view>

        <!-- Right content -->
        <view class="settings-content">
          <!-- 搜索渠道 -->
          <view v-if="activeTab === 'search'" class="content-section">
            <text class="content-title">搜索渠道</text>
            <text class="content-desc">选择 AI 对话中可用的搜索渠道，关闭后 AI 将不会调用对应的搜索工具</text>

            <view class="card">
              <view v-for="(channel, idx) in channels" :key="channel.key" class="card-row">
                <view class="row-main">
                  <view class="row-icon" v-html="channel.icon"></view>
                  <view class="row-text">
                    <text class="row-label">{{ channel.label }}</text>
                    <text class="row-desc">{{ channel.desc }}</text>
                  </view>
                </view>
                <view
                  class="toggle"
                  :class="{ on: settings[channel.key] }"
                  @click="toggleChannel(channel.key)"
                >
                  <view class="toggle-thumb"></view>
                </view>
              </view>
            </view>

            <text class="card-note">所有搜索渠道均免费，无需额外配置。更改即时生效。</text>
          </view>

          <!-- 通用 (placeholder) -->
          <view v-else-if="activeTab === 'general'" class="content-section">
            <text class="content-title">通用</text>
            <text class="content-desc">通用偏好设置</text>
            <view class="card">
              <view class="card-row">
                <view class="row-main">
                  <view class="row-text">
                    <text class="row-label">语言</text>
                    <text class="row-desc">界面显示语言</text>
                  </view>
                </view>
                <text class="row-value">简体中文</text>
              </view>
            </view>
          </view>

          <!-- 账户与安全 (placeholder) -->
          <view v-else-if="activeTab === 'account'" class="content-section">
            <text class="content-title">账户与安全</text>
            <text class="content-desc">管理你的账户信息和安全设置</text>
            <view class="card">
              <view class="card-row card-row-clickable" @click="handleChangePassword">
                <view class="row-main">
                  <view class="row-text">
                    <text class="row-label">修改密码</text>
                    <text class="row-desc">更新登录密码</text>
                  </view>
                </view>
                <svg viewBox="0 0 256 256" width="16" height="16" class="row-arrow">
                  <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
              <view class="card-row card-row-clickable" @click="handleSubscription">
                <view class="row-main">
                  <view class="row-text">
                    <text class="row-label">订阅管理</text>
                    <text class="row-desc">查看和管理订阅计划</text>
                  </view>
                </view>
                <svg viewBox="0 0 256 256" width="16" height="16" class="row-arrow">
                  <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import { getSearchSettings, updateSearchSettings } from '@/api/searchSettings'

export default {
  components: { HomeSidebar },

  data() {
    return {
      sidebarCollapsed: false,
      activeTab: 'search',
      tabs: [
        {
          id: 'general',
          label: '通用',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><rect width="256" height="256" fill="none"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M41.43,178.09A99.14,99.14,0,0,1,31.36,153.8l16.78-21a81.59,81.59,0,0,1,0-9.64l-16.77-21a99.43,99.43,0,0,1,10.05-24.3l26.71-3a81,81,0,0,1,6.81-6.81l3-26.7A99.14,99.14,0,0,1,102.2,31.36l21,16.78a81.59,81.59,0,0,1,9.64,0l21-16.77a99.43,99.43,0,0,1,24.3,10.05l3,26.71a81,81,0,0,1,6.81,6.81l26.7,3a99.14,99.14,0,0,1,10.07,24.29l-16.78,21a81.59,81.59,0,0,1,0,9.64l16.77,21a99.43,99.43,0,0,1-10,24.3l-26.71,3a81,81,0,0,1-6.81,6.81l-3,26.7a99.14,99.14,0,0,1-24.29,10.07l-21-16.78a81.59,81.59,0,0,1-9.64,0l-21,16.77a99.43,99.43,0,0,1-24.3-10l-3-26.71a81,81,0,0,1-6.81-6.81Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>'
        },
        {
          id: 'search',
          label: '搜索',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><circle cx="112" cy="112" r="80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="168" y1="168" x2="224" y2="224" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>'
        },
        {
          id: 'account',
          label: '账户',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><circle cx="128" cy="96" r="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M32,216c19.37-33.47,54.55-56,96-56s76.63,22.53,96,56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>'
        }
      ],
      settings: {
        web_search_enabled: true,
        academic_search_enabled: true,
        encyclopedia_search_enabled: true,
        course_search_enabled: true
      },
      channels: [
        {
          key: 'web_search_enabled',
          label: '联网搜索',
          desc: 'DuckDuckGo 通用网页搜索',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><circle cx="112" cy="112" r="80" fill="none" stroke="currentColor" stroke-width="16"/><line x1="168" y1="168" x2="224" y2="224" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>'
        },
        {
          key: 'academic_search_enabled',
          label: '学术搜索',
          desc: 'Semantic Scholar 学术论文',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><path d="M251.76,88.94l-120-64a8,8,0,0,0-7.52,0l-120,64a8,8,0,0,0,0,14.12L32,117.31v48.27A16.07,16.07,0,0,0,43,180.65l72.27,38.54a16,16,0,0,0,15.1.33L208,178.67V120l32,16v64a8,8,0,0,0,16,0V96A8,8,0,0,0,251.76,88.94Z" fill="currentColor"/></svg>'
        },
        {
          key: 'encyclopedia_search_enabled',
          label: '百科搜索',
          desc: '维基百科中英文词条',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><path d="M48,216a8,8,0,0,1-8-8V48a8,8,0,0,1,8-8H208a8,8,0,0,1,8,8V208a8,8,0,0,1-8,8Z" fill="none" stroke="currentColor" stroke-width="16"/><line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-width="16"/><line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-width="16"/></svg>'
        },
        {
          key: 'course_search_enabled',
          label: '课程搜索',
          desc: 'B站教育视频与课程',
          icon: '<svg viewBox="0 0 256 256" width="18" height="18"><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-width="16"/><line x1="128" y1="32" x2="128" y2="224" fill="none" stroke="currentColor" stroke-width="16"/><path d="M40,128c0-35,39-64,88-64s88,29,88,64-39,64-88,64S40,163,40,128Z" fill="none" stroke="currentColor" stroke-width="16"/></svg>'
        }
      ]
    }
  },

  onLoad() {
    this.loadSettings()
  },

  methods: {
    handleSelectSpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${spaceId}` })
    },

    handleChangePassword() {
      uni.navigateTo({ url: '/pages/resetPassword/resetPassword' })
    },

    handleSubscription() {
      uni.navigateTo({ url: '/pages/activation/activation' })
    },

    async loadSettings() {
      try {
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
      }
    },

    async toggleChannel(key) {
      const newValue = !this.settings[key]
      this.settings = { ...this.settings, [key]: newValue }

      try {
        await updateSearchSettings({ [key]: newValue })
      } catch (error) {
        this.settings = { ...this.settings, [key]: !newValue }
      }
    }
  }
}
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: row;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: #0A0A12;
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 1200px;
  height: 1200px;
  background: radial-gradient(circle, rgba(59,130,246,0.32) 0%, rgba(59,130,246,0.12) 45%, transparent 75%);
  top: -25%;
  left: -10%;
  filter: blur(90px);
  animation: aurora-drift-a 12s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 850px;
  height: 850px;
  background: radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(249,115,22,0.09) 45%, transparent 75%);
  top: 10%;
  right: -10%;
  filter: blur(70px);
  animation: aurora-drift-b 10s ease-in-out infinite;
}

.aurora-blob-3 {
  width: 950px;
  height: 950px;
  background: radial-gradient(circle, rgba(79,70,229,0.20) 0%, rgba(79,70,229,0.08) 45%, transparent 75%);
  bottom: -15%;
  left: 25%;
  filter: blur(90px);
  animation: aurora-drift-c 14s ease-in-out infinite;
}

@keyframes aurora-drift-a {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(50px, 35px) scale(1.06); }
  66% { transform: translate(-25px, 15px) scale(0.97); }
}

@keyframes aurora-drift-b {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-40px, 30px) scale(1.05); }
  66% { transform: translate(20px, -25px) scale(0.98); }
}

@keyframes aurora-drift-c {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -35px) scale(1.07); }
  66% { transform: translate(-20px, 20px) scale(0.96); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
}

/* Main Content Area */
.settings-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 1;
}

/* Two-column layout */
.settings-layout {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* Left nav — subtle glass */
.settings-nav {
  width: 200px;
  flex-shrink: 0;
  padding: 0 0 16px;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.nav-header {
  padding: 18px 20px 14px;
}

.nav-header-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  cursor: pointer;
  position: relative;
  transition: background 0.15s ease;
}

.nav-tab:hover {
  background: rgba(255, 255, 255, 0.03);
}

.nav-tab.active {
  background: rgba(255, 255, 255, 0.04);
}

/* Vertical line indicator */
.nav-tab-indicator {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: transparent;
  transition: background 0.2s ease;
}

.nav-tab.active .nav-tab-indicator {
  background: #8b5cf6;
}

.nav-tab-icon {
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
  transition: color 0.15s ease;
}

.nav-tab.active .nav-tab-icon {
  color: rgba(255, 255, 255, 0.85);
}

.nav-tab-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  font-weight: 500;
  transition: color 0.15s ease;
}

.nav-tab.active .nav-tab-label {
  color: rgba(255, 255, 255, 0.9);
}

/* Right content */
.settings-content {
  flex: 1;
  padding: 28px 36px;
  overflow-y: auto;
  min-height: 0;
}

/* Thin scrollbar */
.settings-content::-webkit-scrollbar {
  width: 6px;
}

.settings-content::-webkit-scrollbar-track {
  background: transparent;
}

.settings-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.settings-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.18);
}

.content-section {
  max-width: 560px;
}

.content-title {
  font-size: 18px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  display: block;
  margin-bottom: 6px;
}

.content-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.38);
  line-height: 1.5;
  display: block;
  margin-bottom: 20px;
}

/* Card — frosted glass */
.card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  overflow: hidden;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  transition: background 0.12s ease;
}

.card-row + .card-row {
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.card-row-clickable {
  cursor: pointer;
}

.card-row-clickable:hover {
  background: rgba(255, 255, 255, 0.03);
}

.row-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.row-icon {
  color: rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.row-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.row-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

.row-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.38);
}

.row-value {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}

.row-arrow {
  color: rgba(255, 255, 255, 0.25);
  flex-shrink: 0;
}

/* Toggle */
.toggle {
  width: 42px;
  height: 24px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  position: relative;
  transition: all 0.25s ease;
  flex-shrink: 0;
  cursor: pointer;
}

.toggle.on {
  background: rgba(139, 92, 246, 0.65);
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.3);
}

.toggle-thumb {
  width: 18px;
  height: 18px;
  border-radius: 9px;
  background: #fff;
  position: absolute;
  top: 3px;
  left: 3px;
  transition: transform 0.25s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

.toggle.on .toggle-thumb {
  transform: translateX(18px);
}

/* Note */
.card-note {
  display: block;
  margin-top: 12px;
  padding: 0 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.25);
  line-height: 1.5;
}
</style>
