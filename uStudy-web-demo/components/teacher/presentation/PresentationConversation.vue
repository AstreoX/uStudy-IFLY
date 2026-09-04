<template>
  <view class="conversation-panel">
    <view class="conversation-header">
      <view class="header-copy">
        <text class="conversation-title">{{ project ? project.title : '教学助教' }}</text>
        <text class="conversation-note">{{ headerNote }}</text>
      </view>
      <view v-if="running" class="running-mark"><view class="running-dot"></view>{{ progressText }}</view>
    </view>

    <scroll-view scroll-y class="message-scroll" :scroll-into-view="scrollTarget" scroll-with-animation @scroll="handleScroll">
      <view v-if="!project" class="conversation-empty">
        <view class="empty-glyph">P</view>
        <text class="empty-title">从教案开始制作</text>
        <text class="empty-copy">粘贴教学内容，或添加 PDF、DOCX、TXT 教案与 PPTX 视觉模板。</text>
        <view class="starter-list">
          <text>“根据这份教案制作 20 页课堂课件”</text>
          <text>“重点讲清楚链表插入，加入过程示意图”</text>
        </view>
      </view>

      <view v-else class="message-list">
        <view v-if="!messages.length" class="project-ready-note">
          <text>项目已就绪</text>
          <text>描述课时、受众、页数或风格；没有说明时助教会根据教案自行规划。</text>
        </view>
        <view
          v-for="message in messages"
          :id="`msg-${message.id}`"
          :key="message.id"
          class="message-row"
          :class="message.role === 'user' ? 'message-row-right' : 'message-row-left'"
        >
          <view v-if="message.role === 'user'" class="user-msg-group">
            <view class="message-bubble bubble-user">
              <text class="bubble-text">{{ message.content }}</text>
            </view>
          </view>
          <view v-else class="assistant-turn">
            <view v-if="message.thinkingContent || message.isThinking" class="message-bubble bubble-ai thinking-bubble">
              <AgentThinkingBlock
                class="assistant-thinking"
                :content="message.thinkingContent || ''"
                :active="Boolean(message.isThinking)"
                :duration="message.thinkingDuration || 0"
              />
            </view>
            <template v-for="(segment, segmentIndex) in messageSegments(message)" :key="`${message.id}-${segmentIndex}-${segment.toolCall?.id || 'text'}`">
              <view v-if="segment.type === 'text' && segment.content" class="message-bubble bubble-ai segment-bubble">
                <view class="message-body"><MarkdownRender :content="displayText(segment.content)" /></view>
              </view>
              <AgentToolCard
                v-else-if="segment.type === 'tool'"
                class="assistant-tool"
                :tool-call="segment.toolCall"
              />
            </template>
            <view v-if="message.runStatus === 'failed'" class="recovery-card" :class="{ blocked: !message.recoverable }">
              <view class="recovery-copy">
                <text>{{ message.runError || '任务已中断，过程和工作区已经保存' }}</text>
                <text>{{ message.recoverable ? '可以从最近的 checkpoint 继续，无需重新发送需求。' : '当前服务配置或外部依赖未就绪，请管理员检查沙盒服务。' }}</text>
              </view>
              <view v-if="message.recoverable" class="recovery-action" @tap="$emit('resume-run', message)">继续任务</view>
            </view>
            <view v-if="message.streaming && !message.thinkingContent && !messageSegments(message).length" class="typing-indicator">
              <view></view><view></view><view></view>
            </view>
          </view>
        </view>

        <view v-if="running" class="run-progress">
          <view class="progress-heading"><text>{{ progressText }}</text><text>{{ progressValue }}%</text></view>
          <view class="progress-track"><view class="progress-fill" :style="{ width: `${progressValue}%` }"></view></view>
          <text class="progress-note">Agent 正在独立沙盒中调用课件技能、构建并检查文件。</text>
        </view>
        <view id="message-end" class="message-end"></view>
      </view>
    </scroll-view>

    <view class="composer-shell">
      <view v-if="sources.length" class="source-row">
        <view v-for="source in sources" :key="source.localId || source.id" class="source-chip">
          <text class="source-kind">{{ sourceKind(source) }}</text>
          <text class="source-name">{{ source.name }}</text>
          <text v-if="source.uploading" class="source-state">上传中</text>
          <view v-else class="source-remove" @tap="$emit('remove-source', source)">×</view>
        </view>
      </view>
      <view class="composer" :class="{ focused: composerFocused }">
        <textarea
          v-model="draft"
          class="composer-input"
          :disabled="running"
          :placeholder="project ? '继续修改课件，或粘贴新的教案内容…' : '粘贴教案并说明你想制作的课件…'"
          :maxlength="20000"
          auto-height
          @focus="composerFocused = true"
          @blur="composerFocused = false"
          @keydown="handleKeydown"
        />
        <view class="composer-actions">
          <view class="attach-button" :class="{ disabled: running || uploading }" @tap="chooseFiles">
            <svg viewBox="0 0 256 256"><path d="M216,120v64a32,32,0,0,1-32,32H72a32,32,0,0,1-32-32V72A32,32,0,0,1,72,40h64" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><line x1="128" y1="104" x2="208" y2="24" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><polyline points="152 24 208 24 208 80" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/></svg>
            <text>{{ uploading ? '上传中' : '添加教案 / 模板' }}</text>
          </view>
          <view v-if="running" class="cancel-button" @tap="$emit('cancel')">停止</view>
          <view v-else class="send-button" :class="{ disabled: !canSend }" @tap="submit">
            <svg viewBox="0 0 256 256"><line x1="128" y1="208" x2="128" y2="48" stroke="currentColor" stroke-width="20" stroke-linecap="round"/><polyline points="64 112 128 48 192 112" fill="none" stroke="currentColor" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </view>
        </view>
      </view>
      <text class="composer-hint">Enter 发送 · Shift + Enter 换行 · 文件仅对当前教师项目可见</text>
    </view>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import AgentThinkingBlock from '@/components/chat/AgentThinkingBlock.vue'
import AgentToolCard from '@/components/chat/AgentToolCard.vue'
import { getAgentMessageSegments } from '@/utils/agent-stream-segments'

const ACCEPTED_EXTENSIONS = ['pdf', 'docx', 'txt', 'pptx']

export default {
  components: { MarkdownRender, AgentThinkingBlock, AgentToolCard },
  props: {
    project: { type: Object, default: null },
    messages: { type: Array, default: () => [] },
    sources: { type: Array, default: () => [] },
    running: { type: Boolean, default: false },
    uploading: { type: Boolean, default: false },
    progress: { type: Object, default: () => ({}) }
  },
  emits: ['send', 'cancel', 'upload-files', 'remove-source', 'resume-run'],
  data() {
    return { draft: '', composerFocused: false, scrollTarget: '', autoFollow: true }
  },
  computed: {
    canSend() {
      return !this.running && !this.uploading && (!!this.draft.trim() || this.sources.some(source => source.id))
    },
    progressValue() {
      const value = Number(this.progress?.percent ?? this.progress?.progress ?? 0)
      return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
    },
    progressText() {
      return this.progress?.label || this.progress?.message || this.phaseLabel(this.progress?.phase) || '正在准备课件'
    },
    headerNote() {
      if (!this.project) return '创建课件、修改页面并发布到课程资料库'
      if (this.running) return '当前任务在服务器隔离工作区中运行'
      return '可继续用自然语言调整任意页面'
    }
  },
  watch: {
    messages: {
      deep: true,
      handler() { this.requestScroll() }
    },
    running() { this.requestScroll() }
  },
  mounted() { this.requestScroll(true) },
  methods: {
    displayText(content) {
      // File citations are an internal agent protocol. Render a compact,
      // human-readable status instead of leaking the workspace path into chat.
      return String(content || '').replace(
        /:codex-file-citation\{[^}]*\}/g,
        '已生成课件文件，可在右侧预览中下载'
      )
    },
    phaseLabel(phase) {
      const labels = {
        queued: '等待沙盒资源', preparing: '读取课程与教案', planning: '规划课件结构',
        generating_assets: '生成课件素材', building: '构建 PowerPoint', rendering: '渲染逐页预览',
        validating: '检查版式与内容', completed: '课件已完成'
      }
      return labels[String(phase || '').toLowerCase()] || ''
    },
    messageSegments(message) {
      return getAgentMessageSegments(message, message.toolCalls || message.activities || [])
    },
    requestScroll(force = false) {
      if (!force && !this.autoFollow) return
      this.$nextTick(() => {
        this.scrollTarget = ''
        this.$nextTick(() => { this.scrollTarget = 'message-end' })
      })
    },
    handleScroll(event) {
      const { scrollTop = 0, scrollHeight = 0, clientHeight = 0 } = event?.detail || {}
      if (!scrollHeight || !clientHeight) return
      this.autoFollow = scrollHeight - scrollTop - clientHeight < 96
    },
    sourceKind(source) {
      const ext = String(source.name || '').split('.').pop()?.toUpperCase()
      return ext || (source.kind === 'template' ? 'PPTX' : 'FILE')
    },
    chooseFiles() {
      if (this.running || this.uploading) return
      // #ifdef H5
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.pdf,.docx,.txt,.pptx'
      input.multiple = true
      input.onchange = (event) => {
        const files = Array.from(event?.target?.files || []).filter(file => {
          const ext = String(file.name || '').split('.').pop()?.toLowerCase()
          return ACCEPTED_EXTENSIONS.includes(ext)
        })
        if (files.length) this.$emit('upload-files', files)
      }
      input.click()
      // #endif
    },
    handleKeydown(event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        this.submit()
      }
    },
    submit() {
      if (!this.canSend) return
      const content = this.draft.trim()
      this.draft = ''
      this.$emit('send', content)
    }
  }
}
</script>

<style scoped>
.conversation-panel { height: 100%; min-height: 0; display: flex; flex-direction: column; background: rgba(42,42,60,.48); color: #fff; backdrop-filter: blur(20px); }
.conversation-header { height: 76px; box-sizing: border-box; padding: 15px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid rgba(255,255,255,.07); }
.header-copy { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.conversation-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 15px; font-weight: 650; }
.conversation-note { color: rgba(255,255,255,.38); font-size: 11px; }
.running-mark { display: flex; align-items: center; gap: 7px; color: #a8c5ff; font-size: 10px; white-space: nowrap; }
.running-dot { width: 6px; height: 6px; border-radius: 50%; background: #7ea8ff; animation: blink 1.3s infinite; }
.message-scroll { flex: 1; min-height: 0; }
.conversation-empty { min-height: 100%; box-sizing: border-box; padding: 48px 12%; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; }
.empty-glyph { width: 44px; height: 44px; display: grid; place-items: center; margin-bottom: 22px; border: 1px solid rgba(126,168,255,.36); border-radius: 12px; color: #acc8ff; font-family: Georgia, serif; font-size: 22px; background: rgba(126,168,255,.07); }
.empty-title { font-size: 22px; font-weight: 650; letter-spacing: -.02em; }
.empty-copy { max-width: 460px; margin-top: 9px; color: rgba(255,255,255,.46); font-size: 12px; line-height: 1.7; }
.starter-list { width: 100%; max-width: 520px; margin-top: 28px; border-top: 1px solid rgba(255,255,255,.07); }
.starter-list text { display: block; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,.07); color: rgba(255,255,255,.55); font-size: 11px; }
.message-list { padding: 18px 16px 26px; }
.project-ready-note { padding: 16px 0 26px; display: flex; flex-direction: column; gap: 6px; color: rgba(255,255,255,.35); font-size: 11px; }
.project-ready-note text:first-child { color: rgba(255,255,255,.72); font-size: 13px; font-weight: 600; }
.message-row { display: flex; max-width: 100%; margin-bottom: 12px; box-sizing: border-box; }
.message-row-left { justify-content: flex-start; }
.message-row-right { justify-content: flex-end; }
.user-msg-group { display: flex; flex-direction: column; align-items: flex-end; max-width: 85%; margin-left: auto; }
.assistant-turn { width: min(88%, 650px); display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.assistant-thinking { width: 100%; margin: 2px 0 3px; }
.thinking-bubble { width: 100%; max-width: 100%; padding-top: 8px; padding-bottom: 9px; }
.assistant-tool { width: 100%; animation: timeline-in .2s ease-out; }
.recovery-card { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 12px; box-sizing: border-box; border: 1px solid rgba(239,168,68,.2); border-radius: 12px; background: rgba(239,168,68,.055); }
.recovery-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; color: rgba(255,255,255,.68); font-size: 10px; }
.recovery-copy text:last-child { color: rgba(255,255,255,.34); font-size: 9px; }
.recovery-action { flex-shrink: 0; padding: 7px 10px; border-radius: 8px; color: #ffe0a3; background: rgba(239,168,68,.13); font-size: 10px; cursor: pointer; }
.recovery-card.blocked { border-color: rgba(239,68,68,.18); background: rgba(239,68,68,.045); }
.message-bubble { max-width: 85%; padding: 10px 14px; border-radius: 14px; box-sizing: border-box; word-break: break-word; }
.bubble-user { max-width: none; border: 1px solid rgba(59,130,246,.25); border-bottom-right-radius: 4px; background: rgba(59,130,246,.2); }
.bubble-user .bubble-text { color: rgba(255,255,255,.95); font-size: 14px; line-height: 1.5; user-select: text; white-space: pre-wrap; }
.bubble-ai { border: 1px solid rgba(255,255,255,.08); border-bottom-left-radius: 4px; background: rgba(255,255,255,.06); }
.segment-bubble { width: auto; max-width: 100%; animation: timeline-in .2s ease-out; }
.message-body { color: rgba(255,255,255,.88); font-size: 14px; line-height: 1.65; }
.message-body :deep(.markdown-body) { font-size: 14px; line-height: 1.65; }
.activity-list { margin-top: 12px; padding: 7px 0; border-top: 1px solid rgba(255,255,255,.06); border-bottom: 1px solid rgba(255,255,255,.06); }
.activity-row { display: flex; gap: 8px; padding: 6px 0; color: rgba(255,255,255,.52); font-size: 10px; }
.activity-icon { width: 16px; height: 16px; display: grid; place-items: center; border-radius: 50%; background: rgba(126,168,255,.12); color: #90b4ff; }
.activity-icon.completed { background: rgba(98,181,131,.12); color: #8fcea9; }
.activity-icon.failed { background: rgba(239,68,68,.12); color: #ff8d8d; }
.activity-copy { display: flex; flex-direction: column; gap: 2px; }
.activity-detail { color: rgba(255,255,255,.28); }
.typing-indicator { height: 26px; display: flex; align-items: center; gap: 4px; padding: 0 5px; }
.typing-indicator view { width: 5px; height: 5px; border-radius: 50%; background: rgba(255,255,255,.32); animation: typing-bounce 1.2s ease-in-out infinite; }
.typing-indicator view:nth-child(2) { animation-delay: .14s; }
.typing-indicator view:nth-child(3) { animation-delay: .28s; }
.run-progress { max-width: 85%; margin: 6px 0 22px; padding: 13px 14px; border: 1px solid rgba(126,168,255,.16); border-radius: 14px 14px 14px 4px; background: rgba(126,168,255,.055); }
.progress-heading { display: flex; justify-content: space-between; color: rgba(255,255,255,.66); font-size: 10px; }
.progress-track { height: 2px; margin-top: 10px; overflow: hidden; background: rgba(255,255,255,.08); }
.progress-fill { height: 100%; background: #75a4ff; transition: width .4s ease; }
.progress-note { display: block; margin-top: 8px; color: rgba(255,255,255,.26); font-size: 9px; }
.message-end { height: 1px; }
.composer-shell { flex-shrink: 0; padding: 10px 16px 15px; background: linear-gradient(180deg, rgba(42,42,60,0), rgba(42,42,60,.78) 18%); backdrop-filter: blur(18px); }
.source-row { display: flex; gap: 6px; padding-bottom: 8px; overflow-x: auto; }
.source-chip { max-width: 220px; display: flex; align-items: center; gap: 6px; padding: 5px 7px; border: 1px solid rgba(255,255,255,.09); border-radius: 7px; background: rgba(255,255,255,.035); }
.source-kind { color: #9bbaff; font-size: 8px; font-weight: 700; }
.source-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(255,255,255,.55); font-size: 9px; }
.source-state { color: rgba(255,255,255,.28); font-size: 8px; white-space: nowrap; }
.source-remove { color: rgba(255,255,255,.34); cursor: pointer; }
.composer { padding: 11px 11px 9px 13px; border: 1px solid rgba(255,255,255,.16); border-radius: 13px; background: rgba(255,255,255,.08); transition: border-color .18s ease, background .18s ease; backdrop-filter: blur(16px); }
.composer.focused { border-color: rgba(126,168,255,.48); background: rgba(255,255,255,.06); }
.composer-input { width: 100%; min-height: 48px; max-height: 160px; color: rgba(255,255,255,.88); font-size: 12px; line-height: 1.6; background: transparent; }
.composer-actions { margin-top: 7px; display: flex; align-items: center; justify-content: space-between; }
.attach-button { display: flex; align-items: center; gap: 6px; padding: 4px; color: rgba(255,255,255,.42); font-size: 9px; cursor: pointer; }
.attach-button svg { width: 14px; height: 14px; }
.attach-button.disabled { opacity: .35; cursor: default; }
.send-button, .cancel-button { height: 28px; display: grid; place-items: center; border-radius: 8px; cursor: pointer; }
.send-button { width: 28px; color: #111725; background: #dce8ff; }
.send-button svg { width: 14px; height: 14px; }
.send-button.disabled { opacity: .28; cursor: default; }
.cancel-button { padding: 0 12px; color: #ffc1c1; border: 1px solid rgba(239,68,68,.22); font-size: 10px; }
.composer-hint { display: block; margin-top: 6px; text-align: center; color: rgba(255,255,255,.2); font-size: 8px; }
@keyframes blink { 50% { opacity: .3; } }
@keyframes typing-bounce { 0%,60%,100% { transform: translateY(0); opacity: .3; } 30% { transform: translateY(-3px); opacity: 1; } }
@keyframes timeline-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 900px) { .conversation-empty { padding: 32px 7%; } .message-list { padding-left: 12px; padding-right: 12px; } .composer-shell { padding-left: 12px; padding-right: 12px; } .assistant-turn { width: 94%; } }
@media (prefers-reduced-motion: reduce) { .assistant-tool, .segment-bubble, .typing-indicator view { animation: none; } }
</style>
