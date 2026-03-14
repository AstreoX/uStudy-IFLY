<template>
  <view class="ncc-card">
    <!-- ======== 待确认预览模式 ======== -->
    <template v-if="isPending && !isPendingEditing">
      <!-- Header -->
      <view class="ncc-card-header">
        <view class="ncc-icon-wrap">
          <image class="ncc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
        </view>
        <view class="ncc-title-col">
          <text class="ncc-note-title">{{ displayTitle }}</text>
          <text class="ncc-note-meta">{{ contentMeta }}</text>
        </view>
        <view class="ncc-edit-trigger" @click="enterPendingEdit">
          <image class="ncc-edit-trigger-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
          <text class="ncc-edit-trigger-text">编辑</text>
        </view>
      </view>
      <!-- 分割线 -->
      <view class="ncc-divider"></view>
      <!-- 内容预览 -->
      <view class="ncc-content-preview">
        <MarkdownRender :content="displayContent" />
      </view>
      <!-- 关联知识节点 -->
      <view v-if="nodeLabel" class="ncc-nodes-section">
        <text class="ncc-nodes-label">关联知识节点</text>
        <view class="ncc-nodes-row">
          <view class="ncc-node-pill">
            <text class="ncc-node-pill-text">{{ nodeLabel }}</text>
          </view>
        </view>
      </view>
      <!-- 操作按钮 -->
      <view class="ncc-btns-row">
        <view class="ncc-reject-btn" :class="{ 'ncc-btn-disabled': isSubmitting }" @click="handleCancel">
          <text class="ncc-reject-btn-text">拒绝</text>
        </view>
        <view class="ncc-confirm-btn" :class="{ 'ncc-btn-disabled': isSubmitting }" @click="handleConfirm">
          <text class="ncc-confirm-btn-text">{{ isSubmitting ? '提交中…' : '确认创建' }}</text>
        </view>
      </view>
      <text v-if="submitError" class="ncc-error-text">{{ submitError }}</text>
    </template>

    <!-- ======== 待确认编辑模式 ======== -->
    <template v-else-if="isPending && isPendingEditing">
      <!-- 节点选择 -->
      <view class="ncc-field-row">
        <text class="ncc-field-label">挂载节点</text>
        <picker mode="selector" :range="nodeOptionLabels" :value="selectedNodeIndex" @change="onNodePickerChange">
          <view class="ncc-node-picker">
            <text class="ncc-node-picker-text">{{ currentNodeLabel }}</text>
            <image class="ncc-node-picker-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
          </view>
        </picker>
      </view>
      <!-- 标题 -->
      <input class="ncc-title-input" v-model="editTitle" placeholder="笔记标题" maxlength="200" />
      <!-- 内容编辑区 -->
      <view class="ncc-edit-area">
        <view class="ncc-edit-toolbar">
          <view class="ncc-tab-group">
            <text class="ncc-tab" :class="{ 'ncc-tab-active': editMode === 'code' }" @click="editMode = 'code'">编辑</text>
            <text class="ncc-tab" :class="{ 'ncc-tab-active': editMode === 'preview' }" @click="editMode = 'preview'">预览</text>
          </view>
        </view>
        <textarea v-if="editMode === 'code'" class="ncc-textarea" v-model="editContent" placeholder="笔记内容 (Markdown)" :auto-height="false"></textarea>
        <view v-else class="ncc-preview-wrap"><MarkdownRender :content="editContent" /></view>
      </view>
      <!-- 按钮 -->
      <view class="ncc-btns-row">
        <view class="ncc-reject-btn" @click="exitPendingEdit">
          <text class="ncc-reject-btn-text">返回预览</text>
        </view>
        <view class="ncc-reject-btn" :class="{ 'ncc-btn-disabled': isSubmitting }" @click="handleCancel">
          <text class="ncc-reject-btn-text">拒绝</text>
        </view>
        <view class="ncc-confirm-btn" :class="{ 'ncc-btn-disabled': isSubmitting }" @click="handleConfirm">
          <text class="ncc-confirm-btn-text">{{ isSubmitting ? '提交中…' : '确认创建' }}</text>
        </view>
      </view>
      <text v-if="submitError" class="ncc-error-text">{{ submitError }}</text>
    </template>

    <!-- ======== Running 状态 ======== -->
    <template v-else-if="toolCall.status === 'running'">
      <view class="ncc-card-header">
        <view class="ncc-icon-wrap">
          <image class="ncc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
        </view>
        <view class="ncc-title-col">
          <text class="ncc-note-title">{{ displayTitle }}</text>
          <text class="ncc-note-meta ncc-loading-text">正在创建笔记…</text>
        </view>
      </view>
    </template>

    <!-- ======== Done 查看模式 ======== -->
    <template v-else-if="!isEditing">
      <view class="ncc-card-header">
        <view class="ncc-icon-wrap">
          <image class="ncc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
        </view>
        <view class="ncc-title-col">
          <text class="ncc-note-title">{{ displayTitle }}</text>
          <text class="ncc-note-meta">{{ contentMeta }}</text>
        </view>
        <view v-if="canEdit" class="ncc-edit-trigger" @click="enterEditMode">
          <image class="ncc-edit-trigger-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
          <text class="ncc-edit-trigger-text">编辑</text>
        </view>
      </view>
      <view class="ncc-divider"></view>
      <view class="ncc-content-preview">
        <MarkdownRender :content="displayContent" />
      </view>
      <view v-if="nodeLabel" class="ncc-nodes-section">
        <text class="ncc-nodes-label">关联知识节点</text>
        <view class="ncc-nodes-row">
          <view class="ncc-node-pill">
            <text class="ncc-node-pill-text">{{ nodeLabel }}</text>
          </view>
        </view>
      </view>
    </template>

    <!-- ======== Post-creation 编辑模式 ======== -->
    <template v-else>
      <view class="ncc-card-header">
        <view class="ncc-icon-wrap">
          <image class="ncc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
        </view>
        <view class="ncc-title-col">
          <text class="ncc-note-title">编辑笔记</text>
        </view>
      </view>
      <view class="ncc-divider"></view>
      <input class="ncc-title-input" v-model="editTitle" placeholder="笔记标题" maxlength="200" />
      <view class="ncc-edit-area">
        <view class="ncc-edit-toolbar">
          <view class="ncc-tab-group">
            <text class="ncc-tab" :class="{ 'ncc-tab-active': editMode === 'code' }" @click="editMode = 'code'">编辑</text>
            <text class="ncc-tab" :class="{ 'ncc-tab-active': editMode === 'preview' }" @click="editMode = 'preview'">预览</text>
          </view>
        </view>
        <textarea v-if="editMode === 'code'" class="ncc-textarea" v-model="editContent" placeholder="笔记内容 (Markdown)" :auto-height="false"></textarea>
        <view v-else class="ncc-preview-wrap"><MarkdownRender :content="editContent" /></view>
      </view>
      <view class="ncc-btns-row">
        <view class="ncc-reject-btn" :class="{ 'ncc-btn-disabled': isSaving }" @click="cancelEdit">
          <text class="ncc-reject-btn-text">取消</text>
        </view>
        <view class="ncc-confirm-btn" :class="{ 'ncc-btn-disabled': isSaving }" @click="saveEdit">
          <text class="ncc-confirm-btn-text">{{ isSaving ? '保存中…' : '保存' }}</text>
        </view>
      </view>
      <text v-if="saveError" class="ncc-error-text">{{ saveError }}</text>
    </template>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import { getNoteDetail, updateNote } from '@/api/note'
import { getSpaceGraph } from '@/api/space'
import { submitToolResult } from '@/api/chat'

export default {
  name: 'NoteCreationCard',
  components: { MarkdownRender },
  props: {
    toolCall: {
      type: Object,
      required: true
    },
    spaceId: {
      type: [String, Number],
      default: ''
    },
    conversationId: {
      type: [String, Number],
      default: ''
    }
  },
  data() {
    return {
      isEditing: false,
      isPendingEditing: false,
      editMode: 'code',
      editContent: '',
      editTitle: '',
      editNodeLabel: '',
      isSaving: false,
      isSubmitting: false,
      saveError: '',
      submitError: '',
      savedContent: null,
      savedTitle: null,
      graphNodes: []
    }
  },
  computed: {
    isPending() {
      return this.toolCall.status === 'pending_confirmation'
    },
    nodeLabel() {
      const label = this.toolCall.arguments?.node_label
      if (!label || label === 'FREE') return ''
      return label
    },
    nodeOptions() {
      const options = [{ value: 'FREE', label: '自由笔记' }]
      for (const node of this.graphNodes) {
        if (node.label) {
          options.push({ value: node.label, label: node.label })
        }
      }
      return options
    },
    nodeOptionLabels() {
      return this.nodeOptions.map(opt => opt.label)
    },
    selectedNodeIndex() {
      const idx = this.nodeOptions.findIndex(opt => opt.value === this.editNodeLabel)
      return idx >= 0 ? idx : 0
    },
    currentNodeLabel() {
      const opt = this.nodeOptions.find(o => o.value === this.editNodeLabel)
      return opt ? opt.label : '自由笔记'
    },
    displayTitle() {
      if (this.savedTitle !== null) return this.savedTitle
      return this.toolCall.arguments?.title || '未命名笔记'
    },
    displayContent() {
      if (this.savedContent !== null) return this.savedContent
      return this.toolCall.arguments?.content || ''
    },
    noteId() {
      return this.toolCall.result?.note_id
    },
    canEdit() {
      return this.toolCall.status === 'done' && this.toolCall.success && this.noteId
    },
    contentMeta() {
      const content = this.displayContent
      if (!content) return ''
      const headings = (content.match(/^#{1,3}\s+/gm) || []).length
      const chineseChars = (content.match(/[\u4e00-\u9fff]/g) || []).length
      const englishWords = content.replace(/[\u4e00-\u9fff]/g, '').split(/\s+/).filter(w => w.length > 0).length
      const totalChars = chineseChars + englishWords
      const parts = []
      if (headings > 0) parts.push(headings + ' 个章节')
      if (totalChars > 0) parts.push(totalChars.toLocaleString() + ' 字')
      return parts.join(' · ') || ''
    }
  },
  watch: {
    'toolCall.status'(newStatus) {
      if (newStatus === 'pending_confirmation') {
        this.initConfirmationMode()
      }
    }
  },
  mounted() {
    if (this.isPending) {
      this.initConfirmationMode()
    }
  },
  methods: {
    onNodePickerChange(e) {
      const idx = e.detail.value
      this.editNodeLabel = this.nodeOptions[idx]?.value || 'FREE'
    },

    async initConfirmationMode() {
      this.editTitle = this.toolCall.arguments?.title || ''
      this.editContent = this.toolCall.arguments?.content || ''
      this.editNodeLabel = this.toolCall.arguments?.node_label || 'FREE'
      this.editMode = 'code'
      this.submitError = ''
      this.isPendingEditing = false

      if (this.spaceId) {
        try {
          const { nodes } = await getSpaceGraph(this.spaceId)
          this.graphNodes = nodes || []
        } catch {
          this.graphNodes = []
        }
      }
    },

    enterPendingEdit() {
      this.isPendingEditing = true
      this.editTitle = this.toolCall.arguments?.title || ''
      this.editContent = this.toolCall.arguments?.content || ''
      this.editNodeLabel = this.toolCall.arguments?.node_label || 'FREE'
      this.editMode = 'code'
      if (this.spaceId && !this.graphNodes.length) {
        getSpaceGraph(this.spaceId).then(({ nodes }) => {
          this.graphNodes = nodes || []
        }).catch(() => { this.graphNodes = [] })
      }
    },

    exitPendingEdit() {
      this.isPendingEditing = false
    },

    async handleConfirm() {
      if (this.isSubmitting) return
      this.isSubmitting = true
      this.submitError = ''

      try {
        await submitToolResult(this.conversationId, {
          tool_call_id: this.toolCall.id,
          success: true,
          result: {
            arguments: {
              title: this.isPendingEditing ? this.editTitle : (this.toolCall.arguments?.title || ''),
              content: this.isPendingEditing ? this.editContent : (this.toolCall.arguments?.content || ''),
              node_label: this.isPendingEditing ? this.editNodeLabel : (this.toolCall.arguments?.node_label || 'FREE')
            }
          }
        })
      } catch (error) {
        this.submitError = error?.message || '提交失败，请重试'
        this.isSubmitting = false
      }
    },

    async handleCancel() {
      if (this.isSubmitting) return
      this.isSubmitting = true
      this.submitError = ''

      try {
        await submitToolResult(this.conversationId, {
          tool_call_id: this.toolCall.id,
          success: false,
          error: '用户取消了笔记创建'
        })
      } catch (error) {
        this.submitError = error?.message || '提交失败，请重试'
        this.isSubmitting = false
      }
    },

    async enterEditMode() {
      if (this.isEditing) return
      this.isEditing = true
      this.saveError = ''
      this.editMode = 'code'

      if (this.spaceId && this.noteId) {
        try {
          const detail = await getNoteDetail(this.spaceId, this.noteId)
          this.editContent = detail.content || ''
          this.editTitle = detail.title || ''
        } catch {
          this.editContent = this.displayContent
          this.editTitle = this.displayTitle
        }
      } else {
        this.editContent = this.displayContent
        this.editTitle = this.displayTitle
      }
    },

    cancelEdit() {
      if (this.isSaving) return
      this.isEditing = false
      this.editContent = ''
      this.editTitle = ''
      this.saveError = ''
    },

    async saveEdit() {
      if (this.isSaving) return
      if (!this.spaceId || !this.noteId) {
        this.saveError = '无法保存：缺少笔记信息'
        return
      }

      this.isSaving = true
      this.saveError = ''

      try {
        await updateNote(this.spaceId, this.noteId, {
          title: this.editTitle,
          content: this.editContent
        })
        this.savedContent = this.editContent
        this.savedTitle = this.editTitle
        this.isEditing = false
      } catch (error) {
        this.saveError = error?.message || '保存失败，请重试'
      } finally {
        this.isSaving = false
      }
    }
  }
}
</script>

<style scoped>
/* 卡片容器 */
.ncc-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 24rpx 28rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

/* Header 行 */
.ncc-card-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
}

.ncc-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ncc-file-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

.ncc-title-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.ncc-note-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.3;
}

.ncc-note-meta {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

.ncc-loading-text {
  font-style: italic;
}

/* 编辑触发按钮 */
.ncc-edit-trigger {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6rpx;
  padding: 10rpx 16rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
  flex-shrink: 0;
}

.ncc-edit-trigger-icon {
  width: 24rpx;
  height: 24rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

.ncc-edit-trigger-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.7);
}

/* 分割线 */
.ncc-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
}

/* 内容预览 */
.ncc-content-preview {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
  word-break: break-word;
}

/* 关联知识节点 */
.ncc-nodes-section {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.ncc-nodes-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

.ncc-nodes-row {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8rpx;
}

.ncc-node-pill {
  display: flex;
  align-items: center;
  padding: 6rpx 16rpx;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 100rpx;
}

.ncc-node-pill-text {
  font-size: 22rpx;
  color: rgba(129, 140, 248, 0.9);
}

/* 操作按钮行 */
.ncc-btns-row {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  margin-top: 4rpx;
}

.ncc-reject-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16rpx 0;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
}

.ncc-reject-btn-text {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.ncc-confirm-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16rpx 0;
  background: rgba(74, 108, 247, 0.7);
  border-radius: 16rpx;
}

.ncc-confirm-btn-text {
  font-size: 26rpx;
  font-weight: 500;
  color: #ffffff;
}

.ncc-btn-disabled {
  opacity: 0.5;
}

.ncc-error-text {
  font-size: 22rpx;
  color: rgba(239, 68, 68, 0.9);
}

/* 编辑区域 */
.ncc-field-row {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.ncc-field-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.ncc-node-picker {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 12rpx 20rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
}

.ncc-node-picker-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
}

.ncc-node-picker-arrow {
  width: 24rpx;
  height: 24rpx;
  opacity: 0.4;
  filter: brightness(0) invert(1);
}

.ncc-title-input {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
  box-sizing: border-box;
}

.ncc-edit-area {
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
  overflow: hidden;
}

.ncc-edit-toolbar {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 12rpx 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}

.ncc-tab-group {
  display: flex;
  flex-direction: row;
  gap: 4rpx;
}

.ncc-tab {
  padding: 6rpx 20rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
  border-radius: 8rpx;
}

.ncc-tab-active {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.ncc-textarea {
  width: 100%;
  min-height: 400rpx;
  padding: 20rpx 24rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(0, 0, 0, 0.2);
  border: none;
  line-height: 1.6;
  box-sizing: border-box;
}

.ncc-preview-wrap {
  padding: 20rpx 24rpx;
  min-height: 400rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.7;
  word-break: break-word;
}
</style>
