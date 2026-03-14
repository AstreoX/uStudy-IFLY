<template>
  <view class="notes-list-page">
    <!-- Background -->
    <view class="page-bg">
      <view class="bg-mesh"></view>
      <view class="bg-glow bg-glow-blue"></view>
      <view class="bg-glow bg-glow-violet"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-back" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <view class="nav-copy">
        <text class="nav-title">笔记管理</text>
        <text v-if="spaceName" class="nav-subtitle">{{ spaceName }}</text>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <!-- Loading State -->
    <view v-if="loading" class="state-container">
      <text class="state-text">正在加载笔记列表...</text>
    </view>

    <!-- Error State -->
    <view v-else-if="loadError" class="state-container">
      <image class="state-icon state-icon-error" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="state-text state-text-error">{{ loadError }}</text>
      <view class="retry-btn" @click="loadNotes">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- Empty State -->
    <view v-else-if="notes.length === 0" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook.svg" mode="aspectFit"></image>
      <text class="state-text">暂无笔记</text>
      <text class="state-sub">在与 AI 对话时可以让 AI 为你创建笔记</text>
    </view>

    <!-- Notes List -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="content-body">
        <!-- Search Bar -->
        <view class="search-bar">
          <image class="search-icon" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
          <input
            class="search-input"
            v-model="searchQuery"
            type="text"
            placeholder="搜索笔记..."
            placeholder-style="color: #7C8598"
          />
        </view>

        <!-- No search results -->
        <view v-if="filteredNotes.length === 0" class="no-results">
          <text class="state-text">没有匹配的笔记</text>
        </view>

        <!-- Notes -->
        <view v-else class="list-section">
          <text class="section-caption">{{ filteredNotes.length }} 条笔记</text>
          <view
            v-for="note in filteredNotes"
            :key="note.id"
            class="note-item"
            @click="handleNoteClick(note)"
          >
            <view class="note-main">
              <view class="note-info">
                <view class="note-title-row">
                  <text class="note-title">{{ getNoteTitle(note) }}</text>
                  <text v-if="note.note_type === 'interactive_html'" class="note-type-badge">互动</text>
                </view>
                <text class="note-preview">{{ note.note_type === 'interactive_html' ? '点击查看互动演示' : truncateContent(note.content) }}</text>
                <view class="note-meta">
                  <text class="note-date">{{ formatDate(note.created_at) }}</text>
                  <text v-if="getNoteNodeTag(note)" class="note-node-tag">{{ getNoteNodeTag(note) }}</text>
                  <text v-if="getNoteAttachmentCount(note) > 0" class="note-attach-badge">{{ getNoteAttachmentCount(note) }} 附件</text>
                  <view v-if="isCollaborative && note.creator_nickname" class="note-creator-inline">
                    <view class="note-creator-dot" :style="{ backgroundColor: getCreatorColor(note.creator_user_id) }"></view>
                    <text class="note-creator-name">{{ note.creator_nickname }}</text>
                  </view>
                </view>
              </view>
              <view class="note-item-actions" @click.stop>
                <view v-if="note.note_type !== 'interactive_html' && canEditNote(note)" class="note-item-btn" @click.stop="startEditNote(note)">
                  <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
                </view>
                <view v-if="canEditNote(note)" class="note-item-btn note-item-btn-delete" @click.stop="showDeleteConfirm(note)">
                  <image class="note-item-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit" />
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- Note Detail Overlay -->
    <view v-if="showNoteDetail" class="note-detail-overlay" @click="closeNoteDetail">
      <view class="overlay-bg">
        <view class="bg-mesh"></view>
        <view class="bg-glow bg-glow-blue"></view>
        <view class="bg-glow bg-glow-violet"></view>
      </view>
      <view class="note-detail-card" @click.stop>
        <!-- Nav Bar -->
        <view class="detail-nav" @touchmove.prevent>
          <view class="detail-nav-left">
            <view class="detail-circle-btn" @click="closeNoteDetail">
              <image class="detail-circle-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
            </view>
            <view class="detail-title-wrap">
              <text class="detail-title-main">笔记详情</text>
              <text v-if="selectedNote && selectedNote.node_label" class="detail-title-sub">{{ selectedNote.node_label }}</text>
            </view>
          </view>
          <view v-if="(!selectedNote || selectedNote.note_type !== 'interactive_html') && canEditNote(selectedNote)" class="detail-circle-btn" @click="startEditNote(selectedNote)">
            <image class="detail-circle-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit"></image>
          </view>
        </view>
        <!-- Content -->
        <scroll-view class="detail-scroll" scroll-y>
          <view v-if="detailLoading" class="note-detail-loading">
            <text class="state-text">加载中...</text>
          </view>
          <view v-else-if="selectedNote" class="detail-content-area">
            <view class="detail-note-card">
              <!-- Title -->
              <text class="detail-note-title">{{ getNoteTitle(selectedNote) }}</text>
              <!-- Node Tag -->
              <view v-if="selectedNote.node_label" class="detail-meta-row">
                <view class="detail-node-tag">
                  <image class="detail-node-icon" src="/static/icons/phosphor-icons/SVGs/regular/git-branch.svg" mode="aspectFit"></image>
                  <text class="detail-node-text">{{ selectedNote.node_label }}</text>
                </view>
              </view>
              <!-- Divider -->
              <view class="detail-divider"></view>
              <!-- Artifact action -->
              <view v-if="selectedNote.note_type === 'interactive_html'" class="artifact-action-bar">
                <view class="artifact-view-btn" @click="openArtifactViewer(selectedNote)">
                  <image class="artifact-view-icon" src="/static/icons/phosphor-icons/SVGs/regular/code.svg" mode="aspectFit" />
                  <text class="artifact-view-text">查看演示</text>
                </view>
              </view>
              <!-- Markdown Content -->
              <view class="detail-markdown-wrap">
                <markdown-render v-if="selectedNote.content" :content="selectedNote.content" />
                <text v-else class="detail-empty-text">（无内容）</text>
              </view>
              <!-- Attachments -->
              <view v-if="selectedNote.attachments && selectedNote.attachments.length" class="detail-attachments">
                <view class="detail-divider"></view>
                <view
                  v-for="(att, idx) in selectedNote.attachments"
                  :key="idx"
                  class="detail-attach-wrap"
                >
                  <image
                    v-if="att.mime_type && att.mime_type.startsWith('image/')"
                    :src="getFullAttachmentUrl(att.file_url)"
                    class="detail-attach-image"
                    mode="widthFix"
                    @click="previewAttachmentImage(att.file_url)"
                  />
                  <view v-else class="detail-attach-file">
                    <image class="detail-attach-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file.svg" mode="aspectFit"></image>
                    <text class="detail-attach-file-name">{{ getAttachmentDisplayName(att) }}</text>
                  </view>
                </view>
              </view>
              <!-- Time -->
              <text class="detail-time">创建于 {{ formatDate(selectedNote.created_at) }}</text>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- Note Edit Overlay -->
    <view v-if="showNoteEdit" class="note-edit-overlay">
      <view class="overlay-bg">
        <view class="bg-mesh"></view>
        <view class="bg-glow bg-glow-blue"></view>
        <view class="bg-glow bg-glow-violet"></view>
      </view>
      <view class="note-edit-card">
        <!-- Nav Bar -->
        <view class="edit-nav" @touchmove.prevent>
          <view class="detail-nav-left">
            <view class="detail-circle-btn" @click="closeNoteEdit">
              <image class="detail-circle-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
            </view>
            <view class="detail-title-wrap">
              <text class="detail-title-main">编辑笔记</text>
              <text v-if="editingNodeLabel" class="detail-title-sub">{{ editingNodeLabel }}</text>
            </view>
          </view>
          <view class="edit-nav-right">
            <view v-if="canEditNote(editingNote)" class="detail-circle-btn edit-delete-btn" @click="showDeleteConfirm(editingNote)">
              <image class="edit-delete-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
            </view>
            <view class="edit-save-pill" @click="saveNoteEdit">
              <image class="edit-save-icon" src="/static/icons/lucide/save.svg" mode="aspectFit"></image>
              <text class="edit-save-text">{{ isSaving ? '保存中...' : '保存' }}</text>
            </view>
          </view>
        </view>
        <!-- Form Sections -->
        <view class="edit-scroll" style="overflow-y: auto;">
          <view class="edit-form">
            <!-- Node Section -->
            <view class="edit-section">
              <text class="edit-label">关联知识节点</text>
              <view class="edit-node-selector" @click="openNodePicker">
                <view class="edit-node-left">
                  <image class="edit-node-icon" src="/static/icons/phosphor-icons/SVGs/regular/git-branch.svg" mode="aspectFit"></image>
                  <text class="edit-node-text">{{ editingNodeLabel || '未关联' }}</text>
                </view>
                <image class="edit-node-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit"></image>
              </view>
            </view>
            <!-- Title Section -->
            <view class="edit-section">
              <text class="edit-label">笔记标题</text>
              <input
                class="edit-title-input"
                v-model="editTitle"
                type="text"
                placeholder="输入笔记标题"
                maxlength="200"
                placeholder-style="color: #5C5B59"
              />
            </view>
            <!-- Content Section -->
            <view class="edit-section edit-section-fill">
              <view class="edit-content-header">
                <text class="edit-label">笔记内容</text>
                <view class="edit-toggle-wrap">
                  <view
                    class="edit-toggle-tab"
                    :class="{ 'edit-toggle-active': editPreviewMode === 'source' }"
                    @click="toggleEditPreview('source')"
                  >
                    <image class="edit-toggle-icon" :class="{ 'edit-toggle-icon-active': editPreviewMode === 'source' }" src="/static/icons/phosphor-icons/SVGs/regular/code.svg" mode="aspectFit"></image>
                    <text class="edit-toggle-text" :class="{ 'edit-toggle-text-active': editPreviewMode === 'source' }">源码</text>
                  </view>
                  <view
                    class="edit-toggle-tab"
                    :class="{ 'edit-toggle-active': editPreviewMode === 'preview' }"
                    @click="toggleEditPreview('preview')"
                  >
                    <image class="edit-toggle-icon" :class="{ 'edit-toggle-icon-active': editPreviewMode === 'preview' }" src="/static/icons/phosphor-icons/SVGs/regular/eye.svg" mode="aspectFit"></image>
                    <text class="edit-toggle-text" :class="{ 'edit-toggle-text-active': editPreviewMode === 'preview' }">渲染</text>
                  </view>
                </view>
              </view>
              <view class="edit-content-box">
                <textarea
                  v-if="editPreviewMode === 'source'"
                  class="edit-textarea"
                  v-model="editContent"
                  placeholder="笔记内容（支持 Markdown）"
                  placeholder-style="color: #5C5B59"
                  auto-height
                />
                <view v-else class="edit-preview-wrap">
                  <markdown-render v-if="editContent" :content="editContent" />
                  <text v-else class="detail-empty-text">（暂无内容）</text>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Node Picker Popup -->
    <view v-if="showNodePicker" class="node-picker-mask" @click="showNodePicker = false">
      <view class="node-picker-popup" @click.stop>
        <view class="node-picker-header">
          <text class="node-picker-title">选择知识节点</text>
          <view class="node-picker-close" @click="showNodePicker = false">
            <image class="node-picker-close-icon" src="/static/icons/phosphor-icons/SVGs/regular/x.svg" mode="aspectFit"></image>
          </view>
        </view>
        <view v-if="loadingNodes" class="node-picker-loading">
          <text class="node-picker-loading-text">加载中...</text>
        </view>
        <scroll-view v-else class="node-picker-list" scroll-y>
          <!-- Unlink option -->
          <view
            class="node-picker-item"
            :class="{ 'node-picker-item-active': !editingNodeId }"
            @click="selectNode(null, '')"
          >
            <text class="node-picker-item-text">未关联（自由笔记）</text>
            <image v-if="!editingNodeId" class="node-picker-check" src="/static/icons/phosphor-icons/SVGs/regular/check.svg" mode="aspectFit"></image>
          </view>
          <!-- Node list -->
          <view
            v-for="node in graphNodes"
            :key="node.id"
            class="node-picker-item"
            :class="{ 'node-picker-item-active': editingNodeId === node.id }"
            @click="selectNode(node.id, node.label)"
          >
            <text class="node-picker-item-text">{{ node.label }}</text>
            <image v-if="editingNodeId === node.id" class="node-picker-check" src="/static/icons/phosphor-icons/SVGs/regular/check.svg" mode="aspectFit"></image>
          </view>
          <view v-if="graphNodes.length === 0" class="node-picker-empty">
            <text class="node-picker-empty-text">暂无知识节点</text>
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
import { getSpace, getSpaceMembers, getSpaceGraph } from '@/api/space'
import { useUserStore } from '@/store/user'
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
      searchQuery: '',
      isCollaborative: false,
      userRole: '',
      currentUserId: '',
      spaceMembers: [],
      showNoteDetail: false,
      selectedNote: null,
      detailLoading: false,
      showNoteEdit: false,
      editNoteId: null,
      editTitle: '',
      editContent: '',
      editingNodeLabel: '',
      editingNodeId: null,
      editingNote: null,
      showNodePicker: false,
      graphNodes: [],
      loadingNodes: false,
      editPreviewMode: 'source',
      isSaving: false,
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
    },

    filteredNotes() {
      if (!this.searchQuery.trim()) return this.notes
      const q = this.searchQuery.trim().toLowerCase()
      return this.notes.filter(note => {
        const title = (note.title || '').toLowerCase()
        const content = (note.content || '').toLowerCase()
        const nodeLabel = (note.node_label || '').toLowerCase()
        return title.includes(q) || content.includes(q) || nodeLabel.includes(q)
      })
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    this.pendingOpenNoteId = options.openNoteId || ''
    this.currentUserId = useUserStore().user?.id || ''
    this.loadCollaborationContext()
    this.loadNotes()
  },

  onShow() {
    this.loadCollaborationContext()
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

    async loadCollaborationContext() {
      if (!this.spaceId) return
      try {
        const space = await getSpace(this.spaceId)
        this.isCollaborative = !!space?.is_collaborative
        this.userRole = space?.user_role || ''
        if (!this.isCollaborative) {
          this.spaceMembers = []
          return
        }
        const members = await getSpaceMembers(this.spaceId)
        this.spaceMembers = members?.data || members || []
      } catch (error) {
        this.isCollaborative = false
        this.userRole = ''
        this.spaceMembers = []
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
        if (this.pendingOpenNoteId) {
          const targetId = this.pendingOpenNoteId
          this.pendingOpenNoteId = ''
          const target = this.notes.find(n => String(n.id) === String(targetId))
          if (target) {
            this.$nextTick(() => this.handleNoteClick(target))
          }
        }
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

    canEditNote(note) {
      if (!note) return false
      if (!this.isCollaborative) return true
      if (this.userRole === 'owner') return true
      return String(note.creator_user_id || '') === String(this.currentUserId || '')
    },

    getCreatorColor(creatorUserId) {
      if (!creatorUserId) return '#666666'
      const member = this.spaceMembers.find(item => String(item.user_id) === String(creatorUserId))
      return member?.color || '#666666'
    },

    openArtifactViewer(note) {
      if (!note?.id) return
      uni.navigateTo({
        url: `/pages/artifactViewer/artifactViewer?spaceId=${this.spaceId}&noteId=${note.id}`
      })
    },

    async handleNoteClick(note) {
      if (!note?.id) return
      if (note.note_type === 'interactive_html') {
        this.openArtifactViewer(note)
        return
      }
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

    startEditNote(note) {
      if (!note || !this.canEditNote(note)) return
      this.editNoteId = note.id
      this.editTitle = note.title || ''
      this.editContent = note.content || ''
      this.editingNodeLabel = note.node_label || ''
      this.editingNodeId = note.node_id || null
      this.editingNote = note
      this.editPreviewMode = 'source'
      this.showNoteEdit = true
    },

    closeNoteEdit() {
      this.showNoteEdit = false
      this.editingNote = null
    },

    toggleEditPreview(mode) {
      this.editPreviewMode = mode
    },

    async openNodePicker() {
      this.showNodePicker = true
      if (this.graphNodes.length > 0) return
      this.loadingNodes = true
      try {
        const graph = await getSpaceGraph(this.spaceId)
        this.graphNodes = (graph.nodes || []).map(n => ({
          id: n.id,
          label: n.label || n.name || ''
        }))
      } catch (e) {
        this.showCustomToast('加载节点失败', 'error')
      } finally {
        this.loadingNodes = false
      }
    },

    selectNode(nodeId, nodeLabel) {
      this.editingNodeId = nodeId
      this.editingNodeLabel = nodeLabel
      this.showNodePicker = false
    },

    async saveNoteEdit() {
      if (this.isSaving) return
      this.isSaving = true
      try {
        const updateData = {
          title: this.editTitle,
          content: this.editContent,
          node_id: this.editingNodeId || null
        }
        await updateNote(this.spaceId, this.editNoteId, updateData)
        const updatedFields = {
          title: this.editTitle,
          content: this.editContent,
          node_id: this.editingNodeId || null,
          node_label: this.editingNodeLabel || ''
        }
        const idx = this.notes.findIndex(n => n.id === this.editNoteId)
        if (idx !== -1) {
          this.notes.splice(idx, 1, { ...this.notes[idx], ...updatedFields })
        }
        if (this.selectedNote?.id === this.editNoteId) {
          this.selectedNote = { ...this.selectedNote, ...updatedFields }
        }
        this.showNoteEdit = false
        this.showCustomToast('已保存', 'success')
      } catch (e) {
        this.showCustomToast(e?.message || '保存失败', 'error')
      } finally {
        this.isSaving = false
      }
    },

    showDeleteConfirm(note) {
      if (!note || !this.canEditNote(note)) return
      this.noteToDelete = note
      this.showDeleteModal = true
    },

    async doDeleteNote() {
      if (this.isDeleting || !this.noteToDelete) return
      if (!this.canEditNote(this.noteToDelete)) {
        this.showCustomToast('当前仅可编辑或删除自己的笔记', 'error')
        return
      }
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
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: rgb(29, 30, 32);
  overflow-x: hidden;
}

/* ========== Background ========== */
.page-bg {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  pointer-events: none;
}

.bg-mesh {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background:
    radial-gradient(circle at 82% 14%, rgba(74, 108, 247, 0.07) 0%, rgba(74, 108, 247, 0) 32%),
    radial-gradient(circle at 12% 100%, rgba(99, 102, 241, 0.04) 0%, rgba(99, 102, 241, 0) 36%);
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(130rpx);
  opacity: 0.2;
}

.bg-glow-blue {
  top: 120rpx;
  right: -90rpx;
  width: 320rpx;
  height: 320rpx;
  background: rgba(74, 108, 247, 0.10);
}

.bg-glow-violet {
  bottom: 180rpx;
  left: -90rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(123, 97, 255, 0.07);
}

/* ========== Navigation Bar ========== */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: calc(100vh * 0.5 / 26);
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
    rgba(29, 30, 32, 0.56) 0%,
    rgba(29, 30, 32, 0.4) 50%,
    rgba(29, 30, 32, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(29, 30, 32, 0.82) 0%,
      rgba(29, 30, 32, 0.66) 50%,
      rgba(29, 30, 32, 0) 100%
    );
  }
}

.nav-back {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-back {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-back:active {
  background: rgba(255, 255, 255, 0.10);
}

.nav-copy {
  flex: 1;
  min-width: 0;
  margin-left: 16rpx;
  margin-right: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 4rpx;
}

.nav-spacer {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.2;
}

.nav-subtitle {
  max-width: 100%;
  font-size: 22rpx;
  line-height: 1.25;
  color: rgba(248, 248, 248, 0.52);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== States ========== */
.state-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
}

.state-icon {
  width: 100rpx;
  height: 100rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  margin-bottom: 32rpx;
}

.state-icon-error {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  opacity: 1;
}

.state-text {
  font-size: 28rpx;
  color: #7C8598;
}

.state-text-error {
  color: rgba(239, 68, 68, 0.9);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 500rpx;
  line-height: 1.5;
}

.state-sub {
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.35);
  margin-top: 12rpx;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(74, 108, 247, 0.15);
  border: 1rpx solid rgba(74, 108, 247, 0.4);
  border-radius: 40rpx;
}

.retry-btn:active {
  background: rgba(74, 108, 247, 0.25);
}

.retry-btn-text {
  font-size: 28rpx;
  color: #4A6CF7;
}

/* ========== Content Scroll ========== */
.content-scroll {
  position: relative;
  z-index: 1;
  height: 100vh;
}

.content-body {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
  padding:
    calc(100vh * 4.2 / 26)
    calc(100vw / 24)
    calc(env(safe-area-inset-bottom) + 42rpx);
}

/* ========== Search Bar ========== */
.search-bar {
  display: flex;
  align-items: center;
  gap: 14rpx;
  height: 80rpx;
  padding: 0 24rpx;
  border-radius: 36rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
}

.search-icon {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(1);
  opacity: 0.35;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
  color: rgb(248, 248, 248);
  background: transparent;
  border: none;
}

/* ========== No Results ========== */
.no-results {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 80rpx 0;
}

/* ========== List Section ========== */
.list-section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.section-caption {
  padding-left: 6rpx;
  margin-bottom: 4rpx;
  font-size: 22rpx;
  letter-spacing: 1rpx;
  color: rgba(248, 248, 248, 0.52);
}

/* ========== Note Item ========== */
.note-item {
  padding: 24rpx 28rpx;
  border-radius: 36rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.note-item:active {
  background: rgb(41, 41, 41);
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

.note-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 10rpx;
}

.note-title {
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.note-type-badge {
  font-size: 20rpx;
  color: rgba(99, 102, 241, 0.9);
  padding: 4rpx 14rpx;
  background: rgba(99, 102, 241, 0.12);
  border: 1rpx solid rgba(99, 102, 241, 0.25);
  border-radius: 8rpx;
  flex-shrink: 0;
  white-space: nowrap;
}

.note-preview {
  font-size: 26rpx;
  color: #7C8598;
  margin-bottom: 14rpx;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.note-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.note-date {
  font-size: 22rpx;
  color: rgba(248, 248, 248, 0.35);
}

.note-node-tag {
  font-size: 20rpx;
  color: rgba(129, 140, 248, 0.9);
  padding: 4rpx 14rpx;
  background: rgba(129, 140, 248, 0.12);
  border: 1rpx solid rgba(129, 140, 248, 0.2);
  border-radius: 8rpx;
}

.note-attach-badge {
  font-size: 20rpx;
  color: rgba(34, 197, 94, 0.9);
  padding: 4rpx 14rpx;
  background: rgba(34, 197, 94, 0.12);
  border: 1rpx solid rgba(34, 197, 94, 0.2);
  border-radius: 8rpx;
}

.note-creator-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.note-creator-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.note-creator-name {
  font-size: 22rpx;
  color: rgba(248, 248, 248, 0.42);
}

/* ========== Card Action Buttons ========== */
.note-item-actions {
  display: flex;
  flex-direction: row;
  gap: 12rpx;
  flex-shrink: 0;
  margin-left: 16rpx;
  align-items: flex-start;
}

.note-item-btn {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
}

.note-item-btn:active {
  background: rgba(255, 255, 255, 0.12);
}

.note-item-btn-icon {
  width: 30rpx;
  height: 30rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

.note-item-btn-delete {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
}

.note-item-btn-delete:active {
  background: rgba(239, 68, 68, 0.25);
}

.note-item-btn-delete .note-item-btn-icon {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  opacity: 0.85;
}

/* ========== Shared Overlay Base ========== */
.note-detail-overlay,
.note-edit-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background-color: rgb(29, 30, 32);
}

.note-detail-overlay {
  z-index: 600;
}

.note-edit-overlay {
  z-index: 700;
}

.overlay-bg {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  pointer-events: none;
}

.note-detail-card,
.note-edit-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* ========== Shared Nav Elements ========== */
.detail-nav,
.edit-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: calc(100vh * 0.5 / 26);
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.detail-nav-left {
  display: flex;
  align-items: center;
  gap: 24rpx;
  flex: 1;
  min-width: 0;
}

.detail-circle-btn {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
  flex-shrink: 0;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .detail-circle-btn {
    background: rgba(80, 80, 95, 0.65);
  }
}

.detail-circle-btn:active {
  background: rgba(255, 255, 255, 0.10);
}

.detail-circle-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
}

.detail-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  flex: 1;
  min-width: 0;
}

.detail-title-main {
  font-size: 34rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.2;
}

.detail-title-sub {
  font-size: 22rpx;
  font-weight: 500;
  color: rgba(248, 248, 248, 0.52);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== Note Detail — Content ========== */
.detail-scroll {
  flex: 1;
  min-height: 0;
}

.note-detail-loading {
  padding: 80rpx 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.detail-content-area {
  padding: 0 40rpx 40rpx 40rpx;
}

.detail-note-card {
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
  border-radius: 32rpx;
  padding: 40rpx;
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}

.detail-note-title {
  font-size: 40rpx;
  font-weight: 700;
  color: rgb(248, 248, 248);
  letter-spacing: -0.6rpx;
  line-height: 1.3;
}

.detail-meta-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
}

.detail-node-tag {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 12rpx 24rpx;
  background: rgba(74, 108, 247, 0.12);
  border-radius: 16rpx;
}

.detail-node-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) saturate(100%) invert(42%) sepia(93%) saturate(1352%) hue-rotate(215deg) brightness(100%) contrast(95%);
}

.detail-node-text {
  font-size: 26rpx;
  font-weight: 500;
  color: #6B8AFF;
}

.detail-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.06);
}

.detail-markdown-wrap {
  /* markdown content container */
}

.detail-empty-text {
  font-size: 28rpx;
  color: #7C8598;
  font-style: italic;
}

.detail-attachments {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.detail-attach-wrap {
  /* individual attachment wrapper */
}

.detail-attach-image {
  width: 100%;
  border-radius: 16rpx;
}

.detail-attach-file {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx 24rpx;
  background: rgb(36, 36, 36);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
}

.detail-attach-file-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.5;
  flex-shrink: 0;
}

.detail-attach-file-name {
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.6);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-time {
  font-size: 22rpx;
  color: rgba(248, 248, 248, 0.3);
}

/* ========== Note Edit — Nav Right ========== */
.edit-nav-right {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex-shrink: 0;
}

.edit-delete-btn {
  /* inherits detail-circle-btn */
}

.edit-delete-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) saturate(100%) invert(49%) sepia(40%) saturate(700%) hue-rotate(335deg) brightness(90%) contrast(92%);
}

.edit-save-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 32rpx;
  background: #4A6CF7;
  border-radius: 100rpx;
}

.edit-save-pill:active {
  background: #3D5BD9;
}

.edit-save-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
}

.edit-save-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #FFFFFF;
}

/* ========== Note Edit — Form ========== */
.edit-scroll {
  flex: 1;
  min-height: 0;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 32rpx;
  padding: 0 40rpx 40rpx 40rpx;
  min-height: calc(100vh - 200rpx);
}

.edit-section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.edit-section-fill {
  flex: 1;
  min-height: 0;
}

.edit-label {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(248, 248, 248, 0.52);
}

/* Node Selector */
.edit-node-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 28rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 24rpx;
}

.edit-node-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.edit-node-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) saturate(100%) invert(42%) sepia(93%) saturate(1352%) hue-rotate(215deg) brightness(100%) contrast(95%);
  flex-shrink: 0;
}

.edit-node-text {
  font-size: 28rpx;
  font-weight: 500;
  color: rgb(248, 248, 248);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edit-node-chevron {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.35;
  flex-shrink: 0;
}

/* Title Input */
.edit-title-input {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  padding: 0 28rpx;
  font-size: 30rpx;
  font-weight: 500;
  color: rgb(248, 248, 248);
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 24rpx;
  box-sizing: border-box;
}

/* Content Header with Toggle */
.edit-content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.edit-toggle-wrap {
  display: flex;
  gap: 4rpx;
  padding: 4rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
}

.edit-toggle-tab {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 12rpx 24rpx;
  border-radius: 12rpx;
}

.edit-toggle-active {
  background: #4A6CF7;
}

.edit-toggle-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.35;
}

.edit-toggle-icon-active {
  opacity: 1;
}

.edit-toggle-text {
  font-size: 24rpx;
  font-weight: 500;
  color: rgba(248, 248, 248, 0.52);
}

.edit-toggle-text-active {
  font-weight: 600;
  color: #FFFFFF;
}

/* Content Box */
.edit-content-box {
  flex: 1;
  min-height: 400rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 24rpx;
  padding: 28rpx;
}

.edit-textarea {
  width: 100%;
  min-height: 360rpx;
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.85);
  line-height: 1.7;
  background: transparent;
  border: none;
}

.edit-preview-wrap {
  /* rendered markdown preview inside edit */
}

/* ========== Artifact Action Bar ========== */
.artifact-action-bar {
  margin-bottom: 0;
}

.artifact-view-btn {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  padding: 16rpx 28rpx;
  background: rgba(99, 102, 241, 0.12);
  border: 1rpx solid rgba(99, 102, 241, 0.3);
  border-radius: 20rpx;
}

.artifact-view-btn:active {
  background: rgba(99, 102, 241, 0.25);
}

.artifact-view-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.8;
}

.artifact-view-text {
  font-size: 26rpx;
  color: rgba(138, 180, 248, 0.9);
}

/* ========== Node Picker ========== */
.node-picker-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 800;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.node-picker-popup {
  width: 100%;
  max-height: 70vh;
  background: rgb(36, 36, 36);
  border-top-left-radius: 32rpx;
  border-top-right-radius: 32rpx;
  display: flex;
  flex-direction: column;
}

.node-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx 40rpx 24rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}

.node-picker-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

.node-picker-close {
  width: 60rpx;
  height: 60rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
}

.node-picker-close-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

.node-picker-loading {
  padding: 60rpx 0;
  display: flex;
  justify-content: center;
}

.node-picker-loading-text {
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.45);
}

.node-picker-list {
  flex: 1;
  min-height: 0;
  max-height: 60vh;
  padding-bottom: env(safe-area-inset-bottom, 0);
}

.node-picker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 40rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.04);
}

.node-picker-item:active {
  background: rgba(255, 255, 255, 0.06);
}

.node-picker-item-active {
  background: rgba(74, 108, 247, 0.12);
}

.node-picker-item-text {
  font-size: 30rpx;
  color: rgb(248, 248, 248);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-picker-check {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) saturate(100%) invert(42%) sepia(93%) saturate(1352%) hue-rotate(215deg) brightness(100%) contrast(95%);
  flex-shrink: 0;
  margin-left: 16rpx;
}

.node-picker-empty {
  padding: 60rpx 0;
  display: flex;
  justify-content: center;
}

.node-picker-empty-text {
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.35);
}
</style>
