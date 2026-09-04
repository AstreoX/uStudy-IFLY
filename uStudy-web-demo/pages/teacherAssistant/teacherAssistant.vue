<template>
  <view class="assistant-page">
    <view class="ambient ambient-one"></view>
    <view class="ambient ambient-two"></view>

    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @select-space="openStudySpace"
    />

    <view class="assistant-workspace">
      <view class="assistant-topbar">
        <view class="assistant-context-copy">
          <text class="assistant-eyebrow">TEACHING · PRESENTATIONS</text>
          <text class="assistant-title">教学助教</text>
        </view>
        <TeacherSpaceSelector
          :spaces="teacherSpaces"
          :space-id="spaceId"
          :disabled="spaceSelectorDisabled"
          @change="handleTeacherSpaceChange"
        />
      </view>
      <view class="mobile-bar">
        <view class="mobile-project-button" @tap="projectRailOpen = true">
          <svg viewBox="0 0 256 256"><line x1="40" y1="72" x2="216" y2="72" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><line x1="40" y1="128" x2="216" y2="128" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><line x1="40" y1="184" x2="216" y2="184" stroke="currentColor" stroke-width="16" stroke-linecap="round"/></svg>
          <text>{{ selectedProject?.title || '教学助教' }}</text>
        </view>
        <view class="mobile-tabs">
          <view :class="{ active: mobilePane === 'chat' }" @tap="mobilePane = 'chat'">对话</view>
          <view :class="{ active: mobilePane === 'preview' }" @tap="mobilePane = 'preview'">预览</view>
        </view>
      </view>

      <view class="workspace-grid">
        <view class="rail-column" :class="{ open: projectRailOpen }">
          <PresentationProjectRail
            :space-name="selectedSpaceName"
            :projects="projects"
            :revisions="revisions"
            :selected-project-id="selectedProjectId"
            :selected-revision-id="selectedRevisionId"
            :loading="projectsLoading"
            :creating="creatingProject"
            @create="createBlankProject"
            @select-project="selectProject"
            @select-revision="selectRevision"
          />
        </view>
        <view v-if="projectRailOpen" class="rail-backdrop" @tap="projectRailOpen = false"></view>

        <view class="chat-column" :class="{ 'mobile-hidden': mobilePane !== 'chat' }">
          <PresentationConversation
            :project="selectedProject"
            :messages="messages"
            :sources="sources"
            :running="running"
            :uploading="uploading"
            :progress="progress"
            @send="sendMessage"
            @cancel="cancelRun"
            @upload-files="uploadFiles"
            @remove-source="removeSource"
            @resume-run="resumeFailedRun"
          />
        </view>

        <view class="preview-column" :class="{ 'mobile-hidden': mobilePane !== 'preview' }">
          <PresentationPreview
            :revision="selectedRevision"
            :selected-slide="selectedSlide"
            :preview-url="previewUrl"
            :preview-loading="previewLoading"
            :busy="actionBusy"
            :running="running"
            @select-slide="selectSlide"
            @restore="confirmRestore"
            @download="downloadRevision"
            @publish="confirmPublish"
            @retry-preview="loadPreview"
            @preview-error="handlePreviewError"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import TeacherSpaceSelector from '@/components/teacher/TeacherSpaceSelector.vue'
import PresentationProjectRail from '@/components/teacher/presentation/PresentationProjectRail.vue'
import PresentationConversation from '@/components/teacher/presentation/PresentationConversation.vue'
import PresentationPreview from '@/components/teacher/presentation/PresentationPreview.vue'
import { useSpacesStore } from '@/store/spaces'
import {
  getTeacherSpaces,
  resolveTeacherSpace,
  rememberTeacherSpace,
  TEACHER_SPACE_TOOLS
} from '@/utils/teacher-space-selection'
import {
  appendAgentText,
  applyAgentStreamEvent,
  createStreamingAgentMessage,
  finalizeAgentMessage,
  upsertAgentTool
} from '@/utils/agent-stream-segments'
import {
  cancelPresentationRun,
  createPresentationProject,
  deletePresentationSource,
  fetchPresentationDownload,
  fetchPresentationPreview,
  getPresentationMessages,
  getPresentationProject,
  listPresentationSources,
  listPresentationProjects,
  listPresentationRevisions,
  normalizePresentationRevision,
  publishPresentationRevision,
  restorePresentationRevision,
  restartPresentationRun,
  resumePresentationRun,
  sendPresentationMessage,
  uploadPresentationSource
} from '@/api/teacher-presentations'

const MAX_SOURCE_BYTES = 40 * 1024 * 1024
const TEACHER_ROUTE = '/pages/teacherAssistant/teacherAssistant'

export default {
  components: {
    HomeSidebar,
    TeacherSpaceSelector,
    PresentationProjectRail,
    PresentationConversation,
    PresentationPreview
  },
  data() {
    return {
      spacesStore: useSpacesStore(),
      spaceId: '',
      sidebarCollapsed: false,
      projects: [],
      revisions: [],
      messages: [],
      sources: [],
      selectedProjectId: '',
      selectedRevisionId: '',
      selectedSlide: 1,
      previewUrl: '',
      previewLoadingState: false,
      previewRequestVersion: 0,
      revisionRequestVersion: 0,
      projectsLoading: false,
      projectLoading: false,
      creatingProject: false,
      uploading: false,
      running: false,
      actionBusy: false,
      progress: {},
      currentRunId: '',
      streamAbort: null,
      reconnectTimer: null,
      reconnectAttempts: 0,
      projectRailOpen: false,
      mobilePane: 'chat',
      requestVersion: 0,
      contextVersion: 0
    }
  },
  computed: {
    teacherSpaces() {
      return getTeacherSpaces(this.spacesStore.spaces)
    },
    selectedSpace() {
      return this.teacherSpaces.find(space => String(space.id) === String(this.spaceId)) || null
    },
    selectedSpaceName() {
      return this.selectedSpace?.name || '课程空间'
    },
    spaceSelectorDisabled() {
      return this.creatingProject || this.uploading || this.actionBusy
    },
    selectedProject() {
      return this.projects.find(project => project.id === this.selectedProjectId) || null
    },
    selectedRevision() {
      return this.revisions.find(revision => revision.id === this.selectedRevisionId) || null
    },
    previewLoading() {
      return this.previewLoadingState
    }
  },
  async onLoad(options) {
    await this.spacesStore.loadSpaces(true)
    const resolved = resolveTeacherSpace({
      spaces: this.spacesStore.spaces,
      requestedSpaceId: options?.spaceId,
      tool: TEACHER_SPACE_TOOLS.PRESENTATIONS
    })
    if (resolved.invalidRequested) {
      uni.showToast({ title: '指定课程空间无效或已无权限', icon: 'none' })
    }
    if (!resolved.space) {
      uni.showToast({ title: '当前账号没有可管理的课程空间', icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
      return
    }
    this.spaceId = String(resolved.space.id)
    if (resolved.shouldCanonicalize) {
      uni.reLaunch({ url: `${TEACHER_ROUTE}?spaceId=${encodeURIComponent(this.spaceId)}` })
      return
    }
    await this.loadProjects()
  },
  beforeUnmount() {
    this.contextVersion += 1
    this.requestVersion += 1
    this.previewRequestVersion += 1
    this.revisionRequestVersion += 1
    this.detachPresentationStream()
    this.releasePreviewUrl()
  },
  methods: {
    handleTeacherSpaceChange(space) {
      if (!space?.id || String(space.id) === String(this.spaceId) || this.spaceSelectorDisabled) return
      if (this.running) {
        uni.showModal({
          title: '切换课程空间？',
          content: '当前课件任务会继续在后台运行。切换后可返回此课程空间恢复查看。',
          confirmText: '继续切换',
          success: result => { if (result.confirm) this.commitTeacherSpaceChange(space.id) }
        })
        return
      }
      this.commitTeacherSpaceChange(space.id)
    },
    commitTeacherSpaceChange(spaceId) {
      this.contextVersion += 1
      this.requestVersion += 1
      this.previewRequestVersion += 1
      this.revisionRequestVersion += 1
      this.detachPresentationStream()
      this.releasePreviewUrl()
      this.projects = []
      this.revisions = []
      this.messages = []
      this.sources = []
      this.selectedProjectId = ''
      this.selectedRevisionId = ''
      this.selectedSlide = 1
      this.projectRailOpen = false
      this.progress = {}
      rememberTeacherSpace(TEACHER_SPACE_TOOLS.PRESENTATIONS, spaceId)
      uni.reLaunch({ url: `${TEACHER_ROUTE}?spaceId=${encodeURIComponent(spaceId)}` })
    },
    detachPresentationStream() {
      this.running = false
      const abort = this.streamAbort
      this.streamAbort = null
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
      this.reconnectAttempts = 0
      abort?.()
    },
    async loadProjects(preferredProjectId = '') {
      const contextVersion = this.contextVersion
      const requestedSpaceId = this.spaceId
      this.projectsLoading = true
      try {
        const projects = await listPresentationProjects(requestedSpaceId)
        if (contextVersion !== this.contextVersion || requestedSpaceId !== this.spaceId) return
        this.projects = projects
        const targetId = preferredProjectId || this.selectedProjectId || this.projects[0]?.id || ''
        if (targetId) await this.selectProject(targetId)
      } catch (error) {
        if (contextVersion === this.contextVersion) this.showError(error, '无法加载课件项目')
      } finally {
        if (contextVersion === this.contextVersion) this.projectsLoading = false
      }
    },
    async createProject(title) {
      if (this.creatingProject) return this.selectedProject
      this.creatingProject = true
      try {
        const project = await createPresentationProject(this.spaceId, { title: title || this.defaultProjectTitle() })
        this.projects = [project, ...this.projects.filter(item => item.id !== project.id)]
        await this.selectProject(project.id)
        return project
      } catch (error) {
        this.showError(error, '新建项目失败')
        return null
      } finally {
        this.creatingProject = false
      }
    },
    async createBlankProject() {
      await this.createProject(this.defaultProjectTitle())
      this.projectRailOpen = false
      this.mobilePane = 'chat'
    },
    defaultProjectTitle() {
      const date = new Date()
      return `新课件 · ${date.getMonth() + 1}月${date.getDate()}日`
    },
    titleFromContent(content) {
      const firstLine = String(content || '').split(/\r?\n/).find(line => line.trim())?.trim() || ''
      return firstLine.slice(0, 32) || this.defaultProjectTitle()
    },
    async selectProject(projectId) {
      if (!projectId) return
      const version = ++this.requestVersion
      this.revisionRequestVersion += 1
      if (this.streamAbort && projectId !== this.selectedProjectId) {
        this.streamAbort()
        this.streamAbort = null
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
        this.reconnectAttempts = 0
        this.running = false
      }
      this.selectedProjectId = String(projectId)
      this.projectRailOpen = false
      this.projectLoading = true
      this.messages = []
      this.sources = []
      this.revisions = []
      this.selectedRevisionId = ''
      this.selectedSlide = 1
      this.releasePreviewUrl()
      try {
        const [project, messages, revisions, sources] = await Promise.all([
          getPresentationProject(this.spaceId, projectId),
          getPresentationMessages(this.spaceId, projectId),
          listPresentationRevisions(this.spaceId, projectId),
          listPresentationSources(this.spaceId, projectId)
        ])
        if (version !== this.requestVersion) return
        this.upsertProject(project)
        this.messages = messages
        this.sources = sources
        this.revisions = this.sortRevisions(revisions)
        const revisionId = project.currentRevisionId
          || this.revisions.find(revision => revision.status === 'completed')?.id
          || ''
        if (revisionId) await this.selectRevision(revisionId)
        if (project.activeRunId && ['queued', 'running', 'recovering', 'waiting_confirmation'].includes(project.status)) {
          this.resumeActiveRun(project.activeRunId)
        }
      } catch (error) {
        if (version === this.requestVersion) this.showError(error, '无法读取课件项目')
      } finally {
        if (version === this.requestVersion) this.projectLoading = false
      }
    },
    async refreshRevisions(preferredId = '') {
      if (!this.selectedProjectId) return
      const contextVersion = this.contextVersion
      const requestVersion = ++this.revisionRequestVersion
      const requestedSpaceId = this.spaceId
      const requestedProjectId = this.selectedProjectId
      const revisions = await listPresentationRevisions(requestedSpaceId, requestedProjectId)
      if (
        contextVersion !== this.contextVersion
        || requestVersion !== this.revisionRequestVersion
        || requestedSpaceId !== this.spaceId
        || requestedProjectId !== this.selectedProjectId
      ) return
      this.revisions = this.sortRevisions(revisions)
      const preferred = this.revisions.find(revision =>
        revision.id === String(preferredId || this.selectedRevisionId)
        && revision.status === 'completed'
      )
      const targetId = preferred?.id
        || this.revisions.find(revision => revision.status === 'completed')?.id
        || ''
      if (targetId) await this.selectRevision(targetId)
    },
    sortRevisions(revisions) {
      return [...revisions].sort((a, b) => {
        if (a.number || b.number) return Number(b.number || 0) - Number(a.number || 0)
        return new Date(b.createdAt || 0) - new Date(a.createdAt || 0)
      })
    },
    async selectRevision(revisionId) {
      if (!revisionId) return
      this.selectedRevisionId = String(revisionId)
      this.selectedSlide = 1
      await this.loadPreview()
    },
    async selectSlide(slide) {
      if (slide === this.selectedSlide && this.previewUrl) return
      this.selectedSlide = Number(slide) || 1
      await this.loadPreview()
    },
    async loadPreview() {
      if (!this.selectedProjectId || !this.selectedRevisionId) return
      if (!this.selectedRevision || this.selectedRevision.status !== 'completed') {
        this.releasePreviewUrl()
        this.previewLoadingState = false
        return
      }
      const projectId = this.selectedProjectId
      const revisionId = this.selectedRevisionId
      const slide = this.selectedSlide
      const requestVersion = ++this.previewRequestVersion
      this.previewLoadingState = true
      this.releasePreviewUrl()
      try {
        const blob = await fetchPresentationPreview(this.spaceId, projectId, revisionId, slide)
        if (requestVersion !== this.previewRequestVersion || projectId !== this.selectedProjectId || revisionId !== this.selectedRevisionId || slide !== this.selectedSlide) return
        this.previewUrl = URL.createObjectURL(blob)
      } catch (error) {
        if (requestVersion !== this.previewRequestVersion) return
        this.previewUrl = ''
        this.showError(error, '预览读取失败')
      } finally {
        if (requestVersion === this.previewRequestVersion) this.previewLoadingState = false
      }
    },
    handlePreviewError() {
      this.releasePreviewUrl()
    },
    releasePreviewUrl() {
      if (this.previewUrl && typeof URL !== 'undefined') URL.revokeObjectURL(this.previewUrl)
      this.previewUrl = ''
    },
    async uploadFiles(files) {
      if (this.uploading || this.running) return
      let project = this.selectedProject
      if (!project) project = await this.createProject(this.defaultProjectTitle())
      if (!project) return

      const accepted = files.filter(file => {
        if (file.size > MAX_SOURCE_BYTES) {
          uni.showToast({ title: `${file.name} 超过 40MB`, icon: 'none' })
          return false
        }
        return true
      })
      if (!accepted.length) return

      this.uploading = true
      for (const file of accepted) {
        const localId = `local-${Date.now()}-${Math.random()}`
        const placeholder = { localId, name: file.name, uploading: true }
        this.sources = [...this.sources, placeholder]
        try {
          const kind = file.name.toLowerCase().endsWith('.pptx') ? 'template' : 'source'
          const source = await uploadPresentationSource(this.spaceId, project.id, file, kind)
          this.sources = this.sources.map(item => item.localId === localId ? { ...source, localId } : item)
        } catch (error) {
          this.sources = this.sources.filter(item => item.localId !== localId)
          this.showError(error, `${file.name} 上传失败`)
        }
      }
      this.uploading = false
    },
    async removeSource(source) {
      if (this.running || source.uploading) return
      const sourceKey = source.localId || source.id
      const previous = [...this.sources]
      this.sources = this.sources.filter(item => (item.localId || item.id) !== sourceKey)
      if (!source.id || !this.selectedProjectId) return
      try {
        await deletePresentationSource(this.spaceId, this.selectedProjectId, source.id)
      } catch (error) {
        this.sources = previous
        this.showError(error, '附件移除失败')
      }
    },
    async sendMessage(content) {
      if (this.running || this.uploading) return
      let project = this.selectedProject
      if (!project) project = await this.createProject(this.titleFromContent(content))
      if (!project) return

      const sourceIds = this.sources.filter(source => source.id && !source.uploading).map(source => source.id)
      const finalContent = content || '请根据我上传的教案和模板制作一套课堂课件。'
      const userMessage = { id: `local-user-${Date.now()}`, role: 'user', content: finalContent, activities: [] }
      const publishIntent = this.isPublishIntent(finalContent)
      let assistantMessage = createStreamingAgentMessage(`local-assistant-${Date.now()}`)
      if (publishIntent) {
        assistantMessage = upsertAgentTool(assistantMessage, {
          id: `optimistic-publish-${Date.now()}`,
          tool: 'publish_presentation_to_space',
          name: 'publish_presentation_to_space',
          status: 'running',
          optimistic: true,
          label: '准备发布课件',
          detail: '正在请求 AI 确认发布到课程资料库'
        })
      }
      this.messages = [...this.messages, userMessage, assistantMessage]
      this.sources = []
      this.running = true
      this.progress = { phase: 'queued', percent: 0, label: '正在启动隔离工作区' }
      this.currentRunId = ''
      this.updateProjectStatus(project.id, 'running')

      const streamContextVersion = this.contextVersion
      const streamSpaceId = this.spaceId
      const isCurrentStream = () => streamContextVersion === this.contextVersion && streamSpaceId === this.spaceId
      const updateAssistant = (updater) => {
        if (!isCurrentStream()) return
        this.messages = this.messages.map(message => message.id === assistantMessage.id ? updater({ ...message }) : message)
      }
      const streamCallbacks = {
        onConnectionError: () => {
          if (isCurrentStream()) this.scheduleRunReconnect(project.id, assistantMessage.id, streamCallbacks)
        },
        onThinkingDelta: (text, event = {}) => updateAssistant(message => applyAgentStreamEvent(
          message,
          'thinking_delta',
          { ...event, content: text }
        )),
        onTextDelta: (text, event = {}) => updateAssistant(message => applyAgentStreamEvent(
          message,
          'text_delta',
          { ...event, content: text }
        )),
        onToolCall: (event) => {
          if (!isCurrentStream()) return
          const toolId = event.tool_call_id || event.id || `${event.tool || 'tool'}-${Date.now()}`
          updateAssistant(message => {
            const hasOptimistic = message.streamSegments?.some(segment =>
              segment.type === 'tool'
              && segment.toolCall?.optimistic
              && segment.toolCall?.tool === (event.tool || event.name)
            )
            const base = hasOptimistic
              ? {
                  ...message,
                  streamSegments: message.streamSegments.filter(segment =>
                    !(segment.type === 'tool' && segment.toolCall?.optimistic)
                  ),
                  segments: message.segments.filter(segment =>
                    !(segment.type === 'tool' && segment.toolCall?.optimistic)
                  )
                }
              : message
            return applyAgentStreamEvent(base, 'tool_call', {
              ...event,
              id: toolId,
              label: event.display_name || event.label,
              detail: event.detail || event.message || ''
            })
          })
          this.updateToolProgress(event)
        },
        onProgress: (event) => {
          if (!isCurrentStream()) return
          this.currentRunId = String(event.run_id || event.runId || this.currentRunId || '')
          if (this.currentRunId) {
            updateAssistant(message => ({ ...message, runId: this.currentRunId }))
          }
          this.progress = {
            ...event,
            phase: event.phase || event.stage || this.progress.phase,
            percent: Number(event.percent ?? event.progress ?? this.progress.percent ?? 0),
            label: event.label || event.message || ''
          }
        },
        onRevision: (event) => { if (isCurrentStream()) this.handleRevisionEvent(event) },
        onReady: (event) => { if (isCurrentStream()) this.handleRevisionEvent(event, true) },
        onDone: (event) => {
          if (!isCurrentStream()) return
          const terminalStatus = String(event?.status || 'completed').toLowerCase()
          const artifactReady = event?.artifact_ready !== false
          const finalText = event?.content || event?.message || ''
          const fallback = terminalStatus === 'failed'
            ? '任务未完成，请查看上方错误并重试。'
            : terminalStatus === 'cancelled'
              ? '任务已停止。'
              : artifactReady ? '课件已经完成。' : '可以继续告诉我你的课件需求。'
          updateAssistant(message => {
          let next = message
            next = this.failUnconfirmedPublishTool(next, terminalStatus)
            if (!next.content && !next.streamSegments?.length) next = appendAgentText(next, finalText || fallback)
            return finalizeAgentMessage(next, event)
          })
          this.finishRun(artifactReady ? terminalStatus : 'idle')
          if (terminalStatus === 'completed' && artifactReady) {
            this.refreshRevisions(event?.revision_id || event?.revisionId || '').catch(() => {})
          }
        },
        onError: (message, event = {}) => {
          if (!isCurrentStream()) return
          updateAssistant(item => ({
            ...finalizeAgentMessage(
              item.content || item.streamSegments?.length ? item : appendAgentText(item, `任务未完成：${message}`),
              { status: 'failed' }
            ),
            runId: item.runId || this.currentRunId,
            recoverable: event.retryable !== false,
            runStatus: 'failed',
            runError: message
          }))
          this.finishRun('failed')
        },
        onComplete: () => {
          if (isCurrentStream() && this.running) this.finishRun('idle')
        }
      }
      this.streamAbort = sendPresentationMessage(this.spaceId, project.id, {
        content: finalContent,
        source_ids: sourceIds,
        expected_revision_id: this.selectedRevisionId || null
      }, streamCallbacks)
    },
    isPublishIntent(content) {
      return /(推送|发布).{0,20}(资料库|资料空间|课程|学生)|资料库.{0,20}(推送|发布)/i.test(String(content || ''))
    },
    failUnconfirmedPublishTool(message, terminalStatus) {
      if (!['completed', 'failed', 'cancelled'].includes(String(terminalStatus || '').toLowerCase())) return message
      const segments = (message.streamSegments || message.segments || []).map(segment => {
        if (segment.type !== 'tool' || !segment.toolCall?.optimistic) return segment
        return {
          ...segment,
          toolCall: {
            ...segment.toolCall,
            status: 'error',
            success: false,
            optimistic: false,
            error: terminalStatus === 'completed' ? '未收到发布工具的确认结果' : '发布任务未完成'
          }
        }
      })
      return { ...message, segments, streamSegments: segments }
    },
    resumeActiveRun(runId, existingMessageId = '', afterSequence = null) {
      if (!runId || this.streamAbort) return
      const existing = this.messages.find(message =>
        String(message.id) === String(existingMessageId)
        || String(message.runId || '') === String(runId)
      )
      const resumeCursor = Math.max(
        Number(existing?.streamSequence || 0),
        Number(afterSequence || 0)
      )
      const assistantMessage = existing
        ? { ...existing, runId: String(runId), streamSequence: resumeCursor, streaming: true, isStreaming: true, isThinking: true, recoverable: false, runStatus: 'recovering', runError: '' }
        : { ...createStreamingAgentMessage(`resumed-assistant-${runId}`), runId: String(runId), streamSequence: resumeCursor }
      if (existing) {
        this.messages = this.messages.map(message => message.id === existing.id ? assistantMessage : message)
      } else {
        this.messages = [...this.messages, assistantMessage]
      }
      this.running = true
      this.currentRunId = String(runId)
      this.progress = { phase: 'running', percent: 0, label: '正在恢复课件任务' }
      const streamContextVersion = this.contextVersion
      const streamSpaceId = this.spaceId
      const isCurrentStream = () => streamContextVersion === this.contextVersion && streamSpaceId === this.spaceId
      const updateAssistant = updater => {
        if (!isCurrentStream()) return
        this.messages = this.messages.map(message => message.id === assistantMessage.id
          ? updater({ ...message })
          : message)
      }
      const streamCallbacks = {
          onConnectionError: () => {
            if (isCurrentStream()) this.scheduleRunReconnect(this.selectedProjectId, assistantMessage.id, streamCallbacks, runId)
          },
          onThinkingDelta: (text, event = {}) => updateAssistant(message => applyAgentStreamEvent(
            message,
            'thinking_delta',
            { ...event, content: text }
          )),
          onTextDelta: (text, event = {}) => updateAssistant(message => applyAgentStreamEvent(
            message,
            'text_delta',
            { ...event, content: text }
          )),
          onToolCall: event => {
            if (!isCurrentStream()) return
            updateAssistant(message => {
              const tool = event.tool || event.name
              const hasOptimistic = message.streamSegments?.some(segment =>
                segment.type === 'tool' && segment.toolCall?.optimistic && segment.toolCall?.tool === tool
              )
              const base = hasOptimistic
                ? {
                    ...message,
                    streamSegments: message.streamSegments.filter(segment =>
                      !(segment.type === 'tool' && segment.toolCall?.optimistic)
                    ),
                    segments: message.segments.filter(segment =>
                      !(segment.type === 'tool' && segment.toolCall?.optimistic)
                    )
                  }
                : message
              return applyAgentStreamEvent(base, 'tool_call', {
                ...event,
                id: event.tool_call_id || event.id || `${tool || 'tool'}-${Date.now()}`
              })
            })
            this.updateToolProgress(event)
          },
          onProgress: event => {
            if (!isCurrentStream()) return
            this.progress = {
              ...event,
              phase: event.phase || event.stage || this.progress.phase,
              percent: Number(event.percent ?? event.progress ?? this.progress.percent ?? 0),
              label: event.label || event.message || ''
            }
          },
          onRevision: event => { if (isCurrentStream()) this.handleRevisionEvent(event) },
          onReady: event => { if (isCurrentStream()) this.handleRevisionEvent(event, true) },
          onDone: event => {
            if (!isCurrentStream()) return
            const status = String(event?.status || 'completed').toLowerCase()
            const artifactReady = event?.artifact_ready !== false
            updateAssistant(message => {
              let next = this.failUnconfirmedPublishTool(message, status)
              if (!next.content && !next.streamSegments?.length) {
                next = appendAgentText(next, status === 'completed'
                  ? artifactReady ? '课件已经完成。' : '可以继续告诉我你的课件需求。'
                  : '任务未完成。')
              }
              return finalizeAgentMessage(next, event)
            })
            this.finishRun(artifactReady ? status : 'idle')
            if (status === 'completed' && artifactReady) {
              this.refreshRevisions(event?.revision_id || event?.revisionId || '').catch(() => {})
            }
          },
          onError: (message, event = {}) => {
            if (!isCurrentStream()) return
            updateAssistant(item => ({
              ...finalizeAgentMessage(
                item.content || item.streamSegments?.length ? item : appendAgentText(item, `任务未完成：${message}`),
                { status: 'failed' }
              ),
              runId: item.runId || String(runId),
              recoverable: event.retryable !== false,
              runStatus: 'failed',
              runError: message
            }))
            this.finishRun('failed')
          },
          onComplete: () => {
            if (isCurrentStream() && this.running) this.finishRun('idle')
          }
        }
      this.streamAbort = resumePresentationRun(
        this.spaceId,
        this.selectedProjectId,
        runId,
        resumeCursor,
        streamCallbacks
      )
    },
    async resumeFailedRun(message) {
      if (this.running || !message?.runId || !this.selectedProjectId) return
      try {
        const resumed = await restartPresentationRun(this.spaceId, this.selectedProjectId, message.runId)
        this.updateProjectStatus(this.selectedProjectId, 'recovering')
        this.resumeActiveRun(message.runId, message.id, resumed.lastSequence)
      } catch (error) {
        this.showError(error, '无法恢复课件任务')
      }
    },
    scheduleRunReconnect(projectId, assistantMessageId, callbacks, hintedRunId = '') {
      if (!this.running || String(projectId) !== String(this.selectedProjectId)) return
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
      const delay = Math.min(5000, 700 * (2 ** Math.min(this.reconnectAttempts, 3)))
      this.progress = { ...this.progress, label: '连接中断，正在恢复任务' }
      this.reconnectTimer = setTimeout(async () => {
        this.reconnectTimer = null
        if (!this.running || String(projectId) !== String(this.selectedProjectId)) return
        let runId = String(hintedRunId || this.currentRunId || '')
        if (!runId) {
          try {
            const project = await getPresentationProject(this.spaceId, projectId)
            this.upsertProject(project)
            runId = String(project.activeRunId || '')
          } catch (_) {}
        }
        if (!runId) {
          this.reconnectAttempts += 1
          this.scheduleRunReconnect(projectId, assistantMessageId, callbacks, hintedRunId)
          return
        }
        const message = this.messages.find(item => item.id === assistantMessageId)
        if (!message?.streaming) return
        this.currentRunId = runId
        this.reconnectAttempts += 1
        this.streamAbort = resumePresentationRun(
          this.spaceId,
          projectId,
          runId,
          Number(message.streamSequence || 0),
          callbacks
        )
      }, delay)
    },
    updateToolProgress(event = {}) {
      if (String(event.status || '').toLowerCase() !== 'running') return
      const tool = String(event.tool || event.name || '')
      const stages = {
        get_course_graph_overview: ['preparing', 10, '正在读取课程知识图谱'],
        list_documents: ['preparing', 12, '正在读取课程资料'],
        search_keywords: ['preparing', 15, '正在检索课程内容'],
        read_document: ['preparing', 18, '正在阅读课程资料'],
        read_skill_resource: ['planning', 22, '正在读取课件技能规范'],
        load_workspace_dependencies: ['planning', 25, '正在准备课件运行环境'],
        read_file: ['building', 32, '正在检查课件工作文件'],
        write_file: ['building', 40, '正在编写课件构建脚本'],
        apply_patch: ['building', 50, '正在修改课件构建脚本'],
        generate_image: ['generating_assets', 55, '正在生成课件配图'],
        execute_command: ['building', 62, '正在构建或渲染课件'],
        view_image: ['validating', 82, '正在逐页检查课件'],
        publish_presentation_to_space: ['completed', 95, '正在准备发布课件']
      }
      const stage = stages[tool]
      if (!stage) return
      this.progress = {
        ...this.progress,
        phase: stage[0],
        percent: Math.max(Number(this.progress.percent || 0), stage[1]),
        label: stage[2]
      }
    },
    async handleRevisionEvent(event, ready = false) {
      const raw = event?.revision || event
      const revision = normalizePresentationRevision(raw)
      const revisionId = revision.id || String(event?.revision_id || event?.revisionId || '')
      if (revision.id) {
        this.revisions = this.sortRevisions([revision, ...this.revisions.filter(item => item.id !== revision.id)])
      }
      if (revisionId) {
        this.selectedRevisionId = revisionId
        if (ready) {
          this.selectedSlide = 1
          await this.refreshRevisions(revisionId)
          this.mobilePane = 'preview'
        }
      }
    },
    finishRun(status) {
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
      this.reconnectAttempts = 0
      this.running = false
      this.streamAbort = null
      this.progress = status === 'completed' ? { phase: 'completed', percent: 100, label: '课件已完成' } : {}
      if (this.selectedProjectId) this.updateProjectStatus(this.selectedProjectId, status === 'failed' ? 'failed' : 'idle')
      this.currentRunId = ''
    },
    async cancelRun() {
      if (!this.running) return
      try {
        if (this.currentRunId) await cancelPresentationRun(this.spaceId, this.selectedProjectId, this.currentRunId)
        this.streamAbort?.()
        this.messages = this.messages.map(message => message.streaming
          ? finalizeAgentMessage(
              message.content || message.streamSegments?.length ? message : appendAgentText(message, '任务已停止。'),
              { status: 'cancelled' }
            )
          : message)
        this.finishRun('cancelled')
      } catch (error) {
        this.showError(error, '停止任务失败')
      }
    },
    confirmRestore() {
      if (!this.selectedRevision || this.actionBusy) return
      uni.showModal({
        title: '恢复这个版本？',
        content: '系统会将该版本设为当前版本，已有历史不会被删除。',
        confirmText: '恢复',
        success: async result => { if (result.confirm) await this.restoreRevision() }
      })
    },
    async restoreRevision() {
      this.actionBusy = true
      try {
        const payload = await restorePresentationRevision(this.spaceId, this.selectedProjectId, this.selectedRevisionId)
        const revisionId = payload?.revision_id || payload?.revision?.id || ''
        await this.refreshRevisions(String(revisionId || ''))
        uni.showToast({ title: '已恢复为新版本', icon: 'success' })
      } catch (error) {
        this.showError(error, '版本恢复失败')
      } finally {
        this.actionBusy = false
      }
    },
    async downloadRevision() {
      if (!this.selectedRevision || this.actionBusy) return
      this.actionBusy = true
      try {
        const { blob, filename } = await fetchPresentationDownload(this.spaceId, this.selectedProjectId, this.selectedRevisionId)
        // #ifdef H5
        const objectUrl = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = objectUrl
        anchor.download = filename
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
        // #endif
      } catch (error) {
        this.showError(error, '下载失败')
      } finally {
        this.actionBusy = false
      }
    },
    confirmPublish() {
      if (!this.selectedRevision || this.actionBusy) return
      const replacing = !!this.selectedProject?.publishedDocumentId || this.selectedRevision.isPublished || this.revisions.some(revision => revision.isPublished)
      uni.showModal({
        title: replacing ? '更新课程资料？' : '发布到课程资料？',
        content: replacing
          ? '将用当前版本更新资料库中的同一份课件，并重新建立学生可检索内容。'
          : `发布后，学生可以在“${this.selectedSpaceName}”资料库中查看并在学习对话中检索这份课件。`,
        confirmText: replacing ? '确认更新' : '确认发布',
        success: async result => { if (result.confirm) await this.publishRevision() }
      })
    },
    async publishRevision() {
      this.actionBusy = true
      try {
        await publishPresentationRevision(
          this.spaceId,
          this.selectedProjectId,
          this.selectedRevisionId,
          this.selectedProject?.title || '教学课件'
        )
        this.revisions = this.revisions.map(revision => revision.id === this.selectedRevisionId
          ? { ...revision, isPublished: true, publishedAt: new Date().toISOString() }
          : revision)
        uni.showToast({ title: '已发布到课程资料库', icon: 'success' })
      } catch (error) {
        this.showError(error, '发布失败，资料库未发生变化')
      } finally {
        this.actionBusy = false
      }
    },
    upsertProject(project) {
      if (!project?.id) return
      const index = this.projects.findIndex(item => item.id === project.id)
      if (index < 0) this.projects = [project, ...this.projects]
      else this.projects = this.projects.map(item => item.id === project.id ? { ...item, ...project } : item)
    },
    updateProjectStatus(projectId, status) {
      this.projects = this.projects.map(project => project.id === projectId ? { ...project, status } : project)
    },
    openStudySpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${encodeURIComponent(spaceId)}` })
    },
    showError(error, fallback) {
      const message = error?.message || error?.data?.detail || fallback
      uni.showToast({ title: typeof message === 'string' ? message : fallback, icon: 'none' })
    }
  }
}
</script>

<style scoped>
.assistant-page { width: 100vw; height: 100vh; display: flex; overflow: hidden; position: relative; color: #f8fafc; background: var(--color-bg); }
.ambient { position: absolute; border-radius: 50%; pointer-events: none; will-change: transform; }
.ambient-one { width: 760px; height: 760px; left: -10%; top: -28%; background: radial-gradient(circle, rgba(59,130,246,.32) 0%, rgba(59,130,246,.12) 45%, transparent 75%); filter: blur(90px); animation: aurora-drift-a 12s ease-in-out infinite; }
.ambient-two { width: 620px; height: 620px; right: -12%; top: 8%; background: radial-gradient(circle, rgba(249,115,22,.22) 0%, rgba(249,115,22,.09) 45%, transparent 75%); filter: blur(70px); animation: aurora-drift-b 10s ease-in-out infinite; }
.assistant-page::after { content: ''; position: absolute; z-index: 0; width: 700px; height: 700px; left: 28%; bottom: -34%; border-radius: 50%; background: radial-gradient(circle, rgba(79,70,229,.2) 0%, rgba(79,70,229,.08) 45%, transparent 75%); filter: blur(90px); pointer-events: none; animation: aurora-drift-c 14s ease-in-out infinite; }
.assistant-workspace { flex: 1; min-width: 0; height: 100vh; display: flex; flex-direction: column; position: relative; z-index: 1; }
.assistant-topbar { min-height: 76px; padding: 12px 22px 11px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; gap: 20px; border-bottom: 1px solid rgba(255,255,255,.1); background: rgba(24,24,37,.34); backdrop-filter: blur(20px); }
.assistant-context-copy { display: flex; flex-direction: column; gap: 4px; }
.assistant-eyebrow { color: #60a5fa; font-size: 9px; font-weight: 700; letter-spacing: .13em; }
.assistant-title { color: #f8fafc; font-size: 20px; font-weight: 650; }
.workspace-grid { width: 100%; flex: 1; min-height: 0; display: grid; grid-template-columns: 250px minmax(350px, .88fr) minmax(430px, 1.24fr); }
.rail-column, .chat-column, .preview-column { min-width: 0; min-height: 0; border-right: 1px solid rgba(255,255,255,.12); }
.preview-column { border-right: 0; }
.mobile-bar, .rail-backdrop { display: none; }
@media (max-width: 1180px) {
  .workspace-grid { grid-template-columns: 215px minmax(330px, .9fr) minmax(390px, 1.1fr); }
}
@media (max-width: 900px) {
  .assistant-page :deep(.sidebar) { display: none; }
  .assistant-workspace { height: 100svh; }
  .assistant-topbar { min-height: 62px; padding: 7px 12px; }
  .assistant-context-copy { display: none; }
  .assistant-topbar :deep(.teacher-space-selector) { width: 100%; }
  .mobile-bar { z-index: 20; height: 54px; display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; padding: 0 12px; box-sizing: border-box; border-bottom: 1px solid rgba(255,255,255,.12); background: rgba(24,24,37,.72); backdrop-filter: blur(20px); }
  .mobile-project-button { min-width: 0; display: flex; align-items: center; gap: 8px; color: rgba(255,255,255,.74); font-size: 12px; }
  .mobile-project-button svg { width: 18px; height: 18px; flex-shrink: 0; }
  .mobile-project-button text { max-width: 42vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mobile-tabs { display: flex; padding: 3px; border-radius: 8px; background: rgba(255,255,255,.05); }
  .mobile-tabs view { padding: 5px 10px; border-radius: 6px; color: rgba(255,255,255,.38); font-size: 10px; }
  .mobile-tabs view.active { color: #dbe7ff; background: rgba(126,168,255,.14); }
  .workspace-grid { display: block; position: relative; height: 100%; }
  .rail-column { position: fixed; z-index: 40; left: 0; top: 0; bottom: 0; width: min(84vw, 310px); transform: translateX(-102%); transition: transform .24s ease; box-shadow: 20px 0 60px rgba(0,0,0,.35); }
  .rail-column.open { transform: translateX(0); }
  .rail-backdrop { display: block; position: fixed; z-index: 35; inset: 0; background: rgba(0,0,0,.55); animation: fade-in .18s ease; }
  .chat-column, .preview-column { width: 100%; height: 100%; border: 0; }
  .mobile-hidden { display: none; }
}
@keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes aurora-drift-a { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(50px,35px) scale(1.06); } 66% { transform: translate(-25px,15px) scale(.97); } }
@keyframes aurora-drift-b { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(-40px,30px) scale(1.05); } 66% { transform: translate(20px,-25px) scale(.98); } }
@keyframes aurora-drift-c { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(30px,-35px) scale(1.07); } 66% { transform: translate(-20px,20px) scale(.96); } }
@media (prefers-reduced-motion: reduce) { .ambient { display: none; } .rail-column { transition: none; } }
</style>
