<template>
  <view class="boot-debug-page">
    <view class="card">
      <text class="title">启动探针页</text>
      <text class="line">如果你能看到这行，说明 App 渲染层正常。</text>
      <text class="line">接下来请点击“进入登录页”继续测试。</text>
      <text class="line">平台：{{ platform }}</text>
      <text class="line">窗口：{{ windowSize }}</text>
      <text class="line">Token：{{ tokenState }}</text>
      <text class="line">启动阶段：{{ bootStage || '无' }}</text>
      <text class="line">最近全局错误：</text>
      <text class="error">{{ lastError || '无' }}</text>

      <view class="actions">
        <button class="btn primary" @click="goLogin">进入登录页</button>
        <button class="btn" @click="refreshInfo">刷新状态</button>
      </view>
    </view>
  </view>
</template>

<script>
import { getTokens } from '@/utils/storage'

export default {
  data() {
    return {
      platform: '',
      windowSize: '',
      tokenState: '',
      bootStage: '',
      lastError: ''
    }
  },
  onLoad() {
    this.refreshInfo()
  },
  methods: {
    refreshInfo() {
      try {
        const info = uni.getSystemInfoSync()
        this.platform = `${info.platform || '-'} / ${info.system || '-'}`
        this.windowSize = `${info.windowWidth || 0} x ${info.windowHeight || 0}`
      } catch (error) {
        this.platform = '读取失败'
        this.windowSize = '读取失败'
      }

      const tokens = getTokens()
      this.tokenState = tokens && tokens.access_token ? '存在 access_token' : '无 token'

      try {
        this.lastError = uni.getStorageSync('__last_runtime_error__') || ''
      } catch (error) {
        this.lastError = ''
      }

      try {
        const raw = uni.getStorageSync('__boot_stage__')
        if (raw) {
          const parsed = JSON.parse(raw)
          this.bootStage = `${parsed.stage || ''} @ ${parsed.time || ''}`
        } else {
          this.bootStage = ''
        }
      } catch (error) {
        this.bootStage = ''
      }
    },
    goLogin() {
      uni.reLaunch({
        url: '/pages/login/login'
      })
    }
  }
}
</script>

<style>
.boot-debug-page {
  min-height: 100vh;
  background: #f4f7ff;
  padding: 40rpx;
  box-sizing: border-box;
}

.card {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 30rpx;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.08);
}

.title {
  font-size: 36rpx;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 20rpx;
  display: block;
}

.line {
  font-size: 28rpx;
  color: #1f2937;
  margin-bottom: 12rpx;
  display: block;
}

.error {
  font-size: 24rpx;
  color: #b91c1c;
  margin-bottom: 20rpx;
  display: block;
  word-break: break-all;
}

.actions {
  display: flex;
  gap: 16rpx;
}

.btn {
  flex: 1;
  height: 84rpx;
  border-radius: 12rpx;
  border: 0;
  background: #e5e7eb;
  color: #111827;
  font-size: 28rpx;
  line-height: 84rpx;
}

.btn::after {
  border: 0;
}

.btn.primary {
  background: #2563eb;
  color: #ffffff;
}
</style>
