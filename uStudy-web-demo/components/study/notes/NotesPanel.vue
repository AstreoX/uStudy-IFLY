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
              <view class="note-card-actions" @click.stop>
                <view v-if="note.note_type !== 'interactive_html'" class="note-action-btn" @click.stop="startEditNote(note)">
                  <image class="note-action-icon" src="/static/icons/phosphor/regular/pencil-white.svg" mode="aspectFit" />
                </view>
                <view class="note-action-btn note-action-delete" @click.stop="confirmDeleteNote(note)">
                  <image class="note-action-icon" src="/static/icons/phosphor/regular/trash.svg" mode="aspectFit" />
                </view>
              </view>
              <view v-if="note.note_type === 'interactive_html'" class="note-card-artifact-badge">
                <text class="note-card-artifact-badge-text">互动演示</text>
              </view>
              <text class="note-card-title">{{ getNoteTitle(note) }}</text>
              <text class="note-card-preview">{{ note.note_type === 'interactive_html' ? '交互式 HTML 演示' : truncateContent(note.content) }}</text>
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
      <view v-else-if="viewMode === 'detail'" class="notes-detail-view">
        <view class="detail-header">
          <view class="detail-back-btn" @click="backToList">
            <image class="detail-back-icon" src="/static/icons/phosphor/regular/arrow-left-white.svg" mode="aspectFit" />
            <text class="detail-back-text">返回列表</text>
          </view>
          <view class="detail-header-actions">
            <view v-if="selectedNote && selectedNote.note_type !== 'interactive_html'" class="note-action-btn" @click="startEditNote(selectedNote)">
              <image class="note-action-icon" src="/static/icons/phosphor/regular/pencil-white.svg" mode="aspectFit" />
            </view>
            <view class="note-action-btn note-action-delete" @click="confirmDeleteNote(selectedNote)">
              <image class="note-action-icon" src="/static/icons/phosphor/regular/trash.svg" mode="aspectFit" />
            </view>
          </view>
        </view>

        <view v-if="detailLoading" class="notes-status">
          <text class="notes-status-text">加载中...</text>
        </view>

        <!-- Interactive HTML Artifact -->
        <template v-else-if="selectedNote && selectedNote.note_type === 'interactive_html'">
          <ArtifactRenderer
            :html="selectedNote.content"
            :title="getNoteTitle(selectedNote)"
            :metadata="selectedNote.metadata_"
          />
        </template>

        <!-- Normal note -->
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
              <view
                v-for="(att, idx) in selectedNote.attachments"
                :key="idx"
                class="detail-attach-item"
              >
                <image
                  v-if="att.mime_type && att.mime_type.startsWith('image/')"
                  :src="getFullAttachmentUrl(att.file_url)"
                  class="detail-attach-image"
                  mode="widthFix"
                  @click="previewAttachmentImage(att.file_url)"
                />
                <text v-else class="detail-attach-name">{{ getAttachmentDisplayName(att) }}</text>
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

      <!-- Edit View -->
      <view v-else-if="viewMode === 'edit'" class="notes-edit-view">
        <view class="detail-header">
          <view class="detail-back-btn" @click="cancelEdit">
            <image class="detail-back-icon" src="/static/icons/phosphor/regular/arrow-left-white.svg" mode="aspectFit" />
            <text class="detail-back-text">取消</text>
          </view>
          <view class="edit-save-btn" :class="{ 'edit-save-btn--saving': isSaving }" @click="saveEdit">
            {{ isSaving ? '保存中...' : '保存' }}
          </view>
        </view>
        <input
          class="edit-title-input"
          v-model="editTitle"
          type="text"
          placeholder="笔记标题"
          maxlength="200"
          placeholder-style="color: rgba(255,255,255,0.3)"
        />
        <scroll-view class="edit-scroll" scroll-y>
          <view class="edit-body">
            <textarea
              class="edit-content-input"
              v-model="editContent"
              placeholder="笔记内容（支持 Markdown）"
              placeholder-style="color: rgba(255,255,255,0.3)"
              auto-height
            />
          </view>
        </scroll-view>
      </view>
    </template>

    <!-- Delete Confirm Dialog -->
    <view v-if="deleteConfirm.visible" class="delete-confirm-overlay" @click.self="deleteConfirm.visible = false">
      <view class="delete-confirm-dialog">
        <text class="delete-confirm-title">删除笔记</text>
        <text class="delete-confirm-msg">确定要删除这条笔记吗？此操作无法撤销。</text>
        <view class="delete-confirm-actions">
          <view class="confirm-cancel-btn" @click="deleteConfirm.visible = false">取消</view>
          <view class="confirm-delete-btn" :class="{ 'confirm-delete-btn--loading': deleteConfirm.isDeleting }" @click="doDeleteNote">
            {{ deleteConfirm.isDeleting ? '删除中...' : '删除' }}
          </view>
        </view>
      </view>
    </view>

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
import ArtifactRenderer from './ArtifactRenderer.vue'
import { getSpaceNotes, getNoteDetail, updateNote, deleteNote } from '@/api/space'
import config from '@/config'

export default {
  name: 'NotesPanel',
  components: {
    UToast,
    MarkdownRender,
    ArtifactRenderer
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
      editTitle: '',
      editContent: '',
      editNoteId: null,
      isSaving: false,
      deleteConfirm: { visible: false, noteId: null, isDeleting: false },
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

    async openNoteById(noteId) {
      if (!noteId) return
      await this.openNoteDetail({ id: noteId })
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

    startEditNote(note) {
      if (!note?.id) return
      this.editNoteId = note.id
      this.editTitle = note.title || ''
      this.editContent = note.content || ''
      this.viewMode = 'edit'
    },

    cancelEdit() {
      this.viewMode = this.selectedNote ? 'detail' : 'list'
    },

    async saveEdit() {
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
          this.viewMode = 'detail'
        } else {
          this.viewMode = 'list'
        }
        this.showToast('已保存', 'success')
      } catch (e) {
        this.showToast(e?.message || '保存失败', 'error')
      } finally {
        this.isSaving = false
      }
    },

    confirmDeleteNote(note) {
      if (!note?.id) return
      this.deleteConfirm = { visible: true, noteId: note.id, isDeleting: false }
    },

    async doDeleteNote() {
      if (this.deleteConfirm.isDeleting) return
      this.deleteConfirm = { ...this.deleteConfirm, isDeleting: true }
      try {
        await deleteNote(this.spaceId, this.deleteConfirm.noteId)
        this.notes = this.notes.filter(n => n.id !== this.deleteConfirm.noteId)
        if (this.selectedNote?.id === this.deleteConfirm.noteId) {
          this.viewMode = 'list'
          this.selectedNote = null
        }
        this.showToast('已删除', 'success')
      } catch (e) {
        this.showToast(e?.message || '删除失败', 'error')
      } finally {
        this.deleteConfirm = { visible: false, noteId: null, isDeleting: false }
      }
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

    getFullAttachmentUrl(path) {
      if (!path) return ''
      if (/^https?:\/\//i.test(path)) return path
      return config.API_BASE_URL + path
    },

    previewAttachmentImage(fileUrl) {
      const fullUrl = this.getFullAttachmentUrl(fileUrl)
      if (fullUrl) {
        window.open(fullUrl, '_blank')
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
  min-height: 0;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
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
  position: relative;
}

.note-card:hover {
  background: rgba(255, 255, 255, 0.08);
}

.note-card-actions {
  position: absolute;
  top: 14rpx;
  right: 14rpx;
  display: flex;
  gap: 6rpx;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.note-card:hover .note-card-actions {
  opacity: 1;
}

@media (hover: none) {
  .note-card-actions {
    opacity: 1;
  }
}

.note-action-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  flex-shrink: 0;
}

.note-action-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.22);
}

.note-action-icon {
  width: 15px;
  height: 15px;
  filter: brightness(0) saturate(100%) invert(95%) sepia(2%) saturate(115%) hue-rotate(183deg) brightness(104%) contrast(100%);
}

.note-action-delete {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.2);
}

.note-action-delete:hover {
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(239, 68, 68, 0.35);
}

.note-action-delete .note-action-icon {
  filter: brightness(0) saturate(100%) invert(40%) sepia(100%) saturate(1500%) hue-rotate(330deg) brightness(140%) contrast(100%);
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
  padding-right: 90rpx;
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

.note-card-artifact-badge {
  display: inline-flex;
  align-self: flex-start;
  margin-bottom: 4rpx;
}
.note-card-artifact-badge-text {
  font-size: 20rpx;
  color: rgba(99, 102, 241, 0.9);
  padding: 3rpx 10rpx;
  background: rgba(99, 102, 241, 0.12);
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
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-header-actions {
  display: flex;
  gap: 10rpx;
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
  min-height: 0;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
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

.detail-attach-item {
  margin-bottom: 10rpx;
}

.detail-attach-image {
  width: 100%;
  border-radius: 8rpx;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.detail-attach-image:hover {
  opacity: 0.85;
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

/* Edit View */
.notes-edit-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.edit-save-btn {
  font-size: 26rpx;
  color: #0088FF;
  padding: 8rpx 20rpx;
  background: rgba(0, 136, 255, 0.12);
  border: 1rpx solid rgba(0, 136, 255, 0.3);
  border-radius: 10rpx;
  cursor: pointer;
  transition: background 0.15s ease;
}

.edit-save-btn:hover {
  background: rgba(0, 136, 255, 0.22);
}

.edit-save-btn--saving {
  opacity: 0.6;
  cursor: not-allowed;
}

.edit-scroll {
  flex: 1;
  width: 100%;
  min-height: 0;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
}

.edit-body {
  padding: 20px 24px;
}

.edit-title-input {
  width: 100%;
  height: 52px;
  line-height: 52px;
  flex-shrink: 0;
  font-size: 17px;
  font-weight: 600;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.04);
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0 24px;
  box-sizing: border-box;
  outline: none;
  cursor: text;
}

.edit-title-input:focus {
  border-bottom-color: rgba(59, 130, 246, 0.5);
  background: rgba(255, 255, 255, 0.06);
}

.edit-content-input {
  width: 100%;
  min-height: 400rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
  padding: 16rpx 20rpx;
  box-sizing: border-box;
  line-height: 1.7;
}

/* Delete Confirm Dialog */
.delete-confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.delete-confirm-dialog {
  background: #1a1f2e;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 20rpx;
  padding: 40rpx;
  width: 540rpx;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.delete-confirm-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
}

.delete-confirm-msg {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.6;
}

.delete-confirm-actions {
  display: flex;
  gap: 16rpx;
  justify-content: flex-end;
  margin-top: 10rpx;
}

.confirm-cancel-btn {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
  padding: 12rpx 30rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
  cursor: pointer;
  transition: background 0.15s ease;
}

.confirm-cancel-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.confirm-delete-btn {
  font-size: 26rpx;
  color: rgba(239, 68, 68, 0.95);
  padding: 12rpx 30rpx;
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
  border-radius: 12rpx;
  cursor: pointer;
  transition: background 0.15s ease;
}

.confirm-delete-btn:hover {
  background: rgba(239, 68, 68, 0.22);
}

.confirm-delete-btn--loading {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
