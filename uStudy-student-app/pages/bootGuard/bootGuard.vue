<template>
  <view class="boot-page">
    <view class="card">
      <text class="title">uStudy 启动检测</text>
      <text class="line">如果你能看到这个页面，说明 App 渲染正常。</text>
      <text class="line">2 秒后自动跳转到登录页。</text>
      <button class="btn" @click="goLogin">立即进入登录页</button>
    </view>
  </view>
</template>

<script>
export default {
  onLoad() {
    this.timer = setTimeout(() => {
      this.goLogin()
    }, 2000)
  },
  onUnload() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  },
  methods: {
    goLogin() {
      uni.reLaunch({
        url: '/pages/login/login'
      })
    }
  }
}
</script>

<style>
.boot-page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 40rpx;
  box-sizing: border-box;
}

.card {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 28rpx;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.08);
}

.title {
  font-size: 36rpx;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16rpx;
  display: block;
}

.line {
  font-size: 28rpx;
  color: #334155;
  margin-bottom: 12rpx;
  display: block;
}

.btn {
  margin-top: 12rpx;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 12rpx;
  border: 0;
  background: #2563eb;
  color: #ffffff;
  font-size: 28rpx;
}

.btn::after {
  border: 0;
}
</style>
