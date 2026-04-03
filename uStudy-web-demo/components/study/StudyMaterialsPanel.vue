<template>
  <view class="materials-panel">
    <view class="materials-toolbar">
      <view class="materials-title-wrap">
        <text class="materials-title">学习资料</text>
        <text v-if="hasSpace" class="materials-count">{{ documents.length }} 项</text>
      </view>

      <view class="materials-actions">
        <view class="toolbar-btn toolbar-btn-refresh" @tap="loadDocuments" :class="{ 'toolbar-btn-disabled': loading || !hasSpace }">
          <image
            class="toolbar-btn-icon toolbar-btn-refresh-icon"
            mode="aspectFit"
            src="/static/icons/phosphor/regular/arrow-clockwise-white.svg"
          />
        </view>
        <view class="toolbar-btn toolbar-btn-primary" @tap="toggleAddMenu" :class="{ 'toolbar-btn-disabled': !hasSpace }">
          <image
            class="toolbar-btn-icon"
            mode="aspectFit"
            src="/static/icons/phosphor/regular/plus.svg"
          />
        </view>
      </view>
    </view>

    <view v-if="showAddMenu" class="add-menu-overlay" @tap="showAddMenu = false">
      <view class="add-menu" @tap.stop>
        <view class="add-menu-item" @tap="handleAddDocument">
          <text class="add-menu-item-text">添加文档</text>
        </view>
        <view class="add-menu-divider"></view>
        <view class="add-menu-item" @tap="handleAddLink">
          <text class="add-menu-item-text">添加链接</text>
        </view>
      </view>
    </view>

    <view
      v-if="showLinkDialog"
      class="link-dialog-overlay"
      :class="{ 'overlay-show': linkDialogVisible }"
      @tap="closeLinkDialog"
    >
      <view class="link-dialog" :class="{ 'dialog-show': linkDialogVisible }" @tap.stop>
        <text class="link-dialog-title">添加链接</text>
        <view class="link-dialog-content">
          <view class="link-input-group">
            <text class="link-input-label">标题</text>
            <input
              class="link-input"
              v-model="linkTitle"
              placeholder="输入链接标题"
              maxlength="255"
            />
          </view>
          <view class="link-input-group">
            <text class="link-input-label">网址</text>
            <input
              class="link-input"
              v-model="linkUrl"
              placeholder="https://example.com"
              maxlength="2048"
              @confirm="submitLink"
            />
          </view>
        </view>
        <view class="link-dialog-actions">
          <view class="link-btn link-btn-cancel" @tap="closeLinkDialog">
            <text class="link-btn-text">取消</text>
          </view>
          <view
            class="link-btn link-btn-confirm"
            :class="{ 'link-btn-disabled': isAddingLink }"
            @tap="submitLink"
          >
            <text class="link-btn-text">{{ isAddingLink ? '添加中...' : '添加' }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="isUploading" class="upload-overlay">
      <view class="upload-content">
        <view class="upload-spinner"></view>
        <text class="upload-text">正在上传...</text>
      </view>
    </view>

    <view class="materials-content">
      <view v-if="!hasSpace" class="panel-empty">
        <text class="panel-empty-title">请先选择学习空间</text>
        <text class="panel-empty-sub">选择左侧学习空间后可管理文档和链接</text>
      </view>

      <view v-else-if="loading" class="panel-empty">
        <text class="panel-empty-title">正在加载学习资料...</text>
      </view>

      <view v-else-if="loadError" class="panel-empty">
        <text class="panel-empty-title">加载失败</text>
        <text class="panel-empty-sub">{{ loadError }}</text>
        <view class="retry-btn" @tap="loadDocuments">
          <text class="retry-btn-text">重试</text>
        </view>
      </view>

      <view v-else-if="documents.length === 0" class="panel-empty">
        <text class="panel-empty-title">暂无文档或链接</text>
        <text class="panel-empty-sub">点击右上角“添加”创建你的第一个学习资料</text>
      </view>

      <scroll-view v-else class="documents-scroll" scroll-y>
        <view class="document-list">
          <view
            v-for="doc in documents"
            :key="doc.id"
            class="document-item"
            @tap="handleDocClick(doc)"
          >
            <view class="document-icon">
              <text class="document-icon-text">{{ getDocIconLabel(doc) }}</text>
            </view>

            <view class="document-info">
              <text class="document-title">{{ truncateTitle(doc.title) }}</text>
              <view class="document-meta">
                <text class="document-type">{{ getDocTypeLabel(doc) }}</text>
                <text v-if="doc.doc_type === 'link'" class="document-url">{{ doc.url }}</text>
                <text v-else-if="doc.file_size" class="document-size">{{ formatFileSize(doc.file_size) }}</text>
              </view>

              <view v-if="doc.doc_type === 'document'" class="document-status-row">
                <view class="status-badge" :class="'status-' + getDocStatus(doc.id)">
                  <view class="status-dot" :style="{ backgroundColor: getStatusColor(getDocStatus(doc.id)) }"></view>
                  <text class="status-text" :style="{ color: getStatusColor(getDocStatus(doc.id)) }">
                    {{ getStatusLabel(getDocStatus(doc.id)) }}
                  </text>
                </view>
                <view
                  v-if="getDocStatus(doc.id) === 'completed' && getDocChunkCount(doc.id) > 0"
                  class="chunk-badge"
                >
                  <text class="chunk-text">{{ getDocChunkCount(doc.id) }} 块</text>
                </view>
                <view
                  v-if="getDocStatus(doc.id) === 'failed'"
                  class="error-badge"
                  @tap.stop="showErrorDetail(doc.id)"
                >
                  <text class="error-badge-text">查看错误</text>
                </view>
              </view>
            </view>

            <view class="document-actions">
              <view
                v-if="doc.doc_type === 'document'"
                class="document-preview"
                @tap.stop="openPreview(doc)"
              >
                <image
                  class="document-preview-icon"
                  mode="aspectFit"
                  src="/static/icons/phosphor/regular/eye.svg"
                />
              </view>
              <view class="document-delete" @tap.stop="showDeleteConfirm(doc)">
                <image
                  class="document-delete-icon"
                  mode="aspectFit"
                  src="/static/icons/phosphor/regular/trash.svg"
                />
              </view>
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <view v-if="showPreviewOverlay" class="preview-overlay" @tap.self="closePreview">
      <view class="preview-container" @tap.stop>
        <view class="preview-header">
          <view class="preview-title-wrap">
            <text class="preview-title">{{ previewTitle }}</text>
            <text class="preview-sub">{{ previewTypeLabel }}</text>
          </view>

          <view class="preview-header-actions">
            <view
              class="preview-header-btn"
              :class="{ 'preview-header-btn-disabled': !previewDownloadUrl }"
              @tap="downloadPreviewFile"
            >
              <image
                class="preview-header-btn-icon"
                mode="aspectFit"
                src="/static/icons/phosphor/regular/download.svg"
              />
            </view>
            <view class="preview-header-btn" @tap="closePreview">
              <image
                class="preview-header-btn-icon"
                mode="aspectFit"
                src="/static/icons/phosphor/regular/x.svg"
              />
            </view>
          </view>
        </view>

        <view class="preview-body">
          <view v-if="previewLoading" class="preview-state">
            <text class="preview-state-title">正在加载预览...</text>
          </view>

          <view v-else-if="previewError" class="preview-state">
            <text class="preview-state-title">预览失败</text>
            <text class="preview-state-sub">{{ previewError }}</text>
            <view class="preview-state-btn" @tap="downloadPreviewFile">
              <text class="preview-state-btn-text">下载文件</text>
            </view>
          </view>

          <scroll-view v-else-if="previewKind === 'txt'" class="preview-text-scroll" scroll-y>
            <text class="preview-text-content">{{ previewTextContent }}</text>
          </scroll-view>

          <view v-else-if="previewKind === 'pdf'" class="preview-frame-wrap">
            <!-- #ifdef H5 -->
            <iframe
              v-if="previewIframeUrl"
              class="preview-iframe"
              :src="previewIframeUrl"
              @load="handlePreviewFrameLoad"
            ></iframe>
            <!-- #endif -->

            <!-- #ifndef H5 -->
            <view class="preview-state">
              <text class="preview-state-title">当前平台不支持内嵌预览</text>
              <view class="preview-state-btn" @tap="downloadPreviewFile">
                <text class="preview-state-btn-text">下载文件</text>
              </view>
            </view>
            <!-- #endif -->
          </view>

          <!-- #ifdef H5 -->
          <scroll-view v-else-if="previewKind === 'docx'" class="preview-docx-scroll" scroll-y>
            <view ref="docxContainer" class="preview-docx-container"></view>
          </scroll-view>
          <!-- #endif -->

          <!-- #ifndef H5 -->
          <view v-else-if="previewKind === 'docx'" class="preview-state">
            <text class="preview-state-title">当前平台不支持内嵌预览</text>
            <view class="preview-state-btn" @tap="downloadPreviewFile">
              <text class="preview-state-btn-text">下载文件</text>
            </view>
          </view>
          <!-- #endif -->

          <view v-else-if="previewKind === 'doc'" class="preview-state">
            <text class="preview-state-title">.doc 格式暂不支持在线预览</text>
            <text class="preview-state-sub">请下载后使用 Word 打开查看</text>
            <view class="preview-state-btn" @tap="downloadPreviewFile">
              <text class="preview-state-btn-text">下载文件</text>
            </view>
          </view>

          <view v-else class="preview-state">
            <text class="preview-state-title">暂不支持该文件类型预览</text>
            <view class="preview-state-btn" @tap="downloadPreviewFile">
              <text class="preview-state-btn-text">下载文件</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view class="storage-container">
      <view class="storage-card">
        <view class="storage-header">
          <text class="storage-title">存储空间</text>
          <view :class="['tier-badge', `tier-${normalizedTier.toLowerCase()}`]">
            <text class="tier-text">{{ tierLabel }}</text>
          </view>
        </view>
        <view class="storage-progress-track">
          <view class="storage-progress-fill" :style="{ width: storagePercent + '%', backgroundColor: storageColor }"></view>
        </view>
        <view class="storage-info">
          <text class="storage-used">{{ formatStorageSize(storageUsed) }} / {{ formatStorageSize(storageLimit) }}</text>
          <text class="storage-percent" :style="{ color: storageColor }">{{ storagePercent }}%</text>
        </view>
      </view>
    </view>

    <u-modal
      :visible="showDeleteModal"
      title="删除确认"
      :content="deleteModalContent"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteDocument"
      @close="showDeleteModal = false"
    />

    <u-modal
      :visible="showUpgradeModal"
      :title="isExpiredSubscription ? '订阅已到期' : (fileSizeExceeded ? '文件大小超出限制' : (pendingFileSize > 0 ? '存储空间不足' : '存储空间已满'))"
      :content="upgradeModalContent"
      :confirm-text="isExpiredSubscription ? `续费 ${expiredTierLabel}` : (nextTierInfo ? `升级到 ${nextTierInfo.label}` : '查看订阅')"
      @confirm="handleUpgrade"
      @close="handleUpgradeModalClose"
    />

    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import {
  addSpaceLink,
  deleteSpaceDocument,
  getDocumentProcessingStatus,
  getSpaceDocuments,
  uploadSpaceDocumentH5
} from '@/api/space'
import config from '@/config'
import { useUserStore } from '@/store/user'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'

// #ifdef H5
let renderAsync = null
import('docx-preview').then(m => { renderAsync = m.renderAsync }).catch(() => {})
// #endif

const POLLING_INTERVAL_MS = 5000
const INITIAL_POLLING_WINDOW_MS = 5 * 60 * 1000
const PREVIEW_IFRAME_TIMEOUT_MS = 12000

export default {
  name: 'StudyMaterialsPanel',
  components: {
    UModal,
    UToast
  },
  props: {
    spaceId: {
      type: [String, Number],
      default: ''
    },
    userTier: {
      type: String,
      default: 'FREE'
    },
    visible: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      loading: false,
      loadError: null,
      documents: [],
      showAddMenu: false,
      showLinkDialog: false,
      linkDialogVisible: false,
      linkTitle: '',
      linkUrl: '',
      isAddingLink: false,
      isUploading: false,
      showDeleteModal: false,
      docToDelete: null,
      isDeleting: false,
      showUpgradeModal: false,
      pendingFileSize: 0,
      fileSizeExceeded: false,
      processingStatuses: {},
      loadingStatuses: false,
      statusPollTimer: null,
      showPreviewOverlay: false,
      previewDoc: null,
      previewKind: '',
      previewLoading: false,
      previewError: '',
      previewTextContent: '',
      previewIframeUrl: '',
      previewFrameLoaded: false,
      previewObjectUrl: '',
      previewLoadTimer: null,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },
  computed: {
    normalizedSpaceId() {
      const value = this.spaceId
      if (value === null || value === undefined) return ''
      return String(value).trim()
    },
    hasSpace() {
      return Boolean(this.normalizedSpaceId)
    },
    normalizedTier() {
      const tier = (this.userTier || 'FREE').toUpperCase()
      const tierMap = { BASIC: 'PLUS', PREMIUM: 'ULTRA' }
      const mapped = tierMap[tier] || tier
      if (['FREE', 'PLUS', 'ULTRA', 'ALPHA'].includes(mapped)) return mapped
      return 'FREE'
    },
    storageLimits() {
      return {
        FREE: 30 * 1024 * 1024,
        PLUS: 200 * 1024 * 1024,
        ULTRA: 500 * 1024 * 1024,
        ALPHA: 500 * 1024 * 1024
      }
    },
    storageLimit() {
      return this.storageLimits[this.normalizedTier] || this.storageLimits.FREE
    },
    uploadFileLimits() {
      return {
        FREE: 10 * 1024 * 1024,
        PLUS: 50 * 1024 * 1024,
        ULTRA: 100 * 1024 * 1024,
        ALPHA: 100 * 1024 * 1024
      }
    },
    uploadFileLimit() {
      return this.uploadFileLimits[this.normalizedTier] || this.uploadFileLimits.FREE
    },
    nextTierInfo() {
      const tierOrder = ['FREE', 'PLUS', 'ULTRA']
      const currentIdx = tierOrder.indexOf(this.normalizedTier)
      if (currentIdx < 0 || currentIdx >= tierOrder.length - 1) return null
      const nextTier = tierOrder[currentIdx + 1]
      const labels = { PLUS: 'Plus', ULTRA: 'Ultra' }
      const uploadLimits = { PLUS: 50, ULTRA: 100 }
      const storageLimits = { PLUS: 200, ULTRA: 500 }
      return { label: labels[nextTier], uploadLimitMB: uploadLimits[nextTier], storageLimitMB: storageLimits[nextTier] }
    },
    isExpiredSubscription() {
      const userStore = useUserStore()
      const user = userStore.user
      if (!user?.subscription_expires_at) return false
      const rawTier = (user.subscription_tier || 'FREE').toUpperCase()
      if (rawTier === 'FREE') return false
      return new Date(user.subscription_expires_at) < new Date()
    },
    expiredTierLabel() {
      const userStore = useUserStore()
      const rawTier = (userStore.user?.subscription_tier || '').toUpperCase()
      const labels = { BASIC: 'Plus', PREMIUM: 'Ultra', PLUS: 'Plus', ULTRA: 'Ultra', ALPHA: 'Alpha' }
      return labels[rawTier] || ''
    },
    storageUsed() {
      return this.documents.reduce((acc, doc) => {
        if (doc.doc_type === 'link') {
          return acc + new Blob([doc.url || '', doc.title || '']).size
        }
        return acc + (doc.file_size || 0)
      }, 0)
    },
    storagePercent() {
      if (!this.storageLimit) return 0
      const percent = (this.storageUsed / this.storageLimit) * 100
      return Math.min(100, Math.round(percent * 10) / 10)
    },
    storageColor() {
      if (this.storagePercent >= 90) return '#ef4444'
      if (this.storagePercent >= 70) return '#f59e0b'
      return '#7acc71'
    },
    tierLabel() {
      const labels = {
        FREE: 'Free 版',
        PLUS: 'Plus 版',
        ULTRA: 'Ultra 版',
        ALPHA: 'Alpha 版'
      }
      return labels[this.normalizedTier] || labels.FREE
    },
    deleteModalContent() {
      if (!this.docToDelete) return ''
      const typeLabel = this.docToDelete.doc_type === 'link' ? '链接' : '文档'
      return `确定要删除${typeLabel}「${this.docToDelete.title}」吗？此操作不可恢复。`
    },
    upgradeModalContent() {
      const limitMB = (this.storageLimit / (1024 * 1024)).toFixed(0)
      const remainingMB = ((this.storageLimit - this.storageUsed) / (1024 * 1024)).toFixed(1)

      // 已到期用户
      if (this.isExpiredSubscription) {
        const tierLabel = this.expiredTierLabel
        if (this.fileSizeExceeded && this.pendingFileSize > 0) {
          const fileSizeMB = (this.pendingFileSize / (1024 * 1024)).toFixed(1)
          return `你的 ${tierLabel} 订阅已到期，当前文件上传上限为 10MB，该文件 ${fileSizeMB}MB 无法上传。\n\n续费 ${tierLabel} 即可恢复更大上传额度。`
        }
        return `你的 ${tierLabel} 订阅已到期，存储空间已降至 ${limitMB}MB。\n\n续费即可恢复原有空间和功能。`
      }

      // 文件大小超限
      if (this.fileSizeExceeded && this.pendingFileSize > 0) {
        const fileSizeMB = (this.pendingFileSize / (1024 * 1024)).toFixed(1)
        const uploadLimitMB = (this.uploadFileLimit / (1024 * 1024)).toFixed(0)
        let msg = `文件大小 ${fileSizeMB}MB，超过当前 ${this.tierLabel} 的单文件上限 ${uploadLimitMB}MB。`
        if (this.nextTierInfo) {
          msg += `\n\n升级到 ${this.nextTierInfo.label} 可上传最大 ${this.nextTierInfo.uploadLimitMB}MB 的文件。`
        }
        return msg
      }

      // 存储空间不足
      if (this.pendingFileSize > 0) {
        const fileSizeMB = (this.pendingFileSize / (1024 * 1024)).toFixed(1)
        let msg = `文件大小 ${fileSizeMB}MB，剩余空间仅 ${remainingMB}MB。\n\n当前 ${this.tierLabel} 存储上限为 ${limitMB}MB。`
        if (this.nextTierInfo) {
          msg += `\n\n升级到 ${this.nextTierInfo.label} 可获得 ${this.nextTierInfo.storageLimitMB}MB 存储空间。`
        }
        return msg
      }

      return `当前 ${this.tierLabel} 存储空间为 ${limitMB}MB，已达到上限。`
    },
    previewTitle() {
      return this.previewDoc?.title || '文件预览'
    },
    previewTypeLabel() {
      const labels = {
        txt: 'TXT 文本预览',
        pdf: 'PDF 预览',
        doc: 'Word 预览',
        docx: 'Word 预览'
      }
      return labels[this.previewKind] || '文件预览'
    },
    previewDownloadUrl() {
      if (!this.previewDoc?.url) return ''
      return this.resolveDocumentUrl(this.previewDoc.url)
    }
  },
  watch: {
    spaceId: {
      immediate: true,
      handler() {
        this.handleSpaceChanged()
      }
    },
    visible(newVal) {
      if (newVal) {
        this.refreshPollingState()
      } else {
        this.stopStatusPolling()
        this.closePreview()
      }
    }
  },
  beforeUnmount() {
    this.stopStatusPolling()
    this.clearPreviewLoadTimer()
  },
  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },
    extractErrorMessage(error, fallback = '请求失败') {
      const detail = error?.data?.detail
      if (typeof detail === 'string') return detail
      if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message
      if (typeof error?.message === 'string' && error.message) return error.message
      return fallback
    },
    handleSpaceChanged() {
      this.stopStatusPolling()
      this.documents = []
      this.processingStatuses = {}
      this.loadError = null
      this.showAddMenu = false
      this.closeLinkDialog()
      this.closePreview()

      if (!this.hasSpace) {
        this.loading = false
        return
      }
      this.loadDocuments()
    },
    async loadDocuments() {
      if (!this.hasSpace) return

      try {
        this.loading = true
        this.loadError = null
        const response = await getSpaceDocuments(this.normalizedSpaceId)
        this.documents = response?.documents || []
        await this.loadProcessingStatuses()
      } catch (error) {
        this.loadError = this.extractErrorMessage(error, '加载失败，请检查网络后重试')
        this.documents = []
      } finally {
        this.loading = false
      }
    },
    async loadProcessingStatuses() {
      const fileDocuments = this.documents.filter((d) => d.doc_type === 'document')
      if (fileDocuments.length === 0) {
        this.processingStatuses = {}
        this.stopStatusPolling()
        return
      }

      this.loadingStatuses = true
      const nextStatuses = { ...this.processingStatuses }

      try {
        const promises = fileDocuments.map((doc) =>
          getDocumentProcessingStatus(this.normalizedSpaceId, doc.id)
            .then((res) => ({ docId: doc.id, status: res }))
            .catch(() => ({ docId: doc.id, status: null }))
        )

        const results = await Promise.all(promises)
        results.forEach(({ docId, status }) => {
          if (status) {
            nextStatuses[docId] = status
          }
        })
        this.processingStatuses = nextStatuses
      } finally {
        this.loadingStatuses = false
        this.refreshPollingState()
      }
    },
    refreshPollingState() {
      if (!this.visible || !this.hasSpace) {
        this.stopStatusPolling()
        return
      }

      const shouldPoll = this.documents.some((doc) => this.shouldContinuePolling(doc))
      if (!shouldPoll) {
        this.stopStatusPolling()
        return
      }

      if (!this.statusPollTimer) {
        this.statusPollTimer = setInterval(() => {
          if (!this.visible || !this.hasSpace) {
            this.stopStatusPolling()
            return
          }
          this.loadProcessingStatuses()
        }, POLLING_INTERVAL_MS)
      }
    },
    stopStatusPolling() {
      if (this.statusPollTimer) {
        clearInterval(this.statusPollTimer)
        this.statusPollTimer = null
      }
    },
    shouldContinuePolling(doc) {
      if (doc.doc_type !== 'document') return false
      const status = this.getDocStatus(doc.id)
      if (status === 'pending' || status === 'processing') return true
      if (status !== 'not_started') return false

      const createdAtMs = new Date(doc.created_at).getTime()
      if (!Number.isFinite(createdAtMs)) return false
      return Date.now() - createdAtMs <= INITIAL_POLLING_WINDOW_MS
    },
    toggleAddMenu() {
      if (!this.hasSpace) return
      this.showAddMenu = !this.showAddMenu
    },
    handleAddDocument() {
      if (this.isUploading) {
        this.showCustomToast('请等待上传完成', 'error')
        return
      }

      this.showAddMenu = false

      // #ifdef H5
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.pdf,.doc,.docx,.txt,.xlsx,.xls,.pptx,.ppt,.md,.html,.htm,.csv,.epub'
      input.onchange = async (event) => {
        const file = event?.target?.files?.[0]
        if (!file) return

        if (file.size > this.uploadFileLimit) {
          this.pendingFileSize = file.size
          this.fileSizeExceeded = true
          this.showUpgradeModal = true
          return
        }

        const ext = (file.name.split('.').pop() || '').toLowerCase()
        const validExtensions = ['pdf', 'doc', 'docx', 'txt', 'xlsx', 'xls', 'pptx', 'ppt', 'md', 'html', 'htm', 'csv', 'epub']
        if (!validExtensions.includes(ext)) {
          this.showCustomToast('不支持该文件格式', 'error')
          return
        }

        if (!this.checkStorageSpace(file.size)) {
          return
        }

        await this.uploadFileH5(file)
      }
      input.click()
      // #endif

      // #ifndef H5
      this.showCustomToast('当前平台暂不支持网页端上传', 'error')
      // #endif
    },
    async uploadFileH5(file) {
      this.isUploading = true
      try {
        await uploadSpaceDocumentH5(this.normalizedSpaceId, file)
        this.showCustomToast('上传成功', 'success')
        await this.loadDocuments()
      } catch (error) {
        this.showCustomToast(this.extractErrorMessage(error, '上传失败'), 'error')
      } finally {
        this.isUploading = false
      }
    },
    handleAddLink() {
      this.showAddMenu = false
      this.showLinkDialog = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.linkDialogVisible = true
        }, 10)
      })
    },
    closeLinkDialog() {
      this.linkDialogVisible = false
      setTimeout(() => {
        this.showLinkDialog = false
        this.linkTitle = ''
        this.linkUrl = ''
      }, 200)
    },
    async submitLink() {
      if (this.isAddingLink) return

      const title = this.linkTitle.trim()
      const url = this.linkUrl.trim()

      if (!title) {
        this.showCustomToast('请输入链接标题', 'error')
        return
      }
      if (!url) {
        this.showCustomToast('请输入链接地址', 'error')
        return
      }

      try {
        new URL(url)
      } catch (error) {
        this.showCustomToast('请输入有效的网址', 'error')
        return
      }

      const estimatedSize = new Blob([url, title]).size
      if (!this.checkStorageSpace(estimatedSize)) {
        this.closeLinkDialog()
        return
      }

      this.isAddingLink = true
      try {
        await addSpaceLink(this.normalizedSpaceId, { title, url })
        this.showCustomToast('链接添加成功', 'success')
        this.closeLinkDialog()
        await this.loadDocuments()
      } catch (error) {
        this.showCustomToast(this.extractErrorMessage(error, '添加链接失败'), 'error')
      } finally {
        this.isAddingLink = false
      }
    },
    showDeleteConfirm(doc) {
      this.docToDelete = doc
      this.showDeleteModal = true
    },
    async doDeleteDocument() {
      if (this.isDeleting || !this.docToDelete) return
      this.isDeleting = true
      const deletingDocId = this.docToDelete.id

      try {
        await deleteSpaceDocument(this.normalizedSpaceId, this.docToDelete.id)
        this.documents = this.documents.filter((d) => d.id !== this.docToDelete.id)
        const { [this.docToDelete.id]: _deleted, ...rest } = this.processingStatuses
        this.processingStatuses = rest
        this.refreshPollingState()
        if (this.previewDoc?.id === deletingDocId) {
          this.closePreview()
        }
        this.showDeleteModal = false
        this.docToDelete = null
        this.showCustomToast('删除成功', 'success')
      } catch (error) {
        this.showCustomToast(this.extractErrorMessage(error, '删除失败，请重试'), 'error')
      } finally {
        this.isDeleting = false
      }
    },
    checkStorageSpace(fileSize) {
      const remaining = this.storageLimit - this.storageUsed
      if (fileSize > remaining) {
        this.pendingFileSize = fileSize
        this.fileSizeExceeded = false
        this.showUpgradeModal = true
        return false
      }
      return true
    },
    handleUpgrade() {
      this.showUpgradeModal = false
      this.pendingFileSize = 0
      this.fileSizeExceeded = false
      uni.navigateTo({ url: '/pages/activation/activation' })
    },
    handleUpgradeModalClose() {
      this.showUpgradeModal = false
      this.pendingFileSize = 0
      this.fileSizeExceeded = false
    },
    clearPreviewLoadTimer() {
      if (this.previewLoadTimer) {
        clearTimeout(this.previewLoadTimer)
        this.previewLoadTimer = null
      }
    },
    clearPreviewObjectUrl() {
      if (this.previewObjectUrl) {
        if (typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(this.previewObjectUrl)
        }
        this.previewObjectUrl = ''
      }
    },
    closePreview() {
      this.clearPreviewLoadTimer()
      this.clearPreviewObjectUrl()
      this.showPreviewOverlay = false
      this.previewDoc = null
      this.previewKind = ''
      this.previewLoading = false
      this.previewError = ''
      this.previewTextContent = ''
      this.previewIframeUrl = ''
      this.previewFrameLoaded = false
    },
    resolveDocumentUrl(url) {
      const normalizedUrl = String(url || '').trim()
      if (!normalizedUrl) return ''
      if (/^https?:\/\//i.test(normalizedUrl)) return normalizedUrl

      const base = String(config.API_BASE_URL || '').replace(/\/+$/, '')
      if (!base) return normalizedUrl
      const path = normalizedUrl.startsWith('/') ? normalizedUrl : `/${normalizedUrl}`
      return `${base}${path}`
    },
    getPreviewKind(doc) {
      if (doc?.doc_type !== 'document') return ''

      const ext = this.getDocExt(doc).toLowerCase()
      if (ext === 'txt') return 'txt'
      if (ext === 'pdf') return 'pdf'
      if (ext === 'doc') return 'doc'
      if (ext === 'docx') return 'docx'
      return 'unsupported'
    },
    startIframePreview(url, withTimeout = true) {
      this.previewFrameLoaded = false
      this.previewIframeUrl = url
      this.previewLoading = withTimeout
      this.previewError = ''
      this.clearPreviewLoadTimer()

      if (!withTimeout) return
      this.previewLoadTimer = setTimeout(() => {
        if (this.previewFrameLoaded) return
        this.previewLoading = false
        if (!this.previewError) {
          this.previewError = '预览加载超时，请尝试下载文件查看。'
        }
      }, PREVIEW_IFRAME_TIMEOUT_MS)
    },
    handlePreviewFrameLoad() {
      this.previewFrameLoaded = true
      this.previewLoading = false
      this.previewError = ''
      this.clearPreviewLoadTimer()
    },
    async loadTxtPreview(fileUrl) {
      const response = await fetch(fileUrl, { method: 'GET' })
      if (!response.ok) {
        throw new Error(`文本加载失败 (${response.status})`)
      }

      const text = await response.text()
      this.previewTextContent = text || '文档内容为空'
    },
    async loadPdfPreview(fileUrl) {
      this.clearPreviewObjectUrl()

      // #ifdef H5
      try {
        const response = await fetch(fileUrl, { method: 'GET' })
        if (!response.ok) {
          throw new Error(`PDF 加载失败 (${response.status})`)
        }

        const blob = await response.blob()
        const objectUrl = URL.createObjectURL(blob)
        this.previewObjectUrl = objectUrl
        this.startIframePreview(objectUrl, false)
        return
      } catch (error) {
        // 降级到直接 URL，避免因 fetch 失败直接不可预览
      }
      // #endif

      this.startIframePreview(fileUrl, false)
    },
    async loadDocxPreview(fileUrl) {
      if (!renderAsync) {
        throw new Error('docx-preview 库加载失败，请刷新页面后重试')
      }

      const response = await fetch(fileUrl, { method: 'GET' })
      if (!response.ok) {
        throw new Error(`文档加载失败 (${response.status})`)
      }
      const arrayBuffer = await response.arrayBuffer()

      await this.$nextTick()
      const container = this.$refs.docxContainer
      if (!container) throw new Error('预览容器未就绪')

      await renderAsync(arrayBuffer, container, null, {
        className: 'docx-preview-wrapper',
        inWrapper: true,
        ignoreWidth: false,
        ignoreHeight: true,
        ignoreFonts: false,
        breakPages: true,
        ignoreLastRenderedPageBreak: true,
        experimental: false,
        trimXmlDeclaration: true,
        useBase64URL: true,
      })
    },
    async openPreview(doc) {
      if (doc?.doc_type !== 'document') return

      const previewKind = this.getPreviewKind(doc)
      const fileUrl = this.resolveDocumentUrl(doc.url)
      if (!fileUrl) {
        this.showCustomToast('未找到可预览的文件地址', 'error')
        return
      }

      this.showAddMenu = false
      this.showPreviewOverlay = true
      this.previewDoc = doc
      this.previewKind = previewKind
      this.previewLoading = true
      this.previewError = ''
      this.previewTextContent = ''
      this.previewIframeUrl = ''
      this.previewFrameLoaded = false
      this.clearPreviewObjectUrl()

      try {
        if (previewKind === 'txt') {
          await this.loadTxtPreview(fileUrl)
          this.previewLoading = false
          return
        }

        if (previewKind === 'pdf') {
          await this.loadPdfPreview(fileUrl)
          return
        }

        if (previewKind === 'docx') {
          await this.loadDocxPreview(fileUrl)
          this.previewLoading = false
          return
        }

        if (previewKind === 'doc') {
          this.previewLoading = false
          this.previewError = '.doc 格式暂不支持在线预览，请下载后查看。'
          return
        }

        this.previewLoading = false
        this.previewError = '暂不支持该文件格式预览。'
      } catch (error) {
        this.previewLoading = false
        this.previewError = this.extractErrorMessage(error, '预览失败，请稍后重试。')
      }
    },
    downloadPreviewFile() {
      const downloadUrl = this.previewDownloadUrl
      if (!downloadUrl) {
        this.showCustomToast('文件地址无效，无法下载', 'error')
        return
      }

      // #ifdef H5
      window.open(downloadUrl, '_blank', 'noopener,noreferrer')
      // #endif

      // #ifndef H5
      uni.setClipboardData({
        data: downloadUrl,
        success: () => this.showCustomToast('下载链接已复制到剪贴板', 'success')
      })
      // #endif
    },
    handleDocClick(doc) {
      if (doc.doc_type !== 'link') return

      // #ifdef H5
      window.open(doc.url, '_blank', 'noopener,noreferrer')
      // #endif

      // #ifndef H5
      uni.setClipboardData({
        data: doc.url,
        success: () => this.showCustomToast('链接已复制到剪贴板', 'success')
      })
      // #endif
    },
    showErrorDetail(docId) {
      const message = this.processingStatuses[docId]?.error_message || '处理失败，请重试'
      this.showCustomToast(message, 'error')
    },
    getDocStatus(docId) {
      const statusData = this.processingStatuses[docId]
      if (!statusData) return this.loadingStatuses ? 'loading' : 'not_started'
      return statusData.status || 'not_started'
    },
    getDocChunkCount(docId) {
      return this.processingStatuses[docId]?.chunk_count || 0
    },
    getStatusLabel(status) {
      const labels = {
        not_started: '未开始',
        pending: '等待处理',
        processing: '处理中',
        completed: '处理完成',
        failed: '处理失败',
        loading: '加载中'
      }
      return labels[status] || status
    },
    getStatusColor(status) {
      const colors = {
        not_started: '#6b7280',
        pending: '#f59e0b',
        processing: '#3b82f6',
        completed: '#10b981',
        failed: '#ef4444',
        loading: '#6b7280'
      }
      return colors[status] || '#6b7280'
    },
    getDocIconLabel(doc) {
      if (doc.doc_type === 'link') return 'LINK'
      const ext = this.getDocExt(doc)
      return ext || 'DOC'
    },
    getDocExt(doc) {
      const filename = doc.original_filename || ''
      const ext = filename.split('.').pop() || ''
      return ext.toUpperCase()
    },
    getDocTypeLabel(doc) {
      if (doc.doc_type === 'link') return '链接'
      const ext = this.getDocExt(doc).toLowerCase()
      if (ext === 'pdf') return 'PDF 文档'
      if (ext === 'doc' || ext === 'docx') return 'Word 文档'
      if (ext === 'txt') return '文本文件'
      return '文档'
    },
    truncateTitle(title, maxLength = 30) {
      if (!title) return ''
      if (title.length <= maxLength) return title
      return `${title.slice(0, maxLength)}...`
    },
    formatFileSize(bytes) {
      if (!bytes) return ''
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    },
    formatStorageSize(bytes) {
      if (!bytes || bytes === 0) return '0 MB'
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }
  }
}
</script>

<style scoped>
.materials-panel {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.materials-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  flex-shrink: 0;
}

.materials-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.materials-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}

.materials-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.materials-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
}

.toolbar-btn-refresh {
  width: 44px;
  height: 31px;
  border-radius: 7px;
  border-color: rgba(96, 165, 250, 0.4);
  background: rgba(96, 165, 250, 0.18);
}

.toolbar-btn-primary {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(59, 130, 246, 0.18);
}

.toolbar-btn-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.toolbar-btn-icon {
  width: 15px;
  height: 15px;
  filter: brightness(0) saturate(100%) invert(95%) sepia(2%) saturate(115%) hue-rotate(183deg) brightness(104%) contrast(100%);
}

.toolbar-btn-refresh-icon {
  filter: none;
}

.materials-content {
  flex: 1;
  min-height: 0;
  position: relative;
}

.panel-empty {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  text-align: center;
}

.panel-empty-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.panel-empty-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

.retry-btn {
  margin-top: 4px;
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid rgba(96, 165, 250, 0.5);
  background: rgba(59, 130, 246, 0.15);
}

.retry-btn-text {
  font-size: 12px;
  color: #93c5fd;
}

.documents-scroll {
  width: 100%;
  height: 100%;
}

.document-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.document-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.document-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.24);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.document-icon-text {
  font-size: 10px;
  font-weight: 700;
  color: #93c5fd;
}

.document-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.document-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.4;
}

.document-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.document-type,
.document-size {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.document-url {
  font-size: 12px;
  color: #93c5fd;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-text {
  font-size: 11px;
}

.chunk-badge {
  height: 20px;
  padding: 0 8px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.16);
}

.chunk-text {
  font-size: 11px;
  color: #6ee7b7;
  line-height: 1;
}

.error-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.16);
}

.error-badge-text {
  font-size: 11px;
  color: #fca5a5;
}

.document-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.document-preview {
  height: 28px;
  padding: 0 8px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(59, 130, 246, 0.25);
}

.document-preview-icon {
  width: 13px;
  height: 13px;
  filter: brightness(0) saturate(100%) invert(81%) sepia(19%) saturate(727%) hue-rotate(185deg) brightness(101%) contrast(101%);
}

.document-delete {
  height: 28px;
  padding: 0 8px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.22);
  flex-shrink: 0;
}

.document-delete-icon {
  width: 13px;
  height: 13px;
  filter: brightness(0) saturate(100%) invert(77%) sepia(15%) saturate(1247%) hue-rotate(305deg) brightness(102%) contrast(97%);
}

.preview-overlay {
  position: absolute;
  inset: 0;
  z-index: 95;
  background: rgba(7, 8, 22, 0.92);
  touch-action: auto;
}

.preview-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preview-header {
  height: 52px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-title-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

.preview-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.preview-header-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.preview-header-btn-disabled {
  opacity: 0.45;
  pointer-events: none;
}

.preview-header-btn-icon {
  width: 14px;
  height: 14px;
  filter: brightness(0) saturate(100%) invert(95%) sepia(2%) saturate(115%) hue-rotate(183deg) brightness(104%) contrast(100%);
}

.preview-body {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  touch-action: auto;
}

.preview-state {
  width: 100%;
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
}

.preview-state-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.preview-state-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.52);
  max-width: 460px;
}

.preview-state-btn {
  margin-top: 6px;
  height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(96, 165, 250, 0.46);
  background: rgba(59, 130, 246, 0.16);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.preview-state-btn-text {
  font-size: 12px;
  color: #93c5fd;
}

.preview-text-scroll {
  width: 100%;
  height: 100%;
  padding: 14px 16px;
  box-sizing: border-box;
}

/* Match chat panel scrollbar style */
.preview-text-scroll::-webkit-scrollbar,
.preview-text-scroll :deep(.uni-scroll-view)::-webkit-scrollbar {
  width: 6px;
}

.preview-text-scroll::-webkit-scrollbar-track,
.preview-text-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-track {
  background: transparent;
}

.preview-text-scroll::-webkit-scrollbar-thumb,
.preview-text-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.preview-text-scroll::-webkit-scrollbar-thumb:hover,
.preview-text-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.preview-text-scroll,
.preview-text-scroll :deep(.uni-scroll-view) {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.preview-text-content {
  display: block;
  font-size: 13px;
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.86);
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-frame-wrap {
  width: 100%;
  height: 100%;
  overflow: hidden;
  touch-action: pan-x pan-y;
  -webkit-overflow-scrolling: touch;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
  touch-action: auto;
}

.preview-docx-scroll {
  width: 100%;
  height: 100%;
  background: #f5f5f5;
  -webkit-overflow-scrolling: touch;
}

.preview-docx-container {
  min-height: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.storage-container {
  padding: 10px 12px 12px;
  flex-shrink: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.storage-card {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 10px 12px;
}

.storage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.storage-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.78);
}

.tier-badge {
  height: 20px;
  padding: 0 8px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
}

.tier-free {
  background: rgba(156, 163, 175, 0.2);
}

.tier-plus {
  background: rgba(59, 130, 246, 0.2);
}

.tier-ultra {
  background: rgba(139, 92, 246, 0.22);
}

.tier-alpha {
  background: rgba(16, 185, 129, 0.2);
}

.tier-text {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1;
}

.storage-progress-track {
  height: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.09);
  overflow: hidden;
}

.storage-progress-fill {
  height: 100%;
  transition: width 220ms ease;
}

.storage-info {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.storage-used,
.storage-percent {
  font-size: 11px;
}

.storage-used {
  color: rgba(255, 255, 255, 0.55);
}

.add-menu-overlay {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 40;
}

.add-menu {
  position: absolute;
  top: 52px;
  right: 14px;
  min-width: 130px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(17, 17, 30, 0.95);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  overflow: hidden;
}

.add-menu-item {
  padding: 10px 12px;
}

.add-menu-item-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.86);
}

.add-menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
}

.link-dialog-overlay {
  position: absolute;
  inset: 0;
  z-index: 80;
  background: rgba(0, 0, 0, 0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 200ms ease;
}

.link-dialog-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.55);
}

.link-dialog {
  width: 640rpx;
  max-width: calc(100vw - 44px);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(16, 16, 26, 0.95);
  transform: translateY(12px) scale(0.96);
  opacity: 0;
  transition: all 220ms ease;
}

.link-dialog.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.link-dialog-title {
  display: block;
  padding: 14px 14px 8px;
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
}

.link-dialog-content {
  padding: 0 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.link-input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.link-input-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.link-input {
  width: 100%;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: #ffffff;
  font-size: 13px;
  padding: 0 10px;
  box-sizing: border-box;
}

.link-dialog-actions {
  display: flex;
  align-items: center;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.link-btn {
  flex: 1;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.link-btn-cancel {
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.link-btn-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
}

.link-btn-disabled {
  opacity: 0.5;
}

.upload-overlay {
  position: absolute;
  inset: 0;
  z-index: 90;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-content {
  padding: 14px 18px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(16, 16, 26, 0.95);
  display: flex;
  align-items: center;
  gap: 10px;
}

.upload-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.upload-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
