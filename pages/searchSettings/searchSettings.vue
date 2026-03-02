<template>
  <view class="search-settings-page">
    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <svg viewBox="0 0 256 256" width="20" height="20" class="nav-icon">
          <polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        </svg>
      </view>
      <text class="nav-title">搜索设置</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <view class="section-title">搜索渠道</view>
      <view class="section-desc">选择 AI 对话中可用的搜索渠道，关闭后 AI 将不会调用对应的搜索工具</view>

      <view class="settings-card">
        <view v-for="(channel, idx) in channels" :key="channel.key" class="settings-item-wrap">
          <view class="settings-item">
            <view class="item-left">
              <view class="item-icon" v-html="channel.icon"></view>
              <view class="item-text">
                <text class="item-label">{{ channel.label }}</text>
                <text class="item-desc">{{ channel.desc }}</text>
              </view>
            </view>
            <view class="toggle-switch" :class="{ 'toggle-on': settings[channel.key] }"
              @click="toggleChannel(channel.key)">
              <view class="toggle-thumb"></view>
            </view>
          </view>
          <view v-if="idx < channels.length - 1" class="settings-divider"></view>
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
    goBack() {
      uni.navigateBack()
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
.search-settings-page {
  min-height: 100vh;
  background: #0A0A12;
}

.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 56px;
}

.nav-left {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 8px;
}

.nav-left:hover {
  background: rgba(255, 255, 255, 0.06);
}

.nav-icon {
  color: rgba(255, 255, 255, 0.7);
}

.nav-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.nav-right-placeholder {
  width: 36px;
}

.content-area {
  padding: 16px 24px;
  max-width: 480px;
  margin: 0 auto;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  margin-bottom: 4px;
}

.section-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 16px;
  line-height: 1.5;
}

.settings-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 0 16px;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.item-icon {
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.item-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

.item-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.settings-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
}

.toggle-switch {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  position: relative;
  transition: background 0.25s ease;
  flex-shrink: 0;
  cursor: pointer;
}

.toggle-switch.toggle-on {
  background: rgba(139, 92, 246, 0.7);
}

.toggle-thumb {
  width: 20px;
  height: 20px;
  border-radius: 10px;
  background: #fff;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform 0.25s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.toggle-on .toggle-thumb {
  transform: translateX(20px);
}

.settings-note {
  margin-top: 16px;
  padding: 0 4px;
}

.note-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  line-height: 1.5;
}
</style>
