<template>
  <view class="knowledge-base-page">
    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <view class="nav-center">
        <text class="nav-title">知识库管理</text>
        <view class="debug-btn" @click="toggleDebugPanel">
          <image class="debug-icon" src="/static/icons/phosphor-icons/SVGs/regular/bug.svg" mode="aspectFit"></image>
        </view>
      </view>
      <view class="nav-right add-btn" @click="handleAddFile">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/plus.svg" mode="aspectFit"></image>
      </view>
    </view>

    <!-- Add File Popup -->
    <view v-if="showAddFilePopup" class="add-file-popup-wrapper" @click="closeAddFilePopup">
      <view
        class="add-file-popup"
        :class="{ 'popup-show': addFilePopupVisible }"
        @click.stop
      >
        <!-- 小箭头指向按钮 (向上) -->
        <view class="popup-arrow-up"></view>
        <view class="popup-option" @click="handleAddDocument">
          <image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
          <text class="popup-option-text">添加文档</text>
        </view>
        <view class="popup-divider"></view>
        <view class="popup-option" @click="handleAddLink">
          <image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit" />
          <text class="popup-option-text">添加链接</text>
        </view>
      </view>
    </view>

    <!-- Add Link Dialog -->
    <view
      v-if="showLinkDialog"
      class="link-dialog-overlay"
      :class="{ 'overlay-show': linkDialogVisible }"
      @click="closeLinkDialog"
    >
      <view
        class="link-dialog"
        :class="{ 'dialog-show': linkDialogVisible }"
        @click.stop
      >
        <text class="link-dialog-title">添加链接</text>
        <view class="link-dialog-content">
          <view class="link-input-group">
            <text class="link-input-label">标题</text>
            <input
              class="link-input"
              v-model="linkTitle"
              placeholder="输入链接标题"
              placeholder-class="link-input-placeholder"
              maxlength="255"
            />
          </view>
          <view class="link-input-group">
            <text class="link-input-label">网址</text>
            <input
              class="link-input"
              v-model="linkUrl"
              placeholder="https://example.com"
              placeholder-class="link-input-placeholder"
              type="url"
              maxlength="2048"
            />
          </view>
        </view>
        <view class="link-dialog-actions">
          <view class="link-btn link-btn-cancel" @click="closeLinkDialog">
            <text class="link-btn-text">取消</text>
          </view>
          <view
            class="link-btn link-btn-confirm"
            :class="{ 'link-btn-disabled': isAddingLink }"
            @click="submitLink"
          >
            <text class="link-btn-text">{{ isAddingLink ? '添加中...' : '添加' }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Upload Progress Overlay -->
    <view v-if="isUploading" class="upload-overlay">
      <view class="upload-content">
        <view class="upload-spinner"></view>
        <text class="upload-filename">{{ uploadFileName }}</text>
        <view class="upload-progress-track">
          <view class="upload-progress-bar" :style="{ width: uploadProgress + '%' }"></view>
        </view>
        <text class="upload-text">正在上传... {{ uploadProgress }}%</text>
      </view>
    </view>

    <!-- Loading State -->
    <view v-if="loading" class="loading-container">
      <text class="loading-text">正在加载知识库...</text>
    </view>

    <!-- Error State -->
    <view v-else-if="loadError" class="error-container">
      <image class="error-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="error-text">{{ loadError }}</text>
      <view class="retry-btn" @click="loadDocuments">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- Empty State -->
    <view v-else-if="documents.length === 0" class="empty-container">
      <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/books.svg" mode="aspectFit"></image>
      <text class="empty-text">暂无文档或链接</text>
      <text class="empty-hint">在学习空间中点击添加按钮来添加文档或链接</text>
    </view>

    <!-- Document List -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="document-list">
        <view
          v-for="doc in documents"
          :key="doc.id"
          class="document-item"
          @click="handleDocClick(doc)"
        >
          <view class="document-icon-wrapper">
            <image
              class="document-icon"
              :src="getDocIcon(doc)"
              mode="aspectFit"
            ></image>
          </view>
          <view class="document-info">
            <text class="document-title">{{ truncateTitle(doc.title) }}</text>
            <view class="document-meta">
              <text class="document-type">{{ getDocTypeLabel(doc) }}{{ doc.doc_type === 'link' ? '：' : '' }}</text>
              <text v-if="doc.doc_type === 'link'" class="document-url">{{ doc.url }}</text>
              <text v-else-if="doc.file_size" class="document-size">{{ formatFileSize(doc.file_size) }}</text>
            </view>
            <!-- 处理状态行 (仅文档类型显示) -->
            <view v-if="doc.doc_type === 'document'" class="document-status-row">
              <!-- 状态 Badge -->
              <view class="status-badge" :class="'status-' + getDocStatus(doc.id)">
                <view class="status-dot" :style="{ backgroundColor: getStatusColor(getDocStatus(doc.id)) }"></view>
                <text class="status-text" :style="{ color: getStatusColor(getDocStatus(doc.id)) }">
                  {{ getStatusLabel(getDocStatus(doc.id)) }}
                </text>
              </view>

              <!-- 切片数量 Badge (仅完成时) -->
              <view v-if="getDocStatus(doc.id) === 'completed' && getDocChunkCount(doc.id) > 0" class="chunk-badge">
                <text class="chunk-text">{{ getDocChunkCount(doc.id) }} 块</text>
              </view>

              <!-- 错误 Badge (仅失败时) -->
              <view v-if="getDocStatus(doc.id) === 'failed'" class="error-badge" @click.stop="showErrorDetail(doc.id)">
                <image class="error-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning.svg" mode="aspectFit"></image>
                <text class="error-text">查看错误</text>
              </view>
            </view>
          </view>
          <view class="document-action delete-btn" @click.stop="showDeleteConfirm(doc)">
            <image class="delete-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- Storage Indicator -->
    <view class="storage-container">
      <view class="storage-card">
        <view class="storage-header">
          <view class="storage-title-row">
            <image class="storage-icon" src="/static/icons/phosphor-icons/SVGs/regular/hard-drive.svg" mode="aspectFit"></image>
            <text class="storage-title">存储空间</text>
          </view>
          <view :class="['tier-badge', `tier-${userTier.toLowerCase()}`]">
            <text class="tier-text">{{ tierLabel }}</text>
          </view>
        </view>
        <view class="storage-progress-track">
          <view
            class="storage-progress-fill"
            :style="{ width: storagePercent + '%', backgroundColor: storageColor }"
          ></view>
        </view>
        <view class="storage-info">
          <text class="storage-used">{{ formatStorageSize(storageUsed) }} / {{ formatStorageSize(storageLimit) }}</text>
          <text class="storage-percent" :style="{ color: storageColor }">{{ storagePercent }}%</text>
        </view>
      </view>
    </view>

    <!-- Delete Confirmation Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除确认"
      :content="deleteModalContent"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteDocument"
      @close="showDeleteModal = false"
    />

    <!-- Storage Full Upgrade Modal -->
    <u-modal
      :visible="showUpgradeModal"
      :title="isExpiredSubscription ? '订阅已到期' : (fileSizeExceeded ? '文件大小超出限制' : (pendingFileSize > 0 ? '存储空间不足' : '存储空间已满'))"
      :content="upgradeModalContent"
      cancel-text="取消"
      :confirm-text="isExpiredSubscription ? `续费 ${expiredTierLabel}` : (nextTierInfo ? `升级到 ${nextTierInfo.label}` : '查看订阅')"
      @confirm="handleUpgrade"
      @close="handleUpgradeModalClose"
    />

    <!-- Toast -->
    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />

    <!-- Debug Panel -->
    <view
      v-if="showDebugPanel"
      class="debug-overlay"
      :class="{ 'overlay-show': debugPanelVisible }"
      @click="closeDebugPanel"
    >
      <view
        class="debug-panel"
        :class="{ 'panel-show': debugPanelVisible }"
        @click.stop
      >
        <!-- Header -->
        <view class="debug-header">
          <text class="debug-header-title">调试信息</text>
          <view class="debug-close-btn" @click="closeDebugPanel">
            <image class="debug-close-icon" src="/static/icons/phosphor-icons/SVGs/regular/x.svg" mode="aspectFit"></image>
          </view>
        </view>

        <!-- Content -->
        <scroll-view class="debug-content" scroll-y>
          <!-- Raw JSON View -->
          <view v-if="showRawJson" class="debug-raw-json">
            <text class="debug-json-text">{{ debugInfoJson }}</text>
          </view>

          <!-- Structured View -->
          <template v-else>
            <!-- Space Info Section -->
            <view class="debug-section">
              <text class="debug-section-title">空间信息</text>
              <view class="debug-info-card">
                <view class="debug-info-row">
                  <text class="debug-info-label">Space ID</text>
                  <text class="debug-info-value debug-mono">{{ spaceId || '-' }}</text>
                </view>
                <view class="debug-info-row">
                  <text class="debug-info-label">Space Name</text>
                  <text class="debug-info-value">{{ spaceName || '-' }}</text>
                </view>
                <view class="debug-info-row">
                  <text class="debug-info-label">订阅层级</text>
                  <text class="debug-info-value">{{ userTier }}</text>
                </view>
                <view class="debug-info-row">
                  <text class="debug-info-label">存储空间</text>
                  <text class="debug-info-value">{{ formatStorageSize(storageUsed) }} / {{ formatStorageSize(storageLimit) }} ({{ storagePercent }}%)</text>
                </view>
                <view class="debug-info-row">
                  <text class="debug-info-label">文档数量</text>
                  <text class="debug-info-value">{{ documents.length }} (文件: {{ fileCount }}, 链接: {{ linkCount }})</text>
                </view>
              </view>
            </view>

            <!-- Documents Section -->
            <view class="debug-section">
              <view class="debug-section-header">
                <text class="debug-section-title">文档列表</text>
                <view v-if="loadingStatuses" class="debug-loading-badge">
                  <text class="debug-loading-text">加载中...</text>
                </view>
              </view>

              <view v-if="documents.length === 0" class="debug-empty">
                <text class="debug-empty-text">暂无文档</text>
              </view>

              <view v-else class="debug-doc-list">
                <view v-for="doc in documents" :key="doc.id" class="debug-doc-card">
                  <!-- Doc Basic Info -->
                  <view class="debug-doc-header">
                    <image
                      class="debug-doc-icon"
                      :src="getDocIcon(doc)"
                      mode="aspectFit"
                    ></image>
                    <text class="debug-doc-title">{{ doc.title }}</text>
                  </view>

                  <view class="debug-doc-info">
                    <view class="debug-info-row">
                      <text class="debug-info-label">ID</text>
                      <text class="debug-info-value debug-mono debug-id">{{ doc.id }}</text>
                    </view>
                    <view class="debug-info-row">
                      <text class="debug-info-label">类型</text>
                      <text class="debug-info-value">{{ doc.doc_type }}</text>
                    </view>
                    <view v-if="doc.doc_type === 'document'" class="debug-info-row">
                      <text class="debug-info-label">大小</text>
                      <text class="debug-info-value">{{ formatFileSize(doc.file_size) }}</text>
                    </view>
                    <view v-if="doc.original_filename" class="debug-info-row">
                      <text class="debug-info-label">原始文件名</text>
                      <text class="debug-info-value">{{ doc.original_filename }}</text>
                    </view>
                    <view v-if="doc.url" class="debug-info-row">
                      <text class="debug-info-label">URL</text>
                      <text class="debug-info-value debug-url">{{ doc.url }}</text>
                    </view>
                    <view class="debug-info-row">
                      <text class="debug-info-label">创建时间</text>
                      <text class="debug-info-value">{{ formatFullDate(doc.created_at) }}</text>
                    </view>
                  </view>

                  <!-- Processing Status (only for document type) -->
                  <view v-if="doc.doc_type === 'document'" class="debug-processing-section">
                    <view class="debug-processing-divider"></view>
                    <view v-if="processingStatuses[doc.id]" class="debug-processing-info">
                      <view class="debug-info-row">
                        <text class="debug-info-label">处理状态</text>
                        <view class="debug-status-wrapper">
                          <view class="debug-status-dot" :style="{ backgroundColor: getStatusColor(processingStatuses[doc.id].status) }"></view>
                          <text class="debug-info-value" :style="{ color: getStatusColor(processingStatuses[doc.id].status) }">{{ getStatusLabel(processingStatuses[doc.id].status) }}</text>
                        </view>
                      </view>
                      <view v-if="processingStatuses[doc.id].chunk_count != null" class="debug-info-row">
                        <text class="debug-info-label">切片数量</text>
                        <text class="debug-info-value">{{ processingStatuses[doc.id].chunk_count }}</text>
                      </view>
                      <view v-if="processingStatuses[doc.id].error_message" class="debug-info-row">
                        <text class="debug-info-label">错误信息</text>
                        <text class="debug-info-value debug-error">{{ processingStatuses[doc.id].error_message }}</text>
                      </view>
                      <view v-if="processingStatuses[doc.id].started_at" class="debug-info-row">
                        <text class="debug-info-label">处理开始</text>
                        <text class="debug-info-value">{{ formatFullDate(processingStatuses[doc.id].started_at) }}</text>
                      </view>
                      <view v-if="processingStatuses[doc.id].completed_at" class="debug-info-row">
                        <text class="debug-info-label">处理完成</text>
                        <text class="debug-info-value">{{ formatFullDate(processingStatuses[doc.id].completed_at) }}</text>
                      </view>
                    </view>
                    <view v-else class="debug-processing-loading">
                      <text class="debug-processing-loading-text">{{ loadingStatuses ? '加载处理状态...' : '点击刷新获取状态' }}</text>
                    </view>
                  </view>

                  <!-- Link note -->
                  <view v-else class="debug-link-note">
                    <text class="debug-link-note-text">(链接无需处理)</text>
                  </view>
                </view>
              </view>
            </view>
          </template>
        </scroll-view>

        <!-- Footer Actions -->
        <view class="debug-footer">
          <view class="debug-action-btn" @click="toggleRawJson">
            <text class="debug-action-text">{{ showRawJson ? '返回结构视图' : '查看原始JSON' }}</text>
          </view>
          <view class="debug-action-btn debug-action-primary" @click="copyDebugInfo">
            <text class="debug-action-text">复制全部信息</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getSpaceDocuments, deleteSpaceDocument, addSpaceLink, uploadSpaceDocument, getDocumentProcessingStatus } from '@/api/space'
import config from '@/config'
import { getTokens } from '@/utils/storage'
import { useUserStore } from '@/store/user'
import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'

export default {
  components: {
    UModal,
    UToast
  },

  data() {
    return {
      spaceId: '',
      spaceName: '',
      loading: true,
      loadError: null,
      documents: [],
      showDeleteModal: false,
      docToDelete: null,
      isDeleting: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      },
      // 存储相关
      userTier: 'FREE', // FREE | PLUS | ULTRA | ALPHA
      storageUsed: 0,   // 已使用字节数

      // 添加文件弹窗状态
      showAddFilePopup: false,
      addFilePopupVisible: false,

      // 添加链接对话框状态
      showLinkDialog: false,
      linkDialogVisible: false,
      linkTitle: '',
      linkUrl: '',
      isAddingLink: false,

      // 上传状态
      isUploading: false,
      uploadProgress: 0,
      uploadFileName: '',

      // 升级提示弹窗状态
      showUpgradeModal: false,

      // 待上传文件大小（用于弹窗提示）
      pendingFileSize: 0,

      // 标记当前是文件大小超限（vs 存储空间不足）
      fileSizeExceeded: false,

      // Debug 面板状态
      showDebugPanel: false,
      debugPanelVisible: false,
      showRawJson: false,
      processingStatuses: {},  // { documentId: ProcessingStatusResponse }
      loadingStatuses: false
    }
  },

  computed: {
    deleteModalContent() {
      if (!this.docToDelete) return ''
      const typeLabel = this.docToDelete.doc_type === 'link' ? '链接' : '文档'
      return `确定要删除${typeLabel}「${this.docToDelete.title}」吗？此操作不可恢复。`
    },

    // 订阅计划存储限制 (字节)
    storageLimits() {
      return {
        FREE: 30 * 1024 * 1024,    // 30MB
        PLUS: 200 * 1024 * 1024,   // 200MB
        ULTRA: 500 * 1024 * 1024,  // 500MB
        ALPHA: 500 * 1024 * 1024   // 500MB - Alpha 内测用户
      }
    },

    storageLimit() {
      return this.storageLimits[this.userTier] || this.storageLimits.FREE
    },

    // 单文件上传大小限制 (字节)
    uploadFileLimits() {
      return {
        FREE: 10 * 1024 * 1024,    // 10MB
        PLUS: 50 * 1024 * 1024,    // 50MB
        ULTRA: 100 * 1024 * 1024,  // 100MB
        ALPHA: 100 * 1024 * 1024   // 100MB
      }
    },

    uploadFileLimit() {
      return this.uploadFileLimits[this.userTier] || this.uploadFileLimits.FREE
    },

    // 是否已过期的付费订阅
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

    // 下一订阅等级信息
    nextTierInfo() {
      const tierOrder = ['FREE', 'PLUS', 'ULTRA']
      const currentIdx = tierOrder.indexOf(this.userTier)
      if (currentIdx < 0 || currentIdx >= tierOrder.length - 1) return null
      const nextTier = tierOrder[currentIdx + 1]
      const labels = { PLUS: 'Plus', ULTRA: 'Ultra' }
      const uploadLimits = { PLUS: 50, ULTRA: 100 }
      const storageLimits = { PLUS: 200, ULTRA: 500 }
      return {
        label: labels[nextTier],
        uploadLimitMB: uploadLimits[nextTier],
        storageLimitMB: storageLimits[nextTier]
      }
    },

    storagePercent() {
      if (this.storageLimit === 0) return 0
      const percent = (this.storageUsed / this.storageLimit) * 100
      return Math.min(100, Math.round(percent * 10) / 10) // 保留一位小数，最大100
    },

    storageColor() {
      const percent = this.storagePercent
      if (percent >= 90) return '#EF4444' // 红色 - 危险
      if (percent >= 70) return '#F59E0B' // 琥珀色 - 警告
      return '#7ACC71' // 绿色 - 正常
    },

    tierLabel() {
      const labels = {
        FREE: 'Free 版',
        PLUS: 'Plus 版',
        ULTRA: 'Ultra 版',
        ALPHA: 'Alpha 版'
      }
      return labels[this.userTier] || labels.FREE
    },

    // 升级弹窗内容
    upgradeModalContent() {
      const limitMB = (this.storageLimit / (1024 * 1024)).toFixed(0)
      const remainingMB = ((this.storageLimit - this.storageUsed) / (1024 * 1024)).toFixed(1)

      // 已到期用户 — 优先级最高
      if (this.isExpiredSubscription) {
        const tierLabel = this.expiredTierLabel
        if (this.fileSizeExceeded && this.pendingFileSize > 0) {
          const fileSizeMB = (this.pendingFileSize / (1024 * 1024)).toFixed(1)
          return `你的 ${tierLabel} 订阅已到期，当前文件上传上限为 10MB，该文件 ${fileSizeMB}MB 无法上传。\n\n续费 ${tierLabel} 即可恢复更大上传额度。`
        }
        return `你的 ${tierLabel} 订阅已到期，存储空间已降至 ${limitMB}MB。\n\n续费即可恢复原有空间和功能。`
      }

      // 文件大小超限（非存储空间不足）
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
      return `当前 ${this.tierLabel} 存储空间为 ${limitMB}MB，已达到上限。\n\n升级订阅计划可获得更大存储空间。`
    },

    // Debug: 文件数量
    fileCount() {
      return this.documents.filter(d => d.doc_type === 'document').length
    },

    // Debug: 链接数量
    linkCount() {
      return this.documents.filter(d => d.doc_type === 'link').length
    },

    // Debug: JSON 格式的调试信息
    debugInfoJson() {
      const info = {
        space: {
          id: this.spaceId,
          name: this.spaceName,
          userTier: this.userTier,
          storageUsed: this.storageUsed,
          storageLimit: this.storageLimit,
          storagePercent: this.storagePercent
        },
        meta: {
          totalDocuments: this.documents.length,
          fileCount: this.fileCount,
          linkCount: this.linkCount
        },
        documents: this.documents.map(doc => ({
          ...doc,
          processing: this.processingStatuses[doc.id] || null
        }))
      }
      return JSON.stringify(info, null, 2)
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    this.loadUserTier()
    this.loadDocuments()
  },

  onShow() {
    this.loadUserTier()
    if (this.spaceId && !this.loading) {
      this.loadDocuments()
    }
  },

  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    loadUserTier() {
      const userStore = useUserStore()
      const rawTier = userStore.user?.subscription_tier?.toUpperCase() || 'FREE'
      const tierMap = { BASIC: 'PLUS', PREMIUM: 'ULTRA' }
      this.userTier = tierMap[rawTier] || rawTier
    },

    goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack({ delta: 1 })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    async loadDocuments() {
      if (!this.spaceId) {
        this.loading = false
        return
      }

      try {
        this.loading = true
        this.loadError = null
        const response = await getSpaceDocuments(this.spaceId)
        this.documents = response?.documents || []
        this.calculateStorageUsed()
        // 自动加载处理状态
        this.$nextTick(() => {
          this.loadProcessingStatuses()
        })
      } catch (error) {
        this.loadError = error.message || '加载失败，请检查网络后重试'
        this.documents = []
      } finally {
        this.loading = false
      }
    },

    getDocIcon(doc) {
      if (doc.doc_type === 'link') {
        return '/static/icons/phosphor-icons/SVGs/regular/link.svg'
      }

      const ext = doc.original_filename ? doc.original_filename.split('.').pop()?.toLowerCase() : ''
      switch (ext) {
        case 'pdf':
          return '/static/icons/phosphor-icons/SVGs/regular/file-pdf.svg'
        case 'doc':
        case 'docx':
          return '/static/icons/phosphor-icons/SVGs/regular/file-doc.svg'
        case 'txt':
          return '/static/icons/phosphor-icons/SVGs/regular/file-text.svg'
        default:
          return '/static/icons/phosphor-icons/SVGs/regular/file.svg'
      }
    },

    getDocTypeLabel(doc) {
      if (doc.doc_type === 'link') {
        return '链接'
      }

      const ext = doc.original_filename ? doc.original_filename.split('.').pop()?.toLowerCase() : ''
      switch (ext) {
        case 'pdf':
          return 'PDF 文档'
        case 'doc':
        case 'docx':
          return 'Word 文档'
        case 'txt':
          return '文本文件'
        default:
          return '文档'
      }
    },

    truncateTitle(title, maxLength = 16) {
      if (!title) return ''
      if (title.length <= maxLength) return title
      return title.slice(0, maxLength) + '...'
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
    },

    calculateStorageUsed() {
      let totalBytes = 0
      for (const doc of this.documents) {
        if (doc.doc_type === 'link') {
          // 链接按 URL 字符串的 UTF-8 字节长度计算
          const urlLength = new Blob([doc.url || '']).size
          const titleLength = new Blob([doc.title || '']).size
          totalBytes += urlLength + titleLength
        } else {
          // 文件按实际大小计算
          totalBytes += doc.file_size || 0
        }
      }
      this.storageUsed = totalBytes
    },

    formatDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      const month = date.getMonth() + 1
      const day = date.getDate()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${month}月${day}日 ${hours}:${minutes}`
    },

    handleDocClick(doc) {
      // 只有链接类型才响应点击
      if (doc.doc_type !== 'link') return

      // #ifdef H5
      window.open(doc.url, '_blank')
      // #endif

      // #ifdef APP-PLUS
      plus.runtime.openURL(doc.url)
      // #endif

      // #ifdef MP-WEIXIN
      // 微信小程序需要配置业务域名才能打开 webview
      uni.setClipboardData({
        data: doc.url,
        success: () => {
          this.showCustomToast('链接已复制到剪贴板', 'success')
        }
      })
      // #endif
    },

    showDeleteConfirm(doc) {
      this.docToDelete = doc
      this.showDeleteModal = true
    },

    async doDeleteDocument() {
      if (this.isDeleting || !this.docToDelete) return
      this.isDeleting = true

      try {
        await deleteSpaceDocument(this.spaceId, this.docToDelete.id)
        this.showDeleteModal = false
        this.showCustomToast('删除成功', 'success')
        this.documents = this.documents.filter(d => d.id !== this.docToDelete.id)
        this.calculateStorageUsed()
        this.docToDelete = null
      } catch (error) {
        this.showCustomToast(error.message || '删除失败，请重试', 'error')
      } finally {
        this.isDeleting = false
      }
    },

    // 打开添加文件弹窗
    handleAddFile() {
      this.showAddFilePopup = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.addFilePopupVisible = true
        }, 10)
      })
    },

    // 关闭添加文件弹窗
    closeAddFilePopup() {
      this.addFilePopupVisible = false
      setTimeout(() => {
        this.showAddFilePopup = false
      }, 250)
    },

    // 添加文档
    async handleAddDocument() {
      if (this.isUploading) {
        this.showCustomToast('请等待上传完成', 'error')
        return
      }

      this.closeAddFilePopup()

      // #ifdef H5
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.pdf,.doc,.docx,.txt,.xlsx,.xls,.pptx,.ppt,.md,.html,.htm,.csv,.epub'
      input.onchange = async (e) => {
        const file = e.target.files[0]
        if (file) {
          // 验证单文件大小（按订阅等级）
          if (file.size > this.uploadFileLimit) {
            this.pendingFileSize = file.size
            this.fileSizeExceeded = true
            this.showUpgradeModal = true
            return
          }

          // 验证文件扩展名
          const ext = file.name.split('.').pop()?.toLowerCase()
          const validExtensions = ['pdf', 'doc', 'docx', 'txt', 'xlsx', 'xls', 'pptx', 'ppt', 'md', 'html', 'htm', 'csv', 'epub']
          if (!validExtensions.includes(ext)) {
            this.showCustomToast('不支持该文件类型', 'error')
            return
          }

          // 检查存储空间是否足够
          if (!this.checkStorageSpace(file.size)) {
            return
          }

          this.uploadFileName = file.name
          await this.uploadFileH5(file)
        }
      }
      input.click()
      // #endif

      // #ifdef APP-PLUS || MP-WEIXIN
      try {
        const files = await chooseLocalFiles({
          count: 1,
          extension: ['pdf', 'doc', 'docx', 'txt', 'xlsx', 'xls', 'pptx', 'ppt', 'md', 'html', 'htm', 'csv', 'epub']
        })
        if (!files.length) return

        const tempFile = files[0]
        if (!tempFile.path) {
          this.showCustomToast('未获取到文件路径', 'error')
          return
        }

        // 检查存储空间是否足够
        if (!this.checkStorageSpace(tempFile.size || 0)) {
          return
        }
        this.uploadFileName = tempFile.name || '文件'
        await this.uploadFile(tempFile.path)
      } catch (err) {
        if (!isPickerCancel(err)) {
          const errMsg = getPickerErrorMessage(err)
          console.error('[KnowledgeBase] 选择文件失败:', errMsg, err)
          this.showCustomToast(`选择文件失败${errMsg ? `: ${errMsg}` : ''}`, 'error')
        }
      }
      // #endif
    },

    // H5 上传文件
    async uploadFileH5(file) {
      const tokens = getTokens()
      if (!tokens?.access_token) {
        this.showCustomToast('登录已过期，请重新登录', 'error')
        return
      }

      this.isUploading = true
      this.uploadProgress = 0
      this.uploadFileName = file.name

      return new Promise((resolve, reject) => {
        const formData = new FormData()
        formData.append('file', file)

        const xhr = new XMLHttpRequest()

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            this.uploadProgress = Math.round((e.loaded / e.total) * 100)
          }
        }

        xhr.onload = async () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            this.showCustomToast('上传成功', 'success')
            await this.loadDocuments()
            resolve()
          } else {
            let errorMessage = '上传失败'
            try {
              const errorData = JSON.parse(xhr.responseText)
              errorMessage = errorData.detail || errorData.message || '上传失败'
            } catch (e) {
              errorMessage = xhr.statusText || '上传失败'
            }
            this.showCustomToast(errorMessage, 'error')
            reject(new Error(errorMessage))
          }
          this.isUploading = false
          this.uploadProgress = 0
        }

        xhr.onerror = () => {
          this.showCustomToast('网络错误', 'error')
          this.isUploading = false
          this.uploadProgress = 0
          reject(new Error('网络错误'))
        }

        xhr.open('POST', `${config.API_BASE_URL}/api/spaces/${this.spaceId}/documents/upload`)
        xhr.setRequestHeader('Authorization', `Bearer ${tokens.access_token}`)
        xhr.send(formData)
      })
    },

    // 原生/小程序 上传文件
    async uploadFile(filePath) {
      this.isUploading = true
      this.uploadProgress = 0
      try {
        await uploadSpaceDocument(this.spaceId, filePath, (res) => {
          this.uploadProgress = res.progress || 0
        })
        this.showCustomToast('上传成功', 'success')
        await this.loadDocuments()
      } catch (error) {
        this.showCustomToast(error.message || '上传失败', 'error')
      } finally {
        this.isUploading = false
        this.uploadProgress = 0
      }
    },

    // 打开添加链接对话框
    handleAddLink() {
      this.closeAddFilePopup()
      this.showLinkDialog = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.linkDialogVisible = true
        }, 10)
      })
    },

    // 关闭添加链接对话框
    closeLinkDialog() {
      this.linkDialogVisible = false
      setTimeout(() => {
        this.showLinkDialog = false
        this.linkTitle = ''
        this.linkUrl = ''
      }, 250)
    },

    // 提交链接
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

      // URL 验证
      try {
        new URL(url)
      } catch (e) {
        this.showCustomToast('请输入有效的网址', 'error')
        return
      }

      // 预估链接数据大小并检查存储空间
      const estimatedSize = new Blob([url, title]).size
      if (!this.checkStorageSpace(estimatedSize)) {
        this.closeLinkDialog()
        return
      }

      this.isAddingLink = true
      try {
        await addSpaceLink(this.spaceId, { title, url })
        this.showCustomToast('链接添加成功', 'success')
        this.closeLinkDialog()
        await this.loadDocuments()
      } catch (error) {
        this.showCustomToast(error.message || '添加链接失败', 'error')
      } finally {
        this.isAddingLink = false
      }
    },

    // 处理升级操作
    handleUpgrade() {
      this.showUpgradeModal = false
      this.pendingFileSize = 0
      this.fileSizeExceeded = false
      uni.navigateTo({
        url: '/pages/subscription/subscription'
      })
    },

    // 处理升级弹窗关闭
    handleUpgradeModalClose() {
      this.showUpgradeModal = false
      this.pendingFileSize = 0
      this.fileSizeExceeded = false
    },

    // 检查是否有足够的存储空间
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


    // ============ Debug 面板相关方法 ============

    // 打开 Debug 面板
    toggleDebugPanel() {
      this.showDebugPanel = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.debugPanelVisible = true
        }, 10)
      })
      // 加载处理状态
      this.loadProcessingStatuses()
    },

    // 关闭 Debug 面板
    closeDebugPanel() {
      this.debugPanelVisible = false
      setTimeout(() => {
        this.showDebugPanel = false
        this.showRawJson = false
      }, 250)
    },

    // 加载所有文档的处理状态
    async loadProcessingStatuses() {
      if (this.loadingStatuses) return

      const fileDocuments = this.documents.filter(d => d.doc_type === 'document')
      if (fileDocuments.length === 0) return

      this.loadingStatuses = true
      const statuses = { ...this.processingStatuses }

      try {
        // 并行请求所有文档的处理状态
        const promises = fileDocuments.map(doc =>
          getDocumentProcessingStatus(this.spaceId, doc.id)
            .then(res => ({ docId: doc.id, status: res }))
            .catch(() => ({ docId: doc.id, status: null }))
        )

        const results = await Promise.all(promises)

        results.forEach(({ docId, status }) => {
          if (status) {
            statuses[docId] = status
          }
        })

        this.processingStatuses = statuses
      } catch (error) {
        console.error('Failed to load processing statuses:', error)
      } finally {
        this.loadingStatuses = false
      }
    },

    // 获取状态标签
    getStatusLabel(status) {
      const labels = {
        'not_started': '未开始',
        'pending': '等待处理',
        'processing': '处理中...',
        'completed': '处理完成',
        'failed': '处理失败',
        'loading': '加载中...'
      }
      return labels[status] || status
    },

    // 获取状态颜色
    getStatusColor(status) {
      const colors = {
        'not_started': '#6B7280',
        'pending': '#F59E0B',
        'processing': '#3B82F6',
        'completed': '#10B981',
        'failed': '#EF4444',
        'loading': '#6B7280'
      }
      return colors[status] || '#6B7280'
    },

    // 获取文档处理状态
    getDocStatus(docId) {
      const statusData = this.processingStatuses[docId]
      if (!statusData) {
        return this.loadingStatuses ? 'loading' : 'not_started'
      }
      return statusData.status || 'not_started'
    },

    // 获取切片数量
    getDocChunkCount(docId) {
      return this.processingStatuses[docId]?.chunk_count || 0
    },

    // 显示错误详情
    showErrorDetail(docId) {
      const msg = this.processingStatuses[docId]?.error_message || '处理失败，请重试'
      this.showCustomToast(msg, 'error')
    },

    // 切换 JSON 视图
    toggleRawJson() {
      this.showRawJson = !this.showRawJson
    },

    // 复制调试信息到剪贴板
    copyDebugInfo() {
      const debugText = this.debugInfoJson

      // #ifdef H5
      if (navigator.clipboard) {
        navigator.clipboard.writeText(debugText).then(() => {
          this.showCustomToast('已复制到剪贴板', 'success')
        }).catch(() => {
          this.showCustomToast('复制失败', 'error')
        })
      }
      // #endif

      // #ifndef H5
      uni.setClipboardData({
        data: debugText,
        success: () => {
          this.showCustomToast('已复制到剪贴板', 'success')
        },
        fail: () => {
          this.showCustomToast('复制失败', 'error')
        }
      })
      // #endif
    },

    // 格式化完整日期时间
    formatFullDate(dateStr) {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const seconds = String(date.getSeconds()).padStart(2, '0')
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    }
  }
}
</script>

<style>
.knowledge-base-page {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A0A;
  position: relative;
  overflow: hidden;
}

/* Navigation Bar */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.nav-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: -70rpx;
  z-index: -1;
  background: linear-gradient(
    to bottom,
    rgba(10, 10, 10, 0.6) 0%,
    rgba(10, 10, 10, 0.45) 50%,
    rgba(10, 10, 10, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
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

/* Loading, Error & Empty States */
.loading-container,
.error-container,
.empty-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
}

.loading-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.6);
}

.error-icon {
  width: 100rpx;
  height: 100rpx;
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  margin-bottom: 24rpx;
}

.error-text {
  font-size: 28rpx;
  color: rgba(239, 68, 68, 0.9);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 500rpx;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(0, 136, 255, 0.15);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
  border-radius: 40rpx;
}

.retry-btn:active {
  background: rgba(0, 136, 255, 0.25);
}

.retry-btn-text {
  font-size: 28rpx;
  color: #0088FF;
}

.empty-icon {
  width: 120rpx;
  height: 120rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  margin-bottom: 32rpx;
}

.empty-text {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 16rpx;
}

.empty-hint {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
  max-width: 400rpx;
}

/* Content Scroll */
.content-scroll {
  flex: 1;
  padding: calc(100vh * 1.5 / 26 + 100rpx) calc(100vw / 24) 180rpx;
  box-sizing: border-box;
}

/* Document List */
.document-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.document-item {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  transition: all 0.2s ease;
}

.document-item:active {
  background: rgba(255, 255, 255, 0.08);
}

.document-icon-wrapper {
  width: 60rpx;
  height: 60rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-right: 20rpx;
}

.document-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.8;
}

.document-info {
  flex: 1;
  min-width: 0;
}

.document-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-meta {
  display: flex;
  align-items: center;
  gap: 4rpx;
  min-width: 0;
}

.document-type {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.document-size {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.35);
  margin-left: 8rpx;
}

.document-url {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.35);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-action {
  flex-shrink: 0;
  margin-left: 12rpx;
}

.delete-btn {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8rpx;
  transition: background 150ms ease;
}

.delete-btn:active {
  background: rgba(239, 68, 68, 0.15);
}

.delete-icon {
  width: 32rpx;
  height: 32rpx;
  /* 红色滤镜 - 与 app 其他红色元素一致 (#EF4444) */
  filter: invert(47%) sepia(82%) saturate(2476%) hue-rotate(332deg) brightness(97%) contrast(92%);
}

/* ========== 文档处理状态 Badges ========== */
.document-status-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 8rpx;
  flex-wrap: wrap;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(255, 255, 255, 0.06);
}

/* 状态背景色 */
.status-not_started { background: rgba(107, 114, 128, 0.15); }
.status-pending { background: rgba(245, 158, 11, 0.15); }
.status-processing { background: rgba(59, 130, 246, 0.15); }
.status-completed { background: rgba(16, 185, 129, 0.15); }
.status-failed { background: rgba(239, 68, 68, 0.15); }
.status-loading { background: rgba(255, 255, 255, 0.06); }

.status-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

/* 处理中动画 */
.status-processing .status-dot {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.status-text {
  font-size: 20rpx;
  font-weight: 500;
  line-height: 1.2;
}

/* 切片数量 Badge */
.chunk-badge {
  display: inline-flex;
  align-items: center;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.2);
}

.chunk-text {
  font-size: 20rpx;
  color: #10B981;
  font-weight: 500;
}

/* 错误 Badge */
.error-badge {
  display: inline-flex;
  align-items: center;
  gap: 4rpx;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.25);
  transition: background 150ms ease;
}

.error-badge:active {
  background: rgba(239, 68, 68, 0.2);
}

.error-icon {
  width: 16rpx;
  height: 16rpx;
  filter: invert(47%) sepia(82%) saturate(2476%) hue-rotate(332deg) brightness(97%) contrast(92%);
}

.error-text {
  font-size: 20rpx;
  color: #EF4444;
  font-weight: 500;
}

/* Storage Indicator */
.storage-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20rpx calc(100vw / 24);
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background: linear-gradient(
    to top,
    rgba(10, 10, 10, 0.95) 0%,
    rgba(10, 10, 10, 0.8) 60%,
    rgba(10, 10, 10, 0) 100%
  );
}

.storage-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 24rpx;
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  backdrop-filter: blur(20px) saturate(150%);
}

.storage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.storage-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.storage-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}

.storage-title {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.tier-badge {
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.1);
}

.tier-free {
  background: rgba(255, 255, 255, 0.08);
}

.tier-plus {
  background: rgba(0, 136, 255, 0.15);
}

.tier-ultra {
  background: rgba(255, 215, 0, 0.15);
}

.tier-alpha {
  background: rgba(138, 43, 226, 0.15);
}

.tier-text {
  font-size: 22rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
}

.tier-plus .tier-text {
  color: #0088FF;
}

.tier-ultra .tier-text {
  color: #FFD700;
}

.tier-alpha .tier-text {
  color: #8A2BE2;
}

.storage-progress-track {
  width: 100%;
  height: 8rpx;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4rpx;
  overflow: hidden;
  margin-bottom: 12rpx;
}

.storage-progress-fill {
  height: 100%;
  border-radius: 4rpx;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.storage-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.storage-used {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
}

.storage-percent {
  font-size: 24rpx;
  font-weight: 600;
}

/* Add Button */
.nav-right {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.add-btn {
  background-color: #007AFF !important;
  border: none !important;
}

.add-btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

/* Add File Popup */
.knowledge-base-page .add-file-popup-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 200;
}

.knowledge-base-page .add-file-popup {
  position: fixed;
  right: calc(100vw / 24);
  top: calc(100vh * 1.5 / 26 + 88rpx);
  bottom: auto;
  height: auto;
  min-width: 280rpx;
  background: rgba(30, 30, 45, 0.95);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 20rpx;
  box-shadow:
    0 12rpx 40rpx rgba(0, 0, 0, 0.4),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  overflow: visible;
  transform: translateY(-20rpx) scale(0.9);
  opacity: 0;
  transition: all 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.knowledge-base-page .add-file-popup.popup-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.knowledge-base-page .popup-arrow-up {
  position: absolute;
  right: 20rpx;
  top: -16rpx;
  width: 0;
  height: 0;
  border-left: 16rpx solid transparent;
  border-right: 16rpx solid transparent;
  border-bottom: 16rpx solid rgba(30, 30, 45, 0.95);
}

.popup-option {
  display: flex;
  align-items: center;
  padding: 28rpx 32rpx;
  transition: background 150ms ease;
}

.popup-option:active {
  background: rgba(255, 255, 255, 0.08);
}

.popup-option-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 24rpx;
  filter: brightness(0) invert(1);
  opacity: 0.85;
}

.popup-option-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.popup-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 24rpx;
}

/* Link Dialog */
.link-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 200ms ease;
}

.link-dialog-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.link-dialog {
  width: 560rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  box-shadow:
    0 16rpx 48rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  overflow: hidden;
  transform: translateY(40rpx) scale(0.95);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.link-dialog.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.link-dialog-title {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
  text-align: center;
  padding: 32rpx 32rpx 24rpx;
}

.link-dialog-content {
  padding: 0 32rpx 24rpx;
}

.link-input-group {
  margin-bottom: 24rpx;
}

.link-input-group:last-child {
  margin-bottom: 0;
}

.link-input-label {
  display: block;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 12rpx;
}

.link-input {
  width: 100%;
  height: 80rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.link-input-placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.link-dialog-actions {
  display: flex;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
}

.link-btn {
  flex: 1;
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms ease;
}

.link-btn:active {
  background: rgba(255, 255, 255, 0.05);
}

.link-btn-cancel {
  border-right: 1rpx solid rgba(255, 255, 255, 0.1);
}

.link-btn-cancel .link-btn-text {
  color: rgba(255, 255, 255, 0.6);
}

.link-btn-confirm .link-btn-text {
  color: #007AFF;
  font-weight: 600;
}

.link-btn-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.link-btn-text {
  font-size: 30rpx;
}

/* Upload Overlay */
.upload-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background-color: rgba(10, 10, 10, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
}

.upload-spinner {
  width: 80rpx;
  height: 80rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.1);
  border-top-color: #007AFF;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.upload-filename {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
  max-width: 400rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-progress-track {
  width: 400rpx;
  height: 8rpx;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4rpx;
  overflow: hidden;
}

.upload-progress-bar {
  height: 100%;
  background: #007AFF;
  border-radius: 4rpx;
  transition: width 0.3s ease;
}

.upload-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
}

/* ============ Nav Center & Debug Button ============ */
.nav-center {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.debug-btn {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8rpx;
  background: rgba(255, 255, 255, 0.08);
  transition: background 150ms ease;
}

.debug-btn:active {
  background: rgba(255, 255, 255, 0.15);
}

.debug-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

/* ============ Debug Panel ============ */
.debug-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 500;
  background: rgba(0, 0, 0, 0);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  transition: background 200ms ease;
}

.debug-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.debug-panel {
  width: 100%;
  max-height: 85vh;
  background: rgba(15, 15, 20, 0.98);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border-top-left-radius: 32rpx;
  border-top-right-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-bottom: none;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.debug-panel.panel-show {
  transform: translateY(0);
  opacity: 1;
}

.debug-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx 32rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.debug-header-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

.debug-close-btn {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  transition: background 150ms ease;
}

.debug-close-btn:active {
  background: rgba(255, 255, 255, 0.15);
}

.debug-close-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}

.debug-content {
  flex: 1;
  padding: 24rpx 32rpx;
  overflow-y: auto;
  box-sizing: border-box;
}

.debug-section {
  margin-bottom: 32rpx;
}

.debug-section:last-child {
  margin-bottom: 0;
}

.debug-section-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.debug-section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 16rpx;
}

.debug-section-header .debug-section-title {
  margin-bottom: 0;
}

.debug-loading-badge {
  padding: 4rpx 12rpx;
  background: rgba(59, 130, 246, 0.2);
  border-radius: 8rpx;
}

.debug-loading-text {
  font-size: 22rpx;
  color: #3B82F6;
}

.debug-info-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  overflow: hidden;
  box-sizing: border-box;
  max-width: 100%;
}

.debug-info-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8rpx 0;
  overflow: hidden;
  width: 100%;
}

.debug-info-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
  margin-right: 16rpx;
  min-width: 120rpx;
}

.debug-info-value {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.9);
  text-align: right;
  word-break: break-all;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.debug-mono {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 22rpx;
}

.debug-id,
.debug-url {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-error {
  color: #EF4444;
}

.debug-empty {
  padding: 40rpx;
  text-align: center;
}

.debug-empty-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.4);
}

.debug-doc-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.debug-doc-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  overflow: hidden;
}

.debug-doc-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.debug-doc-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}

.debug-doc-title {
  font-size: 28rpx;
  font-weight: 500;
  color: #ffffff;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-doc-info {
  padding-left: 48rpx;
  overflow: hidden;
}

.debug-processing-section {
  padding-left: 48rpx;
  overflow: hidden;
}

.debug-processing-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.1);
  margin: 12rpx 0;
}

.debug-processing-info {
  /* Processing info styles inherited from debug-info-row */
}

.debug-processing-loading {
  padding: 8rpx 0;
}

.debug-processing-loading-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
}

.debug-status-wrapper {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.debug-status-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
}

.debug-link-note {
  padding: 8rpx 0 0 48rpx;
}

.debug-link-note-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
  font-style: italic;
}

.debug-footer {
  display: flex;
  gap: 16rpx;
  padding: 20rpx 32rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.debug-action-btn {
  flex: 1;
  height: 80rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  transition: all 150ms ease;
}

.debug-action-btn:active {
  background: rgba(255, 255, 255, 0.12);
  transform: scale(0.98);
}

.debug-action-primary {
  background: rgba(0, 122, 255, 0.15);
  border-color: rgba(0, 122, 255, 0.3);
}

.debug-action-primary:active {
  background: rgba(0, 122, 255, 0.25);
}

.debug-action-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.8);
}

.debug-action-primary .debug-action-text {
  color: #007AFF;
}

/* Raw JSON View */
.debug-raw-json {
  background: rgba(0, 0, 0, 0.3);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
  padding: 20rpx;
  overflow-x: auto;
}

.debug-json-text {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
