<template>
  <view class="notes-list-page">
    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">笔记管理</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Loading State -->
    <view v-if="loading" class="loading-container">
      <text class="loading-text">正在加载笔记列表...</text>
    </view>

    <!-- Error State -->
    <view v-else-if="loadError" class="error-container">
      <image class="error-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="error-text">{{ loadError }}</text>
      <view class="retry-btn" @click="loadNotes">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- Empty State -->
    <view v-else-if="notes.length === 0" class="empty-container">
      <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook.svg" mode="aspectFit"></image>
      <text class="empty-text">暂无笔记</text>
      <text class="empty-sub">在与 AI 对话时可以让 AI 为你创建笔记</text>
    </view>

    <!-- Notes List -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="notes-list">
        <view
          v-for="note in notes"
          :key="note.id"
          class="note-item"
          @click="handleNoteClick(note)"
        >
          <view class="note-main">
            <view class="note-info">
              <text class="note-title">{{ getNoteTitle(note) }}</text>
              <text class="note-preview">{{ truncateContent(note.content) }}</text>
              <view class="note-meta">
                <text class="note-date">{{ formatDate(note.created_at) }}</text>
                <text v-if="getNoteNodeTag(note)" class="note-node-tag">{{ getNoteNodeTag(note) }}</text>
                <text v-if="getNoteAttachmentCount(note) > 0" class="note-attach-badge">{{ getNoteAttachmentCount(note) }} 附件</text>
              </view>
            </view>
            <view class="note-item-actions" @click.stop>
              <view class="note-item-btn" @click.stop="startEditNote(note)">
                <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
              </view>
              <view class="note-item-btn note-item-btn-delete" @click.stop="showDeleteConfirm(note)">
                <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit" />
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- Note Detail Overlay -->
    <view v-if="showNoteDetail" class="note-detail-overlay" @click="closeNoteDetail">
      <view class="note-detail-card" @click.stop>
        <view class="note-detail-header" @touchmove.prevent>
          <view class="note-detail-back" @click="closeNoteDetail">
            <image class="note-detail-back-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
          </view>
          <text class="note-detail-title">{{ getNoteTitle(selectedNote) }}</text>
          <view class="note-detail-actions">
            <view class="note-item-btn" @click="startEditNote(selectedNote)">
              <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
            </view>
            <view class="note-item-btn note-item-btn-delete" @click="showDeleteConfirm(selectedNote)">
              <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit" />
            </view>
          </view>
        </view>
        <scroll-view class="note-detail-scroll" scroll-y>
          <view v-if="detailLoading" class="note-detail-loading">
            <text class="loading-text">加载中...</text>
          </view>
          <view v-else-if="selectedNote" class="note-detail-body">
            <markdown-render v-if="selectedNote.content" :content="selectedNote.content" />
            <text v-else class="note-detail-empty">（无内容）</text>
            <view v-if="selectedNote.attachments && selectedNote.attachments.length" class="note-detail-attachments">
              <view
                v-for="(att, idx) in selectedNote.attachments"
                :key="idx"
                class="note-detail-attach-item-wrap"
              >
                <image
                  v-if="att.mime_type && att.mime_type.startsWith('image/')"
                  :src="getFullAttachmentUrl(att.file_url)"
                  class="note-detail-attach-image"
                  mode="widthFix"
                  @click="previewAttachmentImage(att.file_url)"
                />
                <view v-else class="note-detail-attach-item">
                  <image class="note-detail-attach-icon" src="/static/icons/phosphor-icons/SVGs/regular/file.svg" mode="aspectFit"></image>
                  <text class="note-detail-attach-name">{{ getAttachmentDisplayName(att) }}</text>
                </view>
              </view>
            </view>
            <text class="note-detail-time">创建于 {{ formatDate(selectedNote.created_at) }}</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- Note Edit Overlay -->
    <view v-if="showNoteEdit" class="note-detail-overlay note-edit-overlay">
      <view class="note-detail-card">
        <view class="note-detail-header" @touchmove.prevent>
          <view class="note-detail-back" @click="closeNoteEdit">
            <image class="note-detail-back-icon" src="/static/icons/phosphor-icons/SVGs/regular/x.svg" mode="aspectFit"></image>
          </view>
          <text class="note-detail-title">编辑笔记</text>
          <view class="note-edit-save-btn" @click="saveNoteEdit">
            <text class="note-edit-save-text">{{ isSaving ? '保存中...' : '保存' }}</text>
          </view>
        </view>
        <input
          class="note-edit-title-input"
          v-model="editTitle"
          type="text"
          placeholder="笔记标题"
          maxlength="200"
          placeholder-style="color: rgba(255,255,255,0.3)"
        />
        <scroll-view class="note-detail-scroll" scroll-y>
          <view class="note-edit-body">
            <textarea
              class="note-edit-textarea"
              v-model="editContent"
              placeholder="笔记内容（支持 Markdown）"
              placeholder-style="color: rgba(255,255,255,0.3)"
              auto-height
            />
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- Delete Confirm Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除笔记"
      :content="deleteModalContent"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteNote"
      @close="showDeleteModal = false"
    />

    <!-- Toast -->
    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import { getSpaceNotes, getNoteDetail, updateNote, deleteNote } from '@/api/note'
import UToast from '@/components/u-toast/u-toast.vue'
import UModal from '@/components/u-modal/u-modal.vue'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import config from '@/config'

export default {
  components: {
    UToast,
    UModal,
    MarkdownRender
  },

  data() {
    return {
      spaceId: '',
      spaceName: '',
      loading: true,
      loadError: null,
      notes: [],
      showNoteDetail: false,
      selectedNote: null,
      detailLoading: false,
      // edit
      showNoteEdit: false,
      editNoteId: null,
      editTitle: '',
      editContent: '',
      isSaving: false,
      // delete
      showDeleteModal: false,
      noteToDelete: null,
      isDeleting: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  computed: {
    deleteModalContent() {
      return `确定要删除笔记「${this.noteToDelete ? this.getNoteTitle(this.noteToDelete) : ''}」吗？此操作无法撤销。`
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    this.loadNotes()
  },

  onShow() {
    if (this.spaceId && !this.loading) {
      this.loadNotes()
    }
  },

  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack({ delta: 1 })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    async loadNotes() {
      if (!this.spaceId) {
        this.loading = false
        return
      }

      try {
        this.loading = true
        this.loadError = null
        const response = await getSpaceNotes(this.spaceId)
        this.notes = Array.isArray(response) ? response : []
      } catch (error) {
        this.loadError = error.message || '加载失败，请检查网络后重试'
        this.notes = []
      } finally {
        this.loading = false
      }
    },

    truncateContent(content) {
      if (!content) return ''
      return content.length > 100 ? content.substring(0, 100) + '...' : content
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

    getFullAttachmentUrl(path) {
      if (!path) return ''
      if (/^https?:\/\//i.test(path)) return path
      return `${config.API_BASE_URL}${path}`
    },

    previewAttachmentImage(fileUrl) {
      const fullUrl = this.getFullAttachmentUrl(fileUrl)
      if (fullUrl) {
        uni.previewImage({ urls: [fullUrl], current: fullUrl })
      }
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
    },

    async handleNoteClick(note) {
      if (!note?.id) return
      this.showNoteDetail = true
      this.detailLoading = true
      this.selectedNote = null
      try {
        const detail = await getNoteDetail(this.spaceId, note.id)
        this.selectedNote = detail
      } catch (error) {
        this.showCustomToast(error.message || '加载笔记详情失败', 'error')
        this.showNoteDetail = false
      } finally {
        this.detailLoading = false
      }
    },

    closeNoteDetail() {
      this.showNoteDetail = false
      this.selectedNote = null
    },

    // --- Edit ---
    startEditNote(note) {
      if (!note) return
      this.editNoteId = note.id
      this.editTitle = note.title || ''
      this.editContent = note.content || ''
      this.showNoteEdit = true
    },

    closeNoteEdit() {
      this.showNoteEdit = false
    },

    async saveNoteEdit() {
      if (this.isSaving) return
      this.isSaving = true
      try {
        await updateNote(this.spaceId, this.editNoteId, {
          title: this.editTitle,
          content: this.editContent
        })
        const idx = this.notes.findIndex(n => n.id === this.editNoteId)
        if (idx !== -1) {
          this.notes.splice(idx, 1, { ...this.notes[idx], title: this.editTitle, content: this.editContent })
        }
        if (this.selectedNote?.id === this.editNoteId) {
          this.selectedNote = { ...this.selectedNote, title: this.editTitle, content: this.editContent }
        }
        this.showNoteEdit = false
        this.showCustomToast('已保存', 'success')
      } catch (e) {
        this.showCustomToast(e?.message || '保存失败', 'error')
      } finally {
        this.isSaving = false
      }
    },

    // --- Delete ---
    showDeleteConfirm(note) {
      if (!note) return
      this.noteToDelete = note
      this.showDeleteModal = true
    },

    async doDeleteNote() {
      if (this.isDeleting || !this.noteToDelete) return
      this.isDeleting = true
      try {
        await deleteNote(this.spaceId, this.noteToDelete.id)
        this.notes = this.notes.filter(n => n.id !== this.noteToDelete.id)
        if (this.selectedNote?.id === this.noteToDelete.id) {
          this.showNoteDetail = false
          this.selectedNote = null
        }
        this.showCustomToast('已删除', 'success')
      } catch (e) {
        this.showCustomToast(e?.message || '删除失败', 'error')
      } finally {
        this.showDeleteModal = false
        this.noteToDelete = null
        this.isDeleting = false
      }
    }
  }
}
</script>

<style>
.notes-list-page {
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
}

.empty-sub {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 12rpx;
}

/* Content Scroll */
.content-scroll {
  flex: 1;
  padding: calc(100vh * 1.5 / 26 + 100rpx) calc(100vw / 24) 60rpx;
  box-sizing: border-box;
}

/* Notes List */
.notes-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.note-item {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 28rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  transition: all 0.2s ease;
}

.note-item:active {
  background: rgba(255, 255, 255, 0.08);
}

.note-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.note-info {
  flex: 1;
  min-width: 0;
}

.note-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 10rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.note-preview {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 14rpx;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.note-meta {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex-wrap: wrap;
}

.note-date {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
}

.note-node-tag {
  font-size: 20rpx;
  color: rgba(129, 140, 248, 0.9);
  padding: 4rpx 12rpx;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 6rpx;
}

.note-attach-badge {
  font-size: 20rpx;
  color: rgba(34, 197, 94, 0.9);
  padding: 4rpx 12rpx;
  background: rgba(34, 197, 94, 0.12);
  border-radius: 6rpx;
}

/* Card action buttons */
.note-item-actions {
  display: flex;
  flex-direction: row;
  gap: 12rpx;
  flex-shrink: 0;
  margin-left: 16rpx;
  align-items: flex-start;
}

.note-item-btn {
  width: 52rpx;
  height: 52rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
}

.note-item-btn:active {
  background: rgba(255, 255, 255, 0.12);
}

.note-item-btn-icon {
  width: 30rpx;
  height: 30rpx;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}

.note-item-btn-delete {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
}

.note-item-btn-delete:active {
  background: rgba(239, 68, 68, 0.3);
}

.note-item-btn-delete .note-item-btn-icon {
  filter: brightness(0) invert(1);
  opacity: 1;
}

/* Note Detail Overlay */
.note-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 600;
  background: rgba(10, 10, 18, 0.95);
  display: flex;
  flex-direction: column;
}

.note-edit-overlay {
  z-index: 700;
}

.note-detail-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.note-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  padding-top: calc(100vh * 1.5 / 26);
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
  gap: 16rpx;
}

.note-detail-back {
  width: 60rpx;
  height: 60rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.note-detail-back-icon {
  width: 40rpx;
  height: 40rpx;
  filter: brightness(0) invert(1);
}

.note-detail-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-detail-actions {
  display: flex;
  gap: 12rpx;
  flex-shrink: 0;
}

.note-detail-scroll {
  flex: 1;
  min-height: 0;
}

.note-detail-loading {
  padding: 80rpx 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.note-detail-body {
  padding: 32rpx;
}

.note-detail-empty {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.35);
  font-style: italic;
}

.note-detail-attachments {
  margin-top: 40rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.note-detail-attach-item-wrap {
  margin-bottom: 12rpx;
}

.note-detail-attach-image {
  width: 100%;
  border-radius: 12rpx;
}

.note-detail-attach-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 12rpx;
}

.note-detail-attach-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.5;
  flex-shrink: 0;
}

.note-detail-attach-name {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.6);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-detail-time {
  display: block;
  margin-top: 32rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
}

/* Edit overlay styles */
.note-edit-title-input {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  flex-shrink: 0;
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.04);
  border: none;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 0 32rpx;
  box-sizing: border-box;
}

.note-edit-body {
  padding: 24rpx 32rpx;
}

.note-edit-textarea {
  width: 100%;
  min-height: 400rpx;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.7;
  background: transparent;
  border: none;
}

.note-edit-save-btn {
  padding: 12rpx 28rpx;
  background: rgba(59, 130, 246, 0.2);
  border: 1rpx solid rgba(59, 130, 246, 0.5);
  border-radius: 24rpx;
  flex-shrink: 0;
}

.note-edit-save-btn:active {
  background: rgba(59, 130, 246, 0.35);
}

.note-edit-save-text {
  font-size: 26rpx;
  color: #3b82f6;
}
</style>
