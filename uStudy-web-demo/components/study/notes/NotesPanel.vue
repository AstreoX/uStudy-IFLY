<template>
  <view class="notes-panel">
    <view v-if="!spaceId" class="placeholder-wrap">
      <text class="placeholder-text">请先选择学习空间</text>
      <text class="placeholder-sub">选择左侧学习空间后可查看笔记</text>
    </view>

    <template v-else>
      <!-- List View -->
      <view v-if="viewMode === 'list'" class="notes-list-view">
        <!-- Loading -->
        <view v-if="loading" class="notes-status">
          <text class="notes-status-text">正在加载笔记...</text>
        </view>

        <!-- Error -->
        <view v-else-if="loadError" class="notes-status notes-error">
          <text class="notes-error-text">{{ loadError }}</text>
          <view class="notes-retry-btn" @click="loadNotes">
            <text class="notes-retry-text">重试</text>
          </view>
        </view>

        <!-- Empty -->
        <view v-else-if="notes.length === 0" class="notes-status">
          <text class="notes-status-text">暂无笔记</text>
          <text class="notes-status-sub">在与 AI 对话时可以让 AI 为你创建笔记</text>
        </view>

        <!-- Notes Cards -->
        <scroll-view v-else class="notes-scroll" scroll-y>
          <view class="notes-card-grid">
            <view
              v-for="note in notes"
              :key="note.id"
              class="note-card"
              @click="openNoteDetail(note)"
            >
              <text class="note-card-title">{{ getNoteTitle(note) }}</text>
              <text class="note-card-preview">{{ truncateContent(note.content) }}</text>
              <view class="note-card-footer">
                <text class="note-card-time">{{ formatDate(note.created_at) }}</text>
                <view v-if="getNoteNodeTag(note)" class="note-card-tag">{{ getNoteNodeTag(note) }}</view>
                <view v-if="getNoteAttachmentCount(note) > 0" class="note-card-attach-badge">
                  {{ getNoteAttachmentCount(note) }} 附件
                </view>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>

      <!-- Detail View -->
      <view v-else class="notes-detail-view">
        <view class="detail-header">
          <view class="detail-back-btn" @click="backToList">
            <image class="detail-back-icon" src="/static/icons/phosphor/regular/arrow-left-white.svg" mode="aspectFit" />
            <text class="detail-back-text">返回列表</text>
          </view>
        </view>

        <view v-if="detailLoading" class="notes-status">
          <text class="notes-status-text">加载中...</text>
        </view>

        <scroll-view v-else-if="selectedNote" class="detail-scroll" scroll-y>
          <view class="detail-body">
            <text class="detail-title">{{ getNoteTitle(selectedNote) }}</text>
            <view v-if="getNoteNodeTag(selectedNote)" class="detail-node-tag">
              <text class="detail-node-tag-text">{{ getNoteNodeTag(selectedNote) }}</text>
            </view>
            <view v-if="selectedNote.content" class="detail-content">
              <MarkdownRender :content="selectedNote.content" />
            </view>
            <text v-else class="detail-content-empty">（无内容）</text>

            <view v-if="selectedNote.attachments && selectedNote.attachments.length" class="detail-attachments">
              <text class="detail-attach-label">附件</text>
              <view
                v-for="(att, idx) in selectedNote.attachments"
                :key="idx"
                class="detail-attach-item"
              >
                <text class="detail-attach-name">{{ getAttachmentDisplayName(att) }}</text>
              </view>
            </view>

            <view class="detail-meta">
              <text class="detail-meta-text">创建于 {{ formatDate(selectedNote.created_at) }}</text>
              <text v-if="selectedNote.updated_at && selectedNote.updated_at !== selectedNote.created_at" class="detail-meta-text">
                更新于 {{ formatDate(selectedNote.updated_at) }}
              </text>
            </view>
          </view>
        </scroll-view>
      </view>
    </template>

    <UToast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import UToast from '@/components/u-toast/u-toast.vue'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import { getSpaceNotes, getNoteDetail } from '@/api/space'

export default {
  name: 'NotesPanel',
  components: {
    UToast,
    MarkdownRender
  },
  props: {
    spaceId: {
      type: [String, Number],
      default: ''
    }
  },
  data() {
    return {
      viewMode: 'list',
      loading: false,
      loadError: '',
      notes: [],
      selectedNote: null,
      detailLoading: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },
  watch: {
    spaceId: {
      immediate: true,
      handler() {
        this.resetState()
        if (this.spaceId) {
          this.loadNotes()
        }
      }
    }
  },
  methods: {
    showToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    resetState() {
      this.viewMode = 'list'
      this.loading = false
      this.loadError = ''
      this.notes = []
      this.selectedNote = null
      this.detailLoading = false
    },

    async loadNotes() {
      if (!this.spaceId) return

      try {
        this.loading = true
        this.loadError = ''
        const response = await getSpaceNotes(this.spaceId)
        this.notes = Array.isArray(response) ? response : (Array.isArray(response?.data) ? response.data : [])
      } catch (error) {
        this.notes = []
        this.loadError = error?.message || '加载失败，请检查网络后重试'
      } finally {
        this.loading = false
      }
    },

    async openNoteDetail(note) {
      if (!note?.id) return

      this.viewMode = 'detail'
      this.detailLoading = true
      this.selectedNote = null

      try {
        const detail = await getNoteDetail(this.spaceId, note.id)
        this.selectedNote = detail
      } catch (error) {
        this.showToast(error?.message || '加载笔记详情失败', 'error')
        this.viewMode = 'list'
      } finally {
        this.detailLoading = false
      }
    },

    backToList() {
      this.viewMode = 'list'
      this.selectedNote = null
      this.detailLoading = false
      this.loadNotes()
    },

    truncateContent(content) {
      if (!content) return ''
      return content.length > 120 ? content.substring(0, 120) + '...' : content
    },

    getNoteTitle(note) {
      const title = note?.title
      return typeof title === 'string' && title.trim() ? title.trim() : '未命名笔记'
    },

    getNoteNodeTag(note) {
      return note?.node_label || ''
    },

    getNoteAttachmentCount(note) {
      const count = Number(note?.attachment_count)
      if (Number.isFinite(count) && count > 0) return count
      return Array.isArray(note?.attachments) ? note.attachments.length : 0
    },

    getAttachmentDisplayName(att) {
      if (!att) return '未命名附件'
      return att.link_title || att.original_filename || att.link_url || att.file_url || '未命名附件'
    },

    formatDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      if (Number.isNaN(date.getTime())) return ''
      const month = date.getMonth() + 1
      const day = date.getDate()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${month}月${day}日 ${hours}:${minutes}`
    }
  }
}
</script>

<style scoped>
.notes-panel {
  width: 100%;
  height: 100%;
  position: relative;
}

.placeholder-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14rpx;
}

.placeholder-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.78);
}

.placeholder-sub {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.45);
}

/* List View */
.notes-list-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.notes-status {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
}

.notes-status-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.5);
}

.notes-status-sub {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.35);
}

.notes-error-text {
  font-size: 28rpx;
  color: rgba(239, 68, 68, 0.9);
}

.notes-retry-btn {
  padding: 12rpx 36rpx;
  background: rgba(0, 136, 255, 0.15);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
  border-radius: 30rpx;
  cursor: pointer;
}

.notes-retry-btn:hover {
  background: rgba(0, 136, 255, 0.25);
}

.notes-retry-text {
  font-size: 26rpx;
  color: #0088FF;
}

.notes-scroll {
  flex: 1;
  width: 100%;
}

.notes-card-grid {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  padding: 24rpx;
}

.note-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 24rpx;
  cursor: pointer;
  transition: background 0.15s ease;
}

.note-card:hover {
  background: rgba(255, 255, 255, 0.08);
}

.note-card-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 10rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-card-preview {
  display: block;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 14rpx;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.note-card-footer {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.note-card-time {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
}

.note-card-tag {
  font-size: 20rpx;
  color: rgba(129, 140, 248, 0.9);
  padding: 3rpx 10rpx;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 6rpx;
}

.note-card-attach-badge {
  font-size: 20rpx;
  color: rgba(34, 197, 94, 0.9);
  padding: 3rpx 10rpx;
  background: rgba(34, 197, 94, 0.12);
  border-radius: 6rpx;
}

/* Detail View */
.notes-detail-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-header {
  padding: 16rpx 24rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.detail-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  padding: 8rpx 16rpx;
  border-radius: 10rpx;
  cursor: pointer;
  transition: background 0.15s ease;
}

.detail-back-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.detail-back-icon {
  width: 28rpx;
  height: 28rpx;
}

.detail-back-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
}

.detail-scroll {
  flex: 1;
  width: 100%;
}

.detail-body {
  padding: 28rpx 32rpx;
}

.detail-title {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 16rpx;
  line-height: 1.4;
}

.detail-node-tag {
  display: inline-block;
  margin-bottom: 20rpx;
}

.detail-node-tag-text {
  font-size: 22rpx;
  color: rgba(129, 140, 248, 0.9);
  padding: 4rpx 14rpx;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 8rpx;
}

.detail-content {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.8;
  word-break: break-word;
}

.detail-content-empty {
  display: block;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.35);
}

.detail-attachments {
  margin-top: 36rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.detail-attach-label {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 14rpx;
}

.detail-attach-item {
  padding: 14rpx 16rpx;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10rpx;
  margin-bottom: 10rpx;
}

.detail-attach-name {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.6);
}

.detail-meta {
  margin-top: 32rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.detail-meta-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
}
</style>
