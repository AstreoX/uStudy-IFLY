<template>
  <view class="mcp-detail-page" :class="pageThemeClass">
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
      <text class="nav-title">{{ isEditing ? '编辑 MCP 服务' : '添加 MCP 服务' }}</text>
      <view v-if="isEditing" class="nav-right" @click="confirmDelete">
        <image class="nav-icon nav-icon-delete" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
      </view>
      <view v-else class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <scroll-view scroll-y class="content-scroll">
      <view class="content-area">
        <!-- Form -->
        <view class="form-section">
          <view class="form-group">
            <text class="form-label">服务名称</text>
            <view class="form-input-wrap">
              <input
                class="form-input"
                v-model="form.name"
                placeholder="如：Notion、飞书"
                placeholder-class="input-placeholder"
                maxlength="100"
              />
            </view>
          </view>

          <view class="form-group">
            <text class="form-label">服务地址 (URL)</text>
            <view class="form-input-wrap">
              <input
                class="form-input"
                v-model="form.url"
                placeholder="https://..."
                placeholder-class="input-placeholder"
                type="url"
              />
            </view>
          </view>

          <view class="form-group">
            <text class="form-label">API Key <text class="form-label-optional">(可选)</text></text>
            <view class="form-input-wrap">
              <input
                class="form-input"
                v-model="form.api_key"
                placeholder="服务认证密钥"
                placeholder-class="input-placeholder"
                :password="!showApiKey"
              />
              <view class="input-suffix" @click="showApiKey = !showApiKey">
                <image
                  class="suffix-icon"
                  :src="showApiKey
                    ? '/static/icons/phosphor-icons/SVGs/regular/eye.svg'
                    : '/static/icons/phosphor-icons/SVGs/regular/eye-slash.svg'"
                  mode="aspectFit"
                ></image>
              </view>
            </view>
          </view>
        </view>

        <!-- Test Connection -->
        <view class="test-section">
          <view
            class="test-btn"
            :class="{ 'test-btn-loading': isTesting }"
            @click="testConnection"
          >
            <text class="test-btn-text">{{ isTesting ? '连接中...' : '测试连接' }}</text>
          </view>

          <!-- Test Result -->
          <view v-if="testResult" class="test-result" :class="testResult.success ? 'test-success' : 'test-error'">
            <text class="test-result-text">{{ testResult.success ? '连接成功' : testResult.error }}</text>
          </view>
        </view>

        <!-- Tools Preview -->
        <view v-if="discoveredTools.length > 0" class="tools-section">
          <text class="section-title">可用工具 ({{ discoveredTools.length }})</text>
          <view class="tools-card">
            <view
              v-for="(tool, index) in discoveredTools"
              :key="tool.name"
            >
              <view class="tool-item">
                <text class="tool-name">{{ tool.name }}</text>
                <text class="tool-desc">{{ tool.description || '无描述' }}</text>
              </view>
              <view v-if="index < discoveredTools.length - 1" class="tools-divider"></view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- Bottom Save Button -->
    <view class="bottom-bar">
      <view
        class="save-btn"
        :class="{ 'save-btn-disabled': !canSave || isSaving }"
        @click="saveService"
      >
        <text class="save-btn-text">{{ isSaving ? '保存中...' : '保存' }}</text>
      </view>
    </view>

    <!-- Delete Confirm Modal -->
    <view v-if="showDeleteModal" class="modal-mask" @click="showDeleteModal = false">
      <view class="modal-content" @click.stop>
        <text class="modal-title">删除服务</text>
        <text class="modal-desc">确定删除「{{ form.name }}」？删除后 AI 将无法使用该服务的工具。</text>
        <view class="modal-buttons">
          <view class="modal-btn modal-btn-cancel" @click="showDeleteModal = false">
            <text class="modal-btn-text">取消</text>
          </view>
          <view class="modal-btn modal-btn-danger" @click="doDelete">
            <text class="modal-btn-text modal-btn-text-danger">删除</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getMcpServices, createMcpService, updateMcpService, deleteMcpService, testMcpConnection } from '@/api/mcp'
import { getStoredThemeMode } from '@/utils/themeMode'
import { goBack } from '@/utils/navigation'

export default {
  data() {
    return {
      homeThemeMode: 'dark',
      serviceId: null,
      form: {
        name: '',
        url: '',
        api_key: ''
      },
      showApiKey: false,
      isTesting: false,
      testResult: null,
      discoveredTools: [],
      isSaving: false,
      showDeleteModal: false,
      originalService: null
    }
  },

  computed: {
    isLightTheme() {
      return this.homeThemeMode === 'light'
    },

    pageThemeClass() {
      return this.isLightTheme ? 'theme-light' : 'theme-dark'
    },

    isEditing() {
      return !!this.serviceId
    },

    canSave() {
      return this.form.name.trim() && this.form.url.trim()
    }
  },

  onLoad(options) {
    this.restoreThemeMode()
    if (options.service_id) {
      this.serviceId = options.service_id
      this.loadService()
    }
  },

  onShow() {
    this.restoreThemeMode()
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

    async loadService() {
      try {
        const res = await getMcpServices()
        const services = res?.services || []
        const service = services.find(s => s.id === this.serviceId)
        if (service) {
          this.originalService = service
          this.form = {
            name: service.name,
            url: service.url,
            api_key: ''
          }
          this.discoveredTools = service.tools || []
        }
      } catch (error) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }
    },

    async testConnection() {
      if (!this.form.url.trim()) {
        uni.showToast({ title: '请填写服务地址', icon: 'none' })
        return
      }

      this.isTesting = true
      this.testResult = null

      try {
        const payload = { url: this.form.url.trim() }
        if (this.form.api_key.trim()) {
          payload.api_key = this.form.api_key.trim()
        }
        const res = await testMcpConnection(payload)
        this.testResult = res
        if (res.success) {
          this.discoveredTools = res.tools || []
        }
      } catch (error) {
        this.testResult = { success: false, error: '请求失败，请检查网络' }
      } finally {
        this.isTesting = false
      }
    },

    async saveService() {
      if (!this.canSave || this.isSaving) return

      const data = {
        name: this.form.name.trim(),
        url: this.form.url.trim()
      }
      if (this.form.api_key.trim()) {
        data.api_key = this.form.api_key.trim()
      }

      this.isSaving = true
      try {
        if (this.isEditing) {
          await updateMcpService(this.serviceId, data)
        } else {
          await createMcpService(data)
        }
        uni.showToast({ title: '保存成功', icon: 'success' })
        setTimeout(() => goBack(), 500)
      } catch (error) {
        const msg = error?.data?.detail?.message || '保存失败'
        uni.showToast({ title: msg, icon: 'none' })
      } finally {
        this.isSaving = false
      }
    },

    confirmDelete() {
      this.showDeleteModal = true
    },

    async doDelete() {
      this.showDeleteModal = false
      try {
        await deleteMcpService(this.serviceId)
        uni.showToast({ title: '已删除', icon: 'success' })
        setTimeout(() => goBack(), 500)
      } catch (error) {
        uni.showToast({ title: '删除失败', icon: 'none' })
      }
    }
  }
}
</script>

<style scoped>
.mcp-detail-page {
  min-height: 100vh;
  background: #0A0A12;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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

.nav-left,
.nav-right {
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

.nav-icon-delete {
  opacity: 0.5;
}

.nav-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
  text-align: center;
}

.nav-right-placeholder {
  width: 60rpx;
}

/* Content */
.content-scroll {
  flex: 1;
  position: relative;
  z-index: 1;
  padding-bottom: 140rpx;
}

.content-area {
  padding: 24rpx 32rpx;
}

/* Form */
.form-section {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.form-label {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.form-label-optional {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
  font-weight: 400;
}

.form-input-wrap {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  padding: 0 24rpx;
  height: 88rpx;
  display: flex;
  align-items: center;
}

.form-input {
  flex: 1;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.9);
  height: 100%;
}

.input-placeholder {
  color: rgba(255, 255, 255, 0.25);
}

.input-suffix {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 8rpx;
}

.suffix-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
}

/* Test Connection */
.test-section {
  margin-top: 40rpx;
}

.test-btn {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 16rpx;
  padding: 20rpx 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.test-btn-loading {
  opacity: 0.6;
}

.test-btn-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.test-result {
  margin-top: 16rpx;
  padding: 16rpx 20rpx;
  border-radius: 12rpx;
}

.test-success {
  background: rgba(34, 197, 94, 0.1);
}

.test-error {
  background: rgba(239, 68, 68, 0.1);
}

.test-result-text {
  font-size: 24rpx;
  line-height: 1.5;
}

.test-success .test-result-text {
  color: rgba(34, 197, 94, 0.85);
}

.test-error .test-result-text {
  color: rgba(239, 68, 68, 0.85);
}

/* Tools Section */
.tools-section {
  margin-top: 40rpx;
}

.section-title {
  font-size: 26rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 16rpx;
}

.tools-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 0 24rpx;
  overflow: hidden;
}

.tool-item {
  padding: 20rpx 0;
}

.tool-name {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
  font-family: monospace;
}

.tool-desc {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4rpx;
  line-height: 1.4;
}

.tools-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.06);
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

.save-btn {
  background: rgba(139, 92, 246, 0.85);
  border-radius: 20rpx;
  padding: 24rpx 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.save-btn-disabled {
  opacity: 0.4;
}

.save-btn-text {
  font-size: 30rpx;
  color: #fff;
  font-weight: 600;
}

/* Delete Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  width: 560rpx;
  background: #1E1E26;
  border-radius: 24rpx;
  padding: 40rpx 32rpx 32rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 16rpx;
}

.modal-desc {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.5;
  margin-bottom: 32rpx;
}

.modal-buttons {
  display: flex;
  gap: 16rpx;
}

.modal-btn {
  flex: 1;
  padding: 20rpx 0;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-btn-cancel {
  background: rgba(255, 255, 255, 0.08);
}

.modal-btn-danger {
  background: rgba(239, 68, 68, 0.2);
}

.modal-btn-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.modal-btn-text-danger {
  color: rgba(239, 68, 68, 0.9);
}

/* ===== Light Theme ===== */
.mcp-detail-page.theme-light {
  background: #F3EDE3;
}

.mcp-detail-page.theme-light .aurora-blob-1 {
  background: rgba(47, 110, 234, 0.18);
}

.mcp-detail-page.theme-light .aurora-blob-2 {
  background: rgba(199, 119, 22, 0.14);
}

.mcp-detail-page.theme-light .nav-icon,
.mcp-detail-page.theme-light .suffix-icon {
  filter: brightness(0) saturate(100%);
}

.mcp-detail-page.theme-light .nav-title {
  color: #1F1A16;
}

.mcp-detail-page.theme-light .form-label {
  color: rgba(31, 26, 22, 0.65);
}

.mcp-detail-page.theme-light .form-label-optional {
  color: rgba(31, 26, 22, 0.35);
}

.mcp-detail-page.theme-light .form-input-wrap {
  background: rgba(255, 250, 244, 0.88);
  border-color: rgba(63, 53, 42, 0.12);
}

.mcp-detail-page.theme-light .form-input {
  color: #1F1A16;
}

.mcp-detail-page.theme-light .input-placeholder {
  color: rgba(31, 26, 22, 0.3);
}

.mcp-detail-page.theme-light .test-btn {
  background: rgba(255, 250, 244, 0.88);
  border-color: rgba(63, 53, 42, 0.12);
}

.mcp-detail-page.theme-light .test-btn-text {
  color: rgba(31, 26, 22, 0.65);
}

.mcp-detail-page.theme-light .section-title {
  color: rgba(31, 26, 22, 0.6);
}

.mcp-detail-page.theme-light .tools-card {
  background: rgba(255, 250, 244, 0.88);
  border-color: rgba(63, 53, 42, 0.1);
}

.mcp-detail-page.theme-light .tool-name {
  color: #1F1A16;
}

.mcp-detail-page.theme-light .tool-desc {
  color: rgba(31, 26, 22, 0.5);
}

.mcp-detail-page.theme-light .tools-divider {
  background: rgba(63, 53, 42, 0.08);
}

.mcp-detail-page.theme-light .save-btn {
  background: #2F6EEA;
}

.mcp-detail-page.theme-light .modal-content {
  background: #FAF6F0;
}

.mcp-detail-page.theme-light .modal-title {
  color: #1F1A16;
}

.mcp-detail-page.theme-light .modal-desc {
  color: rgba(31, 26, 22, 0.55);
}

.mcp-detail-page.theme-light .modal-btn-cancel {
  background: rgba(63, 53, 42, 0.08);
}

.mcp-detail-page.theme-light .modal-btn-text {
  color: rgba(31, 26, 22, 0.65);
}
</style>
