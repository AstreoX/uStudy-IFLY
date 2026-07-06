<template>
  <view class="kg-root">
    <!-- Canvas container (native canvas created programmatically to bypass uni-app wrapper) -->
    <view ref="canvasWrap" class="kg-canvas"></view>

    <!-- Minimap -->
    <view ref="minimapWrap" class="kg-minimap"></view>

    <!-- Node popup -->
    <view
      v-if="selectedNode"
      class="kg-popup"
      :style="popupStyle"
    >
      <view class="kg-popup-content">
        <text class="kg-popup-name">{{ selectedNode.label }}</text>
        <view class="kg-popup-mastery">
          <view
            v-if="selectedNode.mastery != null"
            class="kg-mastery-ring"
            :style="{ background: masteryRingGradient }"
          >
            <view class="kg-mastery-inner">
              <text class="kg-mastery-text">{{ selectedNode.mastery }}</text>
            </view>
          </view>
          <view v-else class="kg-unlearned-row">
            <svg viewBox="0 0 256 256" class="kg-lock-icon">
              <rect width="256" height="256" fill="none"/>
              <path d="M208,80H176V56a48,48,0,0,0-96,0V80H48A16,16,0,0,0,32,96V208a16,16,0,0,0,16,16H208a16,16,0,0,0,16-16V96A16,16,0,0,0,208,80Zm-80,84a12,12,0,1,1,12-12A12,12,0,0,1,128,164Zm32-84H96V56a32,32,0,0,1,64,0Z" fill="rgba(255,255,255,0.4)"/>
            </svg>
            <view class="kg-quick-learn-btn" @click.stop="handleQuickLearn">
              <text class="kg-quick-learn-text">快速学习</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 扩展按钮 -->
      <view
        class="kg-expand-btn"
        :class="{ 'kg-expand-btn--loading': isExpandingNode }"
        @click.stop="handleExpandNode"
      >
        <text v-if="!isExpandingNode" class="kg-expand-btn-text">扩展</text>
        <view v-else class="kg-expand-loading">
          <span class="kg-expand-btn-text">扩展中</span>
          <view class="kg-expand-dots">
            <span class="kg-expand-dot"></span>
            <span class="kg-expand-dot"></span>
            <span class="kg-expand-dot"></span>
          </view>
        </view>
      </view>

      <!-- 内联笔记预览 -->
      <view class="kg-notes-inline">
        <text v-if="nodeNotesLoading" class="kg-notes-hint">加载笔记...</text>
        <text v-else-if="nodeNotes.length === 0" class="kg-notes-hint">暂无笔记</text>
        <view v-else class="kg-notes-list">
          <view
            v-for="note in nodeNotes"
            :key="note.id"
            class="kg-notes-item"
            @click.stop="handleNoteClick(note)"
          >
            <text class="kg-notes-item-title">{{ getNoteTitle(note) }}</text>
            <text class="kg-notes-item-preview">{{ truncateContent(note.content) }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Note preview popup -->
    <view
      v-if="previewNote || previewNoteLoading || previewNoteError"
      class="kg-note-overlay"
      @click.self="closeNotePreview"
    >
      <view class="kg-note-preview" @click.stop>
        <!-- Header -->
        <view class="kg-note-preview-header">
          <text class="kg-note-preview-title">
            {{ previewNote ? getNoteTitle(previewNote) : '加载中...' }}
          </text>
          <view class="kg-note-preview-close" @click="closeNotePreview">
            <text class="kg-note-preview-close-icon">×</text>
          </view>
        </view>

        <!-- Loading -->
        <view v-if="previewNoteLoading" class="kg-note-preview-status">
          <view class="kg-spinner"></view>
          <text class="kg-loading-text">加载笔记...</text>
        </view>

        <!-- Error -->
        <view v-else-if="previewNoteError" class="kg-note-preview-status">
          <text class="kg-note-preview-error-text">{{ previewNoteError }}</text>
        </view>

        <!-- Content -->
        <scroll-view v-else-if="previewNote" class="kg-note-preview-body" scroll-y>
          <view v-if="getPreviewNodeTag(previewNote)" class="kg-note-preview-tag">
            <text class="kg-note-preview-tag-text">{{ getPreviewNodeTag(previewNote) }}</text>
          </view>

          <view v-if="previewNote.content" class="kg-note-preview-content">
            <MarkdownRender :content="previewNote.content" />
          </view>
          <text v-else class="kg-note-preview-empty">（无内容）</text>

          <view
            v-if="previewNote.attachments && previewNote.attachments.length"
            class="kg-note-preview-attachments"
          >
            <text class="kg-note-preview-attach-label">附件</text>
            <view
              v-for="(att, idx) in previewNote.attachments"
              :key="att.id || idx"
              class="kg-note-preview-attach-item"
            >
              <text class="kg-note-preview-attach-name">{{ getPreviewAttachmentName(att) }}</text>
            </view>
          </view>

          <view class="kg-note-preview-meta">
            <text class="kg-note-preview-meta-text">创建于 {{ formatNoteDate(previewNote.created_at) }}</text>
            <text
              v-if="previewNote.updated_at && previewNote.updated_at !== previewNote.created_at"
              class="kg-note-preview-meta-text"
            >
              更新于 {{ formatNoteDate(previewNote.updated_at) }}
            </text>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- Loading state -->
    <view v-if="loading" class="kg-loading">
      <view class="kg-spinner"></view>
      <text class="kg-loading-text">Loading graph...</text>
    </view>

    <!-- Error state -->
    <view v-else-if="error" class="kg-error">
      <text class="kg-error-text">{{ error }}</text>
    </view>

    <!-- Generating state (async task in progress) -->
    <view v-else-if="generating && nodes.length === 0" class="kg-generating">
      <view class="kg-spinner"></view>
      <text class="kg-loading-text">正在生成知识图谱...</text>
      <text class="kg-loading-sub">这可能需要 10~30 秒</text>
    </view>

    <!-- Empty state -->
    <view v-else-if="nodes.length === 0" class="kg-empty">
      <text class="kg-empty-text">暂无知识图谱</text>
      <text class="kg-empty-sub">知识图谱尚未生成或生成失败</text>
      <view class="kg-retry-btn" @click="$emit('retry')">
        <text class="kg-retry-btn-text">重新生成</text>
      </view>
    </view>
  </view>
</template>

<script>
import { getSpaceGraph, getSpaceNotes, getNoteDetail, expandNode, getTaskStatus } from '@/api/space'
import { getMasteryColor, getMasteryGlowColor } from '@/utils/mastery-colors'
import {
  buildTreeFromEdges, computeLayout, getNodeBaseRadius,
  getLabelBoxByPosition, clamp,
  UNMASTERED_NODE_COLOR, UNMASTERED_NODE_GLOW, UNMASTERED_NODE_OUTLINE
} from '@/utils/graph-layout'
import {
  drawEdges, drawNode, drawNodeHighlight,
  drawPathHighlightRipple, drawAnimatedPathEdge,
  PATH_RIPPLE_DURATION, PATH_EDGE_GROW_DURATION
} from '@/utils/graph-renderer'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'

const FOREIGN_GRAPH_PATH_EDGE_ALPHA = 0.58

export default {
  components: {
    MarkdownRender
  },
  props: {
    spaceId: { type: [String, Number], default: null },
    pathHighlight: { type: Boolean, default: false },
    generating: { type: Boolean, default: false },
    targetUserId: { type: String, default: null },
    isForeignGraphView: { type: Boolean, default: false },
    pathColor: { type: String, default: '#0088FF' }
  },

  emits: ['node-selected', 'graph-loaded', 'retry', 'quick-learn', 'note-selected'],

  data() {
    return {
      loading: false,
      error: null,
      _loadGeneration: 0,
      nodes: [],
      edges: [],
      learningPath: [],
      childrenMap: new Map(),

      // Viewport
      scale: 1,
      offsetX: 0,
      offsetY: 0,
      canvasWidth: 0,
      canvasHeight: 0,
      dpr: 1,

      // Interaction state
      isDragging: false,
      lastMouseX: 0,
      lastMouseY: 0,
      dragDistance: 0,
      selectedNodeId: null,

      // Touch gesture state
      activeTouches: [],
      lastTouchDist: 0,
      lastTouchMidX: 0,
      lastTouchMidY: 0,
      touchStartTime: 0,
      lastTapTime: 0,
      lastTapX: 0,
      lastTapY: 0,

      // Caches
      nodeMap: new Map(),
      edgeBuckets: { treeEdges: [], advancedEdges: [], pathEdges: [], nonPathEdges: [] },
      learningPathSet: new Set(),
      visibleNodesCache: null,
      visibleNodeIdSetCache: new Set(),
      childCountCache: new Map(),

      // Highlight animation state
      highlightedNodes: new Map(),
      highlightAnimationRunning: false,

      // Path animation state
      pathAnimationRunning: false,
      pathAnimationNodes: [],
      pathAnimationStep: -1,
      pathRippleNodes: new Map(),
      pathAnimatedEdges: [],
      pathCompletedEdges: [],

      // Render throttling
      renderPending: false,
      ctx: null,

      // Minimap
      minimapWidth: 160,
      minimapHeight: 120,
      minimapPending: false,
      lastMinimapRenderAt: 0,
      isMinimapDragging: false,

      // Node notes
      nodeNotes: [],
      nodeNotesLoading: false,

      // Note preview popup
      previewNote: null,
      previewNoteLoading: false,
      previewNoteError: '',

      // 节点扩展状态
      isExpandingNode: false
    }
  },

  computed: {
    selectedNode() {
      if (!this.selectedNodeId) return null
      return this.nodeMap.get(this.selectedNodeId) || null
    },

    popupStyle() {
      if (!this.selectedNode) return {}
      const screenX = this.selectedNode.x * this.scale + this.offsetX
      const screenY = this.selectedNode.y * this.scale + this.offsetY
      const radius = getNodeBaseRadius(this.selectedNode)
      return {
        left: screenX + 'px',
        top: (screenY + (radius + 20) * this.scale) + 'px'
      }
    },

    masteryRingGradient() {
      if (!this.selectedNode || this.selectedNode.mastery == null) return ''
      const mastery = this.selectedNode.mastery || 0
      const color = getMasteryColor(mastery)
      const angle = (mastery / 100) * 360
      return `conic-gradient(${color} 0deg, ${color} ${angle}deg, rgba(255,255,255,0.1) ${angle}deg, rgba(255,255,255,0.1) 360deg)`
    }
  },

  watch: {
    spaceId(newVal) {
      if (newVal) this.loadAndRender()
    },
    targetUserId(newVal, oldVal) {
      if (newVal !== oldVal && this.spaceId) {
        this.loadAndRender()
      }
    },
    pathHighlight() {
      this.requestRender()
      this.requestMinimapRender(true)
    },
    async selectedNodeId(nodeId) {
      // Close note preview when node selection changes
      this.previewNote = null
      this.previewNoteLoading = false
      this.previewNoteError = ''

      if (!nodeId || !this.spaceId) {
        this.nodeNotes = []
        this.nodeNotesLoading = false
        return
      }
      this.nodeNotesLoading = true
      this.nodeNotes = []
      try {
        const notes = await getSpaceNotes(this.spaceId, { nodeId })
        if (this.selectedNodeId === nodeId) {
          this.nodeNotes = Array.isArray(notes) ? notes : []
        }
      } catch {
        if (this.selectedNodeId === nodeId) {
          this.nodeNotes = []
        }
      } finally {
        if (this.selectedNodeId === nodeId) {
          this.nodeNotesLoading = false
        }
      }
    }
  },

  mounted() {
    this.initCanvas()
    if (this.spaceId) this.loadAndRender()
    this._onKeyDown = (e) => {
      if (e.key === 'Escape' && (this.previewNote || this.previewNoteLoading || this.previewNoteError)) {
        this.closeNotePreview()
      }
    }
    window.addEventListener('keydown', this._onKeyDown)
  },

  beforeUnmount() {
    if (this._onKeyDown) {
      window.removeEventListener('keydown', this._onKeyDown)
      this._onKeyDown = null
    }
    this.highlightAnimationRunning = false
    this.highlightedNodes.clear()
    this.pathAnimationRunning = false
    this.pathRippleNodes.clear()
    if (this._pathStepTimer) {
      clearTimeout(this._pathStepTimer)
      this._pathStepTimer = null
    }
    if (this._pathEdgeGrowTimer) {
      clearTimeout(this._pathEdgeGrowTimer)
      this._pathEdgeGrowTimer = null
    }
    if (this._panRAF) {
      cancelAnimationFrame(this._panRAF)
      this._panRAF = null
    }

    if (this._resizeObserver) {
      this._resizeObserver.disconnect()
      this._resizeObserver = null
    }
    if (this._canvasEl) {
      this._canvasEl.removeEventListener('mousedown', this._onMouseDown)
      this._canvasEl.removeEventListener('mousemove', this._onMouseMove)
      this._canvasEl.removeEventListener('mouseup', this._onMouseUp)
      this._canvasEl.removeEventListener('mouseleave', this._onMouseUp)
      this._canvasEl.removeEventListener('dblclick', this._onDblClick)
      this._canvasEl.removeEventListener('wheel', this._onWheel)
      this._canvasEl.removeEventListener('touchstart', this._onTouchStart)
      this._canvasEl.removeEventListener('touchmove', this._onTouchMove)
      this._canvasEl.removeEventListener('touchend', this._onTouchEnd)
      this._canvasEl.removeEventListener('touchcancel', this._onTouchEnd)
      this._canvasEl.remove()
      this._canvasEl = null
    }
    if (this._minimapEl) {
      this._minimapEl.removeEventListener('mousedown', this._onMmDown)
      this._minimapEl.remove()
      this._minimapEl = null
    }
    window.removeEventListener('mousemove', this._onMmMove)
    window.removeEventListener('mouseup', this._onMmUp)
    this._minimapCtx = null
  },

  methods: {
    handleQuickLearn() {
      if (!this.selectedNode) return
      this.$emit('quick-learn', { node: this.selectedNode })
    },

    // ========== 节点扩展 ==========
    async handleExpandNode() {
      if (this.isExpandingNode || !this.selectedNode || !this.spaceId) return
      this.isExpandingNode = true

      const parentNode = this.selectedNode

      try {
        const res = await expandNode(this.spaceId, parentNode.id)
        const taskId = res.task_id

        // 轮询任务状态
        const task = await this._pollTaskUntilDone(taskId)

        // 重新拉取图谱数据
        const graphData = await getSpaceGraph(this.spaceId)
        if (!graphData || !graphData.nodes || graphData.nodes.length === 0) return

        await this.mergeExpandedNodes(graphData, parentNode)

        const nodeCount = task.node_count || 0
        if (nodeCount > 0) {
          // 通知父组件（可选）
          this.$emit('graph-loaded', { nodeCount: this.nodes.length, edgeCount: this.edges.length })
        }
      } catch (e) {
        console.error('节点扩展失败:', e)
      } finally {
        this.isExpandingNode = false
      }
    },

    async _pollTaskUntilDone(taskId) {
      const maxAttempts = 90 // 最多 3 分钟（每 2 秒一次）
      for (let i = 0; i < maxAttempts; i++) {
        const task = await getTaskStatus(taskId)
        if (task.status === 'done') return task
        if (task.status === 'failed') throw new Error(task.error_message || '节点扩展失败')
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
      throw new Error('节点扩展超时，请稍后重试')
    },

    async mergeExpandedNodes(newGraphData, parentNode) {
      const existingIds = new Set(this.nodes.map(n => n.id))

      const { nodes: rawNodes, edges: rawEdges } = newGraphData
      const { nodes: processedNodes, edges: processedEdges, learningPath, childrenMap } = buildTreeFromEdges(rawNodes, rawEdges)
      this.childrenMap = childrenMap

      // 识别新节点
      const addedNodes = processedNodes.filter(n => !existingIds.has(n.id))
      if (addedNodes.length === 0) return

      // 保留已有节点的当前位置
      processedNodes.forEach(n => {
        if (existingIds.has(n.id)) {
          const existing = this.nodeMap.get(n.id)
          if (existing) {
            n.x = existing.x
            n.y = existing.y
          }
        } else {
          // 新节点：起始位置 = 父节点位置
          n.x = parentNode.x
          n.y = parentNode.y
        }
      })

      // 更新数据
      this.nodes = processedNodes
      this.edges = processedEdges
      this.learningPath = learningPath

      // 重建缓存
      this.rebuildCaches()

      // 重新计算布局（确定新节点目标位置）
      computeLayout(this.nodes, this.canvasWidth, this.canvasHeight)

      // 记录新节点目标位置，并重置起始位置为父节点
      const addedIds = addedNodes.map(n => n.id)
      addedIds.forEach(id => {
        const node = this.nodeMap.get(id)
        if (!node) return
        node._expandTargetX = node.x
        node._expandTargetY = node.y
        node.x = parentNode.x
        node.y = parentNode.y
      })

      this.runExpandNodeAnimation(addedIds, parentNode)
    },

    runExpandNodeAnimation(newNodeIds, parentNode) {
      const startTime = Date.now()
      const duration = 600

      const animate = () => {
        const elapsed = Date.now() - startTime
        const t = Math.min(elapsed / duration, 1)
        const eased = 1 - Math.pow(1 - t, 3)

        newNodeIds.forEach(id => {
          const node = this.nodeMap.get(id)
          if (!node || node._expandTargetX === undefined) return
          node.x = parentNode.x + (node._expandTargetX - parentNode.x) * eased
          node.y = parentNode.y + (node._expandTargetY - parentNode.y) * eased
        })

        this.drawGraph()
        this.requestMinimapRender()

        if (t < 1) {
          requestAnimationFrame(animate)
        } else {
          newNodeIds.forEach(id => {
            const node = this.nodeMap.get(id)
            if (!node) return
            node.x = node._expandTargetX
            node.y = node._expandTargetY
            delete node._expandTargetX
            delete node._expandTargetY
          })
          this.drawGraph()
          this.requestMinimapRender(true)
        }
      }

      requestAnimationFrame(animate)
    },

    getNoteTitle(note) {
      const title = note?.title
      return typeof title === 'string' && title.trim() ? title.trim() : '未命名笔记'
    },

    truncateContent(content) {
      if (!content) return ''
      return content.length > 80 ? content.substring(0, 80) + '...' : content
    },

    async handleNoteClick(note) {
      this.$emit('note-selected', { note, nodeId: this.selectedNodeId })
      if (!note?.id || !this.spaceId) return

      const requestedId = note.id
      this._previewRequestId = requestedId
      this.previewNote = null
      this.previewNoteLoading = true
      this.previewNoteError = ''

      try {
        const detail = await getNoteDetail(this.spaceId, requestedId)
        if (this._previewRequestId === requestedId) {
          this.previewNote = detail
        }
      } catch (error) {
        if (this._previewRequestId === requestedId) {
          this.previewNoteError = error?.message || '加载笔记详情失败'
        }
      } finally {
        if (this._previewRequestId === requestedId) {
          this.previewNoteLoading = false
        }
      }
    },

    closeNotePreview() {
      this._previewRequestId = null
      this.previewNote = null
      this.previewNoteLoading = false
      this.previewNoteError = ''
    },

    getPreviewNodeTag(note) {
      return note?.node_label || ''
    },

    getPreviewAttachmentName(att) {
      if (!att) return '未命名附件'
      return att.link_title || att.original_filename || att.link_url || att.file_url || '未命名附件'
    },

    formatNoteDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      if (Number.isNaN(date.getTime())) return ''
      const month = date.getMonth() + 1
      const day = date.getDate()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${month}月${day}日 ${hours}:${minutes}`
    },

    getCanvas() {
      return this._canvasEl || null
    },

    // --- Canvas initialization ---
    initCanvas() {
      const wrap = this.$refs.canvasWrap
      if (!wrap) return
      const parentEl = wrap.$el || wrap

      // Create native canvas element to bypass uni-app's canvas component wrapper
      const canvas = document.createElement('canvas')
      canvas.style.display = 'block'
      canvas.style.width = '100%'
      canvas.style.height = '100%'
      canvas.style.cursor = 'grab'
      canvas.style.touchAction = 'none'
      parentEl.appendChild(canvas)
      this._canvasEl = canvas

      // Attach mouse events directly on native canvas
      this._onMouseDown = this.onMouseDown.bind(this)
      this._onMouseMove = this.onMouseMove.bind(this)
      this._onMouseUp = this.onMouseUp.bind(this)
      this._onDblClick = this.onDoubleClick.bind(this)
      this._onWheel = this.onWheel.bind(this)

      canvas.addEventListener('mousedown', this._onMouseDown)
      canvas.addEventListener('mousemove', this._onMouseMove)
      canvas.addEventListener('mouseup', this._onMouseUp)
      canvas.addEventListener('mouseleave', this._onMouseUp)
      canvas.addEventListener('dblclick', this._onDblClick)
      canvas.addEventListener('wheel', this._onWheel, { passive: false })

      // Touch events for iPad/touch devices
      this._onTouchStart = this.onTouchStart.bind(this)
      this._onTouchMove = this.onTouchMove.bind(this)
      this._onTouchEnd = this.onTouchEnd.bind(this)

      canvas.addEventListener('touchstart', this._onTouchStart, { passive: false })
      canvas.addEventListener('touchmove', this._onTouchMove, { passive: false })
      canvas.addEventListener('touchend', this._onTouchEnd)
      canvas.addEventListener('touchcancel', this._onTouchEnd)

      this.dpr = window.devicePixelRatio || 1
      this.resizeCanvas()

      // ResizeObserver on the container
      this._resizeObserver = new ResizeObserver(() => {
        this.resizeCanvas()
        this.requestRender()
      })
      this._resizeObserver.observe(parentEl)

      this.initMinimap()
    },

    resizeCanvas() {
      const canvas = this._canvasEl
      if (!canvas) return
      const parent = canvas.parentElement
      if (!parent) return

      this.dpr = window.devicePixelRatio || 1
      const rect = parent.getBoundingClientRect()
      this.canvasWidth = rect.width
      this.canvasHeight = rect.height

      canvas.width = rect.width * this.dpr
      canvas.height = rect.height * this.dpr
      canvas.style.width = rect.width + 'px'
      canvas.style.height = rect.height + 'px'

      this.ctx = canvas.getContext('2d')
      this.ctx.scale(this.dpr, this.dpr)
    },

    // --- Data loading ---
    async loadAndRender() {
      if (!this.spaceId) return
      const gen = ++this._loadGeneration
      this.loading = true
      this.error = null

      try {
        const { nodes: apiNodes, edges: apiEdges } = await getSpaceGraph(this.spaceId, this.targetUserId)
        if (gen !== this._loadGeneration) return // stale response, discard

        if (!apiNodes || apiNodes.length === 0) {
          this.nodes = []
          this.edges = []
          this.loading = false
          return
        }

        const { nodes, edges, learningPath, childrenMap } = buildTreeFromEdges(apiNodes, apiEdges)
        this.nodes = nodes
        this.edges = edges
        this.learningPath = learningPath
        this.childrenMap = childrenMap

        // Compute layout
        computeLayout(this.nodes, this.canvasWidth, this.canvasHeight)

        // Build caches
        this.rebuildCaches()

        // Center viewport
        this.resetViewportToGraphCenter()

        // Render
        this.drawGraph()
        this.requestMinimapRender(true)

        this.$emit('graph-loaded', { nodeCount: nodes.length, edgeCount: edges.length })
      } catch (err) {
        this.error = err.message || 'Failed to load graph'
      } finally {
        this.loading = false
      }
    },

    // --- Cache building ---
    rebuildCaches() {
      // Node map
      this.nodeMap = new Map()
      this.nodes.forEach(n => this.nodeMap.set(n.id, n))

      // Edge buckets
      this.edgeBuckets = { treeEdges: [], advancedEdges: [], pathEdges: [], nonPathEdges: [] }
      this.edges.forEach(edge => {
        const fromNode = this.nodeMap.get(edge.from) || null
        const toNode = this.nodeMap.get(edge.to) || null
        const linked = { ...edge, fromNode, toNode }

        if (edge.type === 'knowledge_tree' || !edge.type) {
          this.edgeBuckets.treeEdges.push(linked)
        }
        if (edge.type === 'advanced') {
          this.edgeBuckets.advancedEdges.push(linked)
        }
        if (edge.type === 'learning_path') {
          this.edgeBuckets.pathEdges.push(linked)
        } else {
          this.edgeBuckets.nonPathEdges.push(linked)
        }
      })

      // Learning path set
      this.learningPathSet = new Set(this.learningPath)

      // Node style cache
      this.nodes.forEach(node => {
        node.baseRadius = getNodeBaseRadius(node)
        if (node.mastery == null) {
          node.fillColor = UNMASTERED_NODE_COLOR
          node.glowColor = UNMASTERED_NODE_GLOW
          node.outlineColor = UNMASTERED_NODE_OUTLINE
        } else {
          node.fillColor = getMasteryColor(node.mastery)
          node.glowColor = getMasteryGlowColor(node.mastery, 0.5)
          node.outlineColor = getMasteryGlowColor(node.mastery, 0.2)
        }
      })

      // Child count cache (iterative approach using childrenMap to avoid stack overflow)
      this.childCountCache = new Map()
      const countDescendants = (nodeId) => {
        let count = 0
        const stack = [...(this.childrenMap.get(nodeId) || [])]
        while (stack.length > 0) {
          const childId = stack.pop()
          count++
          const grandchildren = this.childrenMap.get(childId)
          if (grandchildren) stack.push(...grandchildren)
        }
        return count
      }
      this.nodes.forEach(n => {
        const count = countDescendants(n.id)
        n.childCount = count
        this.childCountCache.set(n.id, count)
      })

      // Visible nodes
      this.updateVisibleNodesCache()
    },

    updateVisibleNodesCache() {
      const MAX_DEPTH = 100  // Safety limit to prevent stack overflow from cycles
      this.visibleNodesCache = this.nodes.filter(node => {
        let parent = node.parent ? this.nodeMap.get(node.parent) : null
        const visited = new Set()
        let depth = 0
        while (parent && depth < MAX_DEPTH) {
          if (visited.has(parent.id)) {
            console.warn(`[KnowledgeGraph] Cycle detected in parent chain: ${node.id} -> ${parent.id}`)
            return true  // Show node if cycle detected (fail-safe)
          }
          visited.add(parent.id)
          if (parent.collapsed) return false
          parent = parent.parent ? this.nodeMap.get(parent.parent) : null
          depth++
        }
        return true
      })
      this.visibleNodeIdSetCache = new Set(this.visibleNodesCache.map(n => n.id))
    },

    getVisibleNodes() {
      if (this.visibleNodesCache) return this.visibleNodesCache
      this.updateVisibleNodesCache()
      return this.visibleNodesCache
    },

    // --- Viewport ---
    getGraphBounds() {
      if (this.nodes.length === 0) return { minX: 0, maxX: 100, minY: 0, maxY: 100 }

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
      this.nodes.forEach(node => {
        const radius = getNodeBaseRadius(node)
        minX = Math.min(minX, node.x - radius)
        maxX = Math.max(maxX, node.x + radius)
        minY = Math.min(minY, node.y - radius)
        maxY = Math.max(maxY, node.y + radius)

        if (node.labelBox) {
          minX = Math.min(minX, node.labelBox.x)
          maxX = Math.max(maxX, node.labelBox.x + node.labelBox.width)
          minY = Math.min(minY, node.labelBox.y)
          maxY = Math.max(maxY, node.labelBox.y + node.labelBox.height)
        }
      })

      if (maxX - minX < 1) maxX = minX + 100
      if (maxY - minY < 1) maxY = minY + 100
      return { minX, maxX, minY, maxY }
    },

    resetViewportToGraphCenter() {
      const bounds = this.getGraphBounds()
      const centerX = (bounds.minX + bounds.maxX) / 2
      const centerY = (bounds.minY + bounds.maxY) / 2
      const graphWidth = bounds.maxX - bounds.minX
      const graphHeight = bounds.maxY - bounds.minY

      // Fit the graph in the viewport with some padding
      const padding = 40
      const scaleX = (this.canvasWidth - padding * 2) / graphWidth
      const scaleY = (this.canvasHeight - padding * 2) / graphHeight
      this.scale = clamp(Math.min(scaleX, scaleY), 0.3, 3)

      this.offsetX = this.canvasWidth / 2 - centerX * this.scale
      this.offsetY = this.canvasHeight / 2 - centerY * this.scale
    },

    getViewportBounds(padding = 96) {
      const safeScale = Math.max(0.0001, this.scale || 1)
      const p = padding / safeScale
      return {
        minX: (0 - this.offsetX) / safeScale - p,
        maxX: (this.canvasWidth - this.offsetX) / safeScale + p,
        minY: (0 - this.offsetY) / safeScale - p,
        maxY: (this.canvasHeight - this.offsetY) / safeScale + p
      }
    },

    isNodeInViewport(node, bounds) {
      const radius = getNodeBaseRadius(node)
      if (node.x + radius >= bounds.minX && node.x - radius <= bounds.maxX &&
          node.y + radius >= bounds.minY && node.y - radius <= bounds.maxY) return true
      if (node.labelBox) {
        return !(node.labelBox.x > bounds.maxX || node.labelBox.x + node.labelBox.width < bounds.minX ||
                 node.labelBox.y > bounds.maxY || node.labelBox.y + node.labelBox.height < bounds.minY)
      }
      return false
    },

    // --- Drawing ---
    requestRender() {
      if (this.renderPending) return
      this.renderPending = true
      requestAnimationFrame(() => {
        this.renderPending = false
        this.drawGraph()
      })
    },

    drawGraph() {
      if (!this.ctx) return
      const ctx = this.ctx
      const visibleNodes = this.getVisibleNodes()
      const viewportBounds = this.getViewportBounds(120)
      const renderNodes = visibleNodes.filter(n => this.isNodeInViewport(n, viewportBounds))
      const renderNodeIds = new Set(renderNodes.map(n => n.id))

      // Reset transform and clear
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
      ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)

      // Apply viewport transform
      ctx.save()
      ctx.translate(this.offsetX, this.offsetY)
      ctx.scale(this.scale, this.scale)

      // Draw edges
      drawEdges(ctx, this.edgeBuckets, {
        isPathHighlightOn: this.pathHighlight,
        visibleNodeIds: this.visibleNodeIdSetCache,
        viewportNodeIds: renderNodeIds,
        showAdvancedEdges: true,
        isForeignGraphView: this.isForeignGraphView,
        pathColor: this.pathColor
      })

      // Draw path animation edges (completed + in-progress)
      if (this.pathAnimationRunning) {
        const now = Date.now()
        ctx.save()
        ctx.globalAlpha = this.isForeignGraphView ? FOREIGN_GRAPH_PATH_EDGE_ALPHA : 1
        this.pathCompletedEdges.forEach(edge => {
          if (edge.from && edge.to) {
            drawAnimatedPathEdge(ctx, edge.from, edge.to, 1.0, this.pathColor)
          }
        })
        this.pathAnimatedEdges.forEach(edge => {
          if (edge.from && edge.to) {
            const elapsed = now - edge.startTime
            const t = Math.min(1, elapsed / PATH_EDGE_GROW_DURATION)
            const progress = 1 - Math.pow(1 - t, 3)
            drawAnimatedPathEdge(ctx, edge.from, edge.to, progress, this.pathColor)
          }
        })
        ctx.restore()
      }

      // Draw nodes (apply highlight color override if active)
      renderNodes.forEach(node => {
        const hlState = this.highlightedNodes.get(node.id)
        let savedFill, savedGlow
        if (node._highlightFillOverride) {
          savedFill = node.fillColor
          savedGlow = node.glowColor
          node.fillColor = node._highlightFillOverride
          node.glowColor = node._highlightGlowOverride || node.glowColor
        }

        drawNode(ctx, node, {
          selectedNodeId: this.selectedNodeId,
          isPathHighlightOn: this.pathHighlight,
          learningPathSet: this.learningPathSet,
          isForeignGraphView: this.isForeignGraphView,
          pathColor: this.pathColor
        })

        if (savedFill) {
          node.fillColor = savedFill
          node.glowColor = savedGlow
        }

        // Draw highlight ripple rings on top
        if (hlState) {
          drawNodeHighlight(ctx, node, hlState)
        }

        // Draw path animation ripples on top
        if (this.pathAnimationRunning) {
          const rippleState = this.pathRippleNodes.get(node.id)
          if (rippleState) {
            drawPathHighlightRipple(ctx, node, rippleState, this.pathColor)
          }
        }
      })

      ctx.restore()
      this.requestMinimapRender()
    },

    // --- Mouse interactions ---
    onMouseDown(e) {
      this.isDragging = true
      this.dragDistance = 0
      this.lastMouseX = e.clientX
      this.lastMouseY = e.clientY
      if (this._canvasEl) this._canvasEl.style.cursor = 'grabbing'
    },

    onMouseMove(e) {
      if (!this.isDragging) return

      const deltaX = e.clientX - this.lastMouseX
      const deltaY = e.clientY - this.lastMouseY
      this.dragDistance += Math.abs(deltaX) + Math.abs(deltaY)

      this.offsetX += deltaX
      this.offsetY += deltaY
      this.lastMouseX = e.clientX
      this.lastMouseY = e.clientY

      this.requestRender()
    },

    onMouseUp(e) {
      if (!this.isDragging) return
      this.isDragging = false
      if (this._canvasEl) this._canvasEl.style.cursor = 'grab'

      // If drag distance is small, treat as click
      if (this.dragDistance < 10) {
        this.handleClick(e)
      }
    },

    handleClick(e) {
      const canvas = this._canvasEl
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const screenX = e.clientX - rect.left
      const screenY = e.clientY - rect.top

      const node = this.findNodeAtPosition(screenX, screenY)
      if (node) {
        if (this.selectedNodeId === node.id) {
          this.selectedNodeId = null
          this.$emit('node-selected', null)
        } else {
          this.selectedNodeId = node.id
          this.$emit('node-selected', { node })
        }
      } else {
        this.selectedNodeId = null
        this.$emit('node-selected', null)
      }
      this.requestRender()
    },

    onDoubleClick(e) {
      const canvas = this._canvasEl
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const screenX = e.clientX - rect.left
      const screenY = e.clientY - rect.top

      const node = this.findNodeAtPosition(screenX, screenY)
      if (node && node.childCount > 0) {
        node.collapsed = !node.collapsed
        this.updateVisibleNodesCache()
        this.requestRender()
        this.requestMinimapRender(true)
      }
    },

    onWheel(e) {
      e.preventDefault()

      const zoomSensitivity = 0.001
      const delta = -e.deltaY * zoomSensitivity
      const newScale = clamp(this.scale * (1 + delta), 0.3, 3)

      const canvas = this._canvasEl
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const mouseX = e.clientX - rect.left
      const mouseY = e.clientY - rect.top

      // Zoom centered on cursor
      const scaleRatio = newScale / this.scale
      this.offsetX = mouseX - (mouseX - this.offsetX) * scaleRatio
      this.offsetY = mouseY - (mouseY - this.offsetY) * scaleRatio
      this.scale = newScale

      this.requestRender()
    },

    // --- Touch interactions ---
    onTouchStart(e) {
      e.preventDefault()
      const touches = e.touches
      this.activeTouches = Array.from(touches).map(t => ({ id: t.identifier, x: t.clientX, y: t.clientY }))

      if (touches.length === 1) {
        this.isDragging = true
        this.dragDistance = 0
        this.lastMouseX = touches[0].clientX
        this.lastMouseY = touches[0].clientY
        this.touchStartTime = Date.now()
      } else if (touches.length === 2) {
        this.isDragging = false
        const dx = touches[1].clientX - touches[0].clientX
        const dy = touches[1].clientY - touches[0].clientY
        this.lastTouchDist = Math.sqrt(dx * dx + dy * dy)
        this.lastTouchMidX = (touches[0].clientX + touches[1].clientX) / 2
        this.lastTouchMidY = (touches[0].clientY + touches[1].clientY) / 2
      }
    },

    onTouchMove(e) {
      e.preventDefault()
      const touches = e.touches

      if (touches.length === 1 && this.isDragging) {
        const deltaX = touches[0].clientX - this.lastMouseX
        const deltaY = touches[0].clientY - this.lastMouseY
        this.dragDistance += Math.abs(deltaX) + Math.abs(deltaY)

        this.offsetX += deltaX
        this.offsetY += deltaY
        this.lastMouseX = touches[0].clientX
        this.lastMouseY = touches[0].clientY

        this.requestRender()
      } else if (touches.length === 2) {
        const dx = touches[1].clientX - touches[0].clientX
        const dy = touches[1].clientY - touches[0].clientY
        const newDist = Math.sqrt(dx * dx + dy * dy)
        const midX = (touches[0].clientX + touches[1].clientX) / 2
        const midY = (touches[0].clientY + touches[1].clientY) / 2

        if (this.lastTouchDist > 0) {
          // Pinch-to-zoom centered on midpoint
          const canvas = this._canvasEl
          if (!canvas) return
          const rect = canvas.getBoundingClientRect()
          const canvasMidX = midX - rect.left
          const canvasMidY = midY - rect.top

          const scaleRatio = newDist / this.lastTouchDist
          const newScale = clamp(this.scale * scaleRatio, 0.3, 3)
          const actualRatio = newScale / this.scale

          this.offsetX = canvasMidX - (canvasMidX - this.offsetX) * actualRatio
          this.offsetY = canvasMidY - (canvasMidY - this.offsetY) * actualRatio
          this.scale = newScale
        }

        // Pan by midpoint movement
        this.offsetX += midX - this.lastTouchMidX
        this.offsetY += midY - this.lastTouchMidY

        this.lastTouchDist = newDist
        this.lastTouchMidX = midX
        this.lastTouchMidY = midY

        this.requestRender()
      }
    },

    onTouchEnd(e) {
      const prevTouchCount = this.activeTouches.length
      const remainingTouches = e.touches

      // Single-finger lift: check for tap / double-tap
      if (prevTouchCount === 1 && remainingTouches.length === 0) {
        const elapsed = Date.now() - this.touchStartTime
        if (this.dragDistance < 10 && elapsed < 300) {
          const touch = this.activeTouches[0]
          const now = Date.now()

          // Double-tap detection
          if (now - this.lastTapTime < 300 &&
              Math.abs(touch.x - this.lastTapX) < 30 &&
              Math.abs(touch.y - this.lastTapY) < 30) {
            this.handleTouchDoubleTap(touch.x, touch.y)
            this.lastTapTime = 0
          } else {
            this.handleTouchTap(touch.x, touch.y)
            this.lastTapTime = now
            this.lastTapX = touch.x
            this.lastTapY = touch.y
          }
        }
      }

      // Reset state
      this.isDragging = false
      this.activeTouches = Array.from(remainingTouches).map(t => ({ id: t.identifier, x: t.clientX, y: t.clientY }))

      // If going from 2 fingers to 1, restart single-finger pan
      if (remainingTouches.length === 1) {
        this.isDragging = true
        this.dragDistance = 0
        this.lastMouseX = remainingTouches[0].clientX
        this.lastMouseY = remainingTouches[0].clientY
      }
    },

    handleTouchTap(clientX, clientY) {
      const canvas = this._canvasEl
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const screenX = clientX - rect.left
      const screenY = clientY - rect.top

      const node = this.findNodeAtPosition(screenX, screenY)
      if (node) {
        if (this.selectedNodeId === node.id) {
          this.selectedNodeId = null
          this.$emit('node-selected', null)
        } else {
          this.selectedNodeId = node.id
          this.$emit('node-selected', { node })
        }
      } else {
        this.selectedNodeId = null
        this.$emit('node-selected', null)
      }
      this.requestRender()
    },

    handleTouchDoubleTap(clientX, clientY) {
      const canvas = this._canvasEl
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const screenX = clientX - rect.left
      const screenY = clientY - rect.top

      const node = this.findNodeAtPosition(screenX, screenY)
      if (node && node.childCount > 0) {
        node.collapsed = !node.collapsed
        this.updateVisibleNodesCache()
        this.requestRender()
        this.requestMinimapRender(true)
      }
    },

    findNodeAtPosition(screenX, screenY) {
      const graphX = (screenX - this.offsetX) / this.scale
      const graphY = (screenY - this.offsetY) / this.scale

      const visibleNodes = this.getVisibleNodes()

      // Hit-test circles first
      for (const node of visibleNodes) {
        const radius = getNodeBaseRadius(node)
        const hitRadius = radius + 15
        const dx = graphX - node.x
        const dy = graphY - node.y
        if (dx * dx + dy * dy <= hitRadius * hitRadius) return node
      }

      // Then hit-test label boxes
      for (const node of visibleNodes) {
        const box = node.labelBox
        if (!box) continue
        if (graphX >= box.x && graphX <= box.x + box.width &&
            graphY >= box.y && graphY <= box.y + box.height) return node
      }

      return null
    },

    // --- Mastery highlight animation ---
    highlightNode(nodeName, newMastery, change) {
      const node = this.nodes.find(n => n.label === nodeName)
      if (!node) return

      const oldFillColor = node.fillColor
      const oldGlowColor = node.glowColor

      // Update node mastery and recalculate colors
      node.mastery = newMastery
      node.fillColor = getMasteryColor(newMastery)
      node.glowColor = getMasteryGlowColor(newMastery, 0.5)
      node.outlineColor = getMasteryGlowColor(newMastery, 0.2)

      const newGlowColor = getMasteryGlowColor(newMastery, 0.5)

      this.highlightedNodes.set(node.id, {
        startTime: Date.now(),
        oldFillColor,
        oldGlowColor,
        newGlowColor
      })

      if (!this.highlightAnimationRunning) {
        this.highlightAnimationRunning = true
        this._runHighlightAnimation()
      }

      this._smoothPanToNode(node)
    },

    _runHighlightAnimation() {
      if (this.highlightedNodes.size === 0) {
        this.highlightAnimationRunning = false
        return
      }

      this.requestRender()

      requestAnimationFrame(() => {
        if (!this.highlightAnimationRunning) return

        // Prune finished animations
        for (const [nodeId, state] of this.highlightedNodes) {
          if (Date.now() - state.startTime > 3000) {
            const node = this.nodeMap.get(nodeId)
            if (node) {
              node._highlightFillOverride = null
              node._highlightGlowOverride = null
            }
            this.highlightedNodes.delete(nodeId)
          }
        }

        this._runHighlightAnimation()
      })
    },

    _smoothPanToNode(node, duration = 500) {
      // Cancel any previous smooth pan
      if (this._panRAF) {
        cancelAnimationFrame(this._panRAF)
        this._panRAF = null
      }

      const targetOffsetX = this.canvasWidth / 2 - node.x * this.scale
      const targetOffsetY = this.canvasHeight / 2 - node.y * this.scale
      const startOffsetX = this.offsetX
      const startOffsetY = this.offsetY
      const startTime = Date.now()

      const step = () => {
        if (!this._canvasEl) return // component unmounted guard
        const elapsed = Date.now() - startTime
        const t = Math.min(1, elapsed / duration)
        const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic

        this.offsetX = startOffsetX + (targetOffsetX - startOffsetX) * eased
        this.offsetY = startOffsetY + (targetOffsetY - startOffsetY) * eased
        this.requestRender()

        if (t < 1) {
          this._panRAF = requestAnimationFrame(step)
        } else {
          this._panRAF = null
        }
      }
      this._panRAF = requestAnimationFrame(step)
    },

    // --- Learning path animation ---
    async animateLearningPath(pathNodeNames) {
      // Cancel any running path animation first
      this.pathAnimationRunning = false
      if (this._pathStepTimer) {
        clearTimeout(this._pathStepTimer)
        this._pathStepTimer = null
      }
      if (this._pathEdgeGrowTimer) {
        clearTimeout(this._pathEdgeGrowTimer)
        this._pathEdgeGrowTimer = null
      }
      this.pathRippleNodes = new Map()
      this.pathAnimatedEdges = []
      this.pathCompletedEdges = []

      // Load fresh graph data (which now includes the new path edges)
      await this.loadAndRender()

      // Resolve node names to node objects
      const resolved = pathNodeNames
        .map(name => this.nodes.find(n => n.label === name))
        .filter(Boolean)

      if (resolved.length === 0) return

      // Initialize animation state
      this.pathAnimationNodes = resolved
      this.pathAnimationStep = -1
      this.pathRippleNodes = new Map()
      this.pathAnimatedEdges = []
      this.pathCompletedEdges = []
      this.pathAnimationRunning = true

      this._startPathAnimationStep(0)
      this._runPathAnimation()
    },

    _startPathAnimationStep(stepIndex) {
      if (!this.pathAnimationRunning) return
      if (stepIndex >= this.pathAnimationNodes.length) return

      this.pathAnimationStep = stepIndex
      const node = this.pathAnimationNodes[stepIndex]

      // Add ripple for this node
      this.pathRippleNodes.set(node.id, { startTime: Date.now() })

      // Smooth-pan viewport to this node
      this._smoothPanToNode(node, 400)

      // Start edge growth (200ms after ripple) to next node
      if (stepIndex < this.pathAnimationNodes.length - 1) {
        const nextNode = this.pathAnimationNodes[stepIndex + 1]
        this._pathEdgeGrowTimer = setTimeout(() => {
          this._pathEdgeGrowTimer = null
          if (!this.pathAnimationRunning) return
          this.pathAnimatedEdges = [
            ...this.pathAnimatedEdges,
            { from: node, to: nextNode, startTime: Date.now(), done: false }
          ]
        }, 200)
      }

      // Schedule next step
      if (stepIndex < this.pathAnimationNodes.length - 1) {
        this._pathStepTimer = setTimeout(() => {
          this._pathStepTimer = null
          this._startPathAnimationStep(stepIndex + 1)
        }, 800)
      }
    },

    _runPathAnimation() {
      if (!this.pathAnimationRunning) return

      const now = Date.now()

      // Prune finished ripples
      for (const [nodeId, state] of this.pathRippleNodes) {
        if (now - state.startTime > PATH_RIPPLE_DURATION) {
          this.pathRippleNodes.delete(nodeId)
        }
      }

      // Move completed edges to pathCompletedEdges
      const stillAnimating = []
      this.pathAnimatedEdges.forEach(edge => {
        if (now - edge.startTime > PATH_EDGE_GROW_DURATION) {
          this.pathCompletedEdges = [...this.pathCompletedEdges, { from: edge.from, to: edge.to }]
        } else {
          stillAnimating.push(edge)
        }
      })
      this.pathAnimatedEdges = stillAnimating

      // Detect full completion: all steps done, no active ripples, no animating edges
      const allStepsDone = this.pathAnimationStep >= this.pathAnimationNodes.length - 1
      const noActiveRipples = this.pathRippleNodes.size === 0
      const noAnimatingEdges = this.pathAnimatedEdges.length === 0

      if (allStepsDone && noActiveRipples && noAnimatingEdges) {
        this.pathAnimationRunning = false
        this.pathAnimationNodes = []
        this.pathAnimationStep = -1
        this.pathRippleNodes = new Map()
        this.pathAnimatedEdges = []
        this.pathCompletedEdges = []
        // Final render with static path highlight
        this.drawGraph()
        return
      }

      this.requestRender()
      requestAnimationFrame(() => {
        if (!this.pathAnimationRunning) return
        this._runPathAnimation()
      })
    },

    // --- Minimap ---
    initMinimap() {
      const wrap = this.$refs.minimapWrap
      if (!wrap) return
      const parentEl = wrap.$el || wrap

      const canvas = document.createElement('canvas')
      const dpr = this.dpr
      canvas.width = this.minimapWidth * dpr
      canvas.height = this.minimapHeight * dpr
      canvas.style.display = 'block'
      canvas.style.width = this.minimapWidth + 'px'
      canvas.style.height = this.minimapHeight + 'px'
      parentEl.appendChild(canvas)
      this._minimapEl = canvas
      this._minimapCtx = canvas.getContext('2d')
      this._minimapCtx.scale(dpr, dpr)

      this._onMmDown = this.onMinimapMouseDown.bind(this)
      this._onMmMove = this.onMinimapMouseMove.bind(this)
      this._onMmUp = this.onMinimapMouseUp.bind(this)
      canvas.addEventListener('mousedown', this._onMmDown)
    },

    getMinimapTransform() {
      const bounds = this.getGraphBounds()
      const gw = bounds.maxX - bounds.minX
      const gh = bounds.maxY - bounds.minY
      const pad = Math.max(gw, gh) * 0.1
      const tw = Math.max(gw + pad * 2, 100)
      const th = Math.max(gh + pad * 2, 100)
      const minimapScale = Math.min(this.minimapWidth / tw, this.minimapHeight / th)
      return {
        minimapScale,
        centerX: this.minimapWidth / 2,
        centerY: this.minimapHeight / 2,
        graphCenterX: (bounds.minX + bounds.maxX) / 2,
        graphCenterY: (bounds.minY + bounds.maxY) / 2
      }
    },

    requestMinimapRender(force = false) {
      const now = Date.now()
      if (!force && (now - this.lastMinimapRenderAt < 100)) return
      if (this.minimapPending) return
      this.minimapPending = true
      requestAnimationFrame(() => {
        this.minimapPending = false
        this.lastMinimapRenderAt = Date.now()
        this.drawMinimap()
      })
    },

    drawMinimap() {
      const ctx = this._minimapCtx
      if (!ctx) return

      // Always clear (removes stale content when graph becomes empty)
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
      ctx.clearRect(0, 0, this.minimapWidth, this.minimapHeight)

      if (this.nodes.length === 0) return

      const { centerX, centerY, graphCenterX, graphCenterY, minimapScale } = this.getMinimapTransform()
      if (!minimapScale || minimapScale <= 0) return

      const buckets = this.edgeBuckets || { nonPathEdges: [], pathEdges: [] }

      ctx.save()

      // Draw non-path edges
      if (this.pathHighlight) {
        ctx.globalAlpha = 0.15
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
      ctx.lineWidth = 0.5
      buckets.nonPathEdges.forEach(edge => {
        const fromNode = edge.fromNode || this.nodeMap.get(edge.from)
        const toNode = edge.toNode || this.nodeMap.get(edge.to)
        if (!fromNode || !toNode) return
        const x1 = centerX + (fromNode.x - graphCenterX) * minimapScale
        const y1 = centerY + (fromNode.y - graphCenterY) * minimapScale
        const x2 = centerX + (toNode.x - graphCenterX) * minimapScale
        const y2 = centerY + (toNode.y - graphCenterY) * minimapScale
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      })

      // Draw path edges (highlighted)
      if (this.pathHighlight) {
        ctx.globalAlpha = 1.0
        ctx.strokeStyle = this.pathColor
        ctx.lineWidth = 1
        buckets.pathEdges.forEach(edge => {
          const fromNode = edge.fromNode || this.nodeMap.get(edge.from)
          const toNode = edge.toNode || this.nodeMap.get(edge.to)
          if (!fromNode || !toNode) return
          const x1 = centerX + (fromNode.x - graphCenterX) * minimapScale
          const y1 = centerY + (fromNode.y - graphCenterY) * minimapScale
          const x2 = centerX + (toNode.x - graphCenterX) * minimapScale
          const y2 = centerY + (toNode.y - graphCenterY) * minimapScale
          ctx.beginPath()
          ctx.moveTo(x1, y1)
          ctx.lineTo(x2, y2)
          ctx.stroke()
        })
      }

      // Draw nodes as dots
      this.nodes.forEach(node => {
        const x = centerX + (node.x - graphCenterX) * minimapScale
        const y = centerY + (node.y - graphCenterY) * minimapScale
        const isOnPath = this.pathHighlight && this.learningPathSet.has(node.id)
        const isDimmed = this.pathHighlight && !isOnPath

        ctx.globalAlpha = isDimmed ? 0.25 : 1.0
        const dotColor = isOnPath ? this.pathColor : (node.level === 0 ? '#9CA3AF' : '#6B7280')
        const dotRadius = node.level === 0 ? 3 : (node.level === 1 ? 2.5 : 2)

        ctx.beginPath()
        ctx.arc(x, y, dotRadius, 0, Math.PI * 2)
        ctx.fillStyle = dotColor
        ctx.fill()
      })

      ctx.restore()

      // Draw viewport indicator
      if (this.scale > 0 && isFinite(this.offsetX) && isFinite(this.offsetY)) {
        const viewportWidth = (this.canvasWidth / this.scale) * minimapScale
        const viewportHeight = (this.canvasHeight / this.scale) * minimapScale
        const viewportCenterX = centerX - ((this.offsetX - this.canvasWidth / 2) / this.scale + graphCenterX) * minimapScale
        const viewportCenterY = centerY - ((this.offsetY - this.canvasHeight / 2) / this.scale + graphCenterY) * minimapScale

        const vx = viewportCenterX - viewportWidth / 2
        const vy = viewportCenterY - viewportHeight / 2
        const vr = 4

        ctx.beginPath()
        ctx.moveTo(vx + vr, vy)
        ctx.lineTo(vx + viewportWidth - vr, vy)
        ctx.arcTo(vx + viewportWidth, vy, vx + viewportWidth, vy + vr, vr)
        ctx.lineTo(vx + viewportWidth, vy + viewportHeight - vr)
        ctx.arcTo(vx + viewportWidth, vy + viewportHeight, vx + viewportWidth - vr, vy + viewportHeight, vr)
        ctx.lineTo(vx + vr, vy + viewportHeight)
        ctx.arcTo(vx, vy + viewportHeight, vx, vy + viewportHeight - vr, vr)
        ctx.lineTo(vx, vy + vr)
        ctx.arcTo(vx, vy, vx + vr, vy, vr)
        ctx.closePath()

        ctx.strokeStyle = '#FFFFFF'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
    },

    onMinimapMouseDown(e) {
      e.stopPropagation()
      e.preventDefault()
      this.isMinimapDragging = true
      window.addEventListener('mousemove', this._onMmMove)
      window.addEventListener('mouseup', this._onMmUp)
      this.navigateFromMinimap(e)
    },

    onMinimapMouseMove(e) {
      if (!this.isMinimapDragging) return
      e.preventDefault()
      this.navigateFromMinimap(e)
    },

    onMinimapMouseUp() {
      this.isMinimapDragging = false
      window.removeEventListener('mousemove', this._onMmMove)
      window.removeEventListener('mouseup', this._onMmUp)
    },

    navigateFromMinimap(e) {
      if (!this._minimapEl) return
      const rect = this._minimapEl.getBoundingClientRect()
      const localX = e.clientX - rect.left
      const localY = e.clientY - rect.top
      const { graphCenterX, graphCenterY, minimapScale } = this.getMinimapTransform()
      if (!minimapScale || minimapScale <= 0) return

      const targetX = graphCenterX + (localX - this.minimapWidth / 2) / minimapScale
      const targetY = graphCenterY + (localY - this.minimapHeight / 2) / minimapScale

      this.offsetX = this.canvasWidth / 2 - targetX * this.scale
      this.offsetY = this.canvasHeight / 2 - targetY * this.scale
      this.requestRender()
      this.requestMinimapRender(true)
    }
  }
}
</script>

<style scoped>
.kg-root {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.kg-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

/* Node popup */
.kg-popup {
  position: absolute;
  transform: translateX(-50%);
  z-index: 10;
  pointer-events: auto;
  min-width: 200px;
  max-width: 320px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.16);
  border-radius: 12px;
  backdrop-filter: blur(12px);
}

.kg-popup-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  white-space: nowrap;
}

.kg-popup-name {
  font-size: 14px;
  font-weight: 600;
  color: #F1F5F9;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kg-popup-mastery {
  flex-shrink: 0;
}

.kg-mastery-ring {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kg-mastery-inner {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
}

.kg-mastery-text {
  font-size: 11px;
  font-weight: 700;
  color: #F1F5F9;
}

.kg-lock-icon {
  width: 24px;
  height: 24px;
}

.kg-unlearned-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kg-quick-learn-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3px 10px;
  background: rgba(129, 140, 248, 0.18);
  border: 1px solid rgba(129, 140, 248, 0.35);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.kg-quick-learn-btn:hover {
  background: rgba(129, 140, 248, 0.30);
}

.kg-quick-learn-text {
  font-size: 12px;
  font-weight: 500;
  color: #818CF8;
  white-space: nowrap;
  line-height: 1;
}

/* Expand button */
.kg-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 4px 12px 6px;
  padding: 6px 0;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.35);
  cursor: pointer;
  transition: background 0.15s;
}

.kg-expand-btn:hover {
  background: rgba(99, 102, 241, 0.22);
}

.kg-expand-btn--loading {
  opacity: 0.85;
  cursor: default;
  pointer-events: none;
}

.kg-expand-btn-text {
  font-size: 12px;
  color: #818CF8;
  font-weight: 500;
  line-height: 1;
}

.kg-expand-loading {
  display: flex;
  align-items: center;
  gap: 5px;
}

.kg-expand-dots {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 0;
}

.kg-expand-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background-color: #818CF8;
  border-radius: 50%;
  animation: kg-expand-bounce 1.4s ease-in-out infinite;
}

.kg-expand-dot:nth-child(1) { animation-delay: 0s; }
.kg-expand-dot:nth-child(2) { animation-delay: 0.2s; }
.kg-expand-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes kg-expand-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

/* Loading */
.kg-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.kg-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(59, 130, 246, 0.7);
  border-radius: 50%;
  animation: kg-spin 0.8s linear infinite;
}

@keyframes kg-spin {
  to { transform: rotate(360deg); }
}

.kg-loading-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

/* Error */
.kg-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kg-error-text {
  font-size: 13px;
  color: rgba(255, 100, 100, 0.7);
}

/* Empty */
.kg-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.kg-empty-text {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.15);
}

.kg-empty-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.08);
}

/* Generating state */
.kg-generating {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.kg-loading-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.25);
  margin-top: 2px;
}

/* Retry button */
.kg-retry-btn {
  margin-top: 12px;
  padding: 8px 20px;
  border-radius: 20px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.35);
  cursor: pointer;
  transition: all 0.2s ease;
}

.kg-retry-btn:hover {
  background: rgba(59, 130, 246, 0.3);
  border-color: rgba(59, 130, 246, 0.5);
}

.kg-retry-btn-text {
  font-size: 13px;
  font-weight: 500;
  color: rgba(59, 130, 246, 0.9);
}

/* Inline notes */
.kg-notes-inline {
  border-top: 1px solid rgba(226, 232, 240, 0.08);
  padding: 6px 14px 8px;
}
.kg-notes-hint {
  font-size: 12px;
  color: rgba(241, 245, 249, 0.35);
  display: block;
  text-align: center;
}
.kg-notes-list {
  max-height: 150px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}
.kg-notes-list::-webkit-scrollbar {
  width: 6px;
}
.kg-notes-list::-webkit-scrollbar-track {
  background: transparent;
}
.kg-notes-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.kg-notes-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
.kg-notes-item {
  padding: 5px 0;
  cursor: pointer;
  transition: background 0.15s;
}
.kg-notes-item + .kg-notes-item {
  border-top: 1px solid rgba(226, 232, 240, 0.06);
}
.kg-notes-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.kg-notes-item-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(241, 245, 249, 0.85);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kg-notes-item-preview {
  font-size: 11px;
  color: rgba(241, 245, 249, 0.4);
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Minimap */
.kg-minimap {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 5;
  width: 160px;
  height: 120px;
  background-color: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
  pointer-events: auto;
  cursor: crosshair;
}

/* Note preview overlay */
.kg-note-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: auto;
}

.kg-note-preview {
  width: 70%;
  max-width: 680px;
  max-height: 80%;
  display: flex;
  flex-direction: column;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.16);
  border-radius: 16px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
}

.kg-note-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.08);
  flex-shrink: 0;
}

.kg-note-preview-title {
  font-size: 16px;
  font-weight: 700;
  color: #F1F5F9;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 12px;
}

.kg-note-preview-close {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}

.kg-note-preview-close:hover {
  background: rgba(255, 255, 255, 0.1);
}

.kg-note-preview-close-icon {
  font-size: 20px;
  color: rgba(241, 245, 249, 0.5);
  line-height: 1;
}

.kg-note-preview-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 20px;
}

.kg-note-preview-error-text {
  font-size: 13px;
  color: rgba(255, 100, 100, 0.7);
}

.kg-note-preview-body {
  flex: 1;
  padding: 20px 24px;
  overflow-x: hidden;
}

.kg-note-preview-tag {
  display: inline-block;
  margin-bottom: 14px;
}

.kg-note-preview-tag-text {
  font-size: 12px;
  color: rgba(129, 140, 248, 0.9);
  padding: 3px 10px;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 6px;
}

.kg-note-preview-content {
  font-size: 14px;
  color: rgba(241, 245, 249, 0.85);
  line-height: 1.8;
  word-break: break-word;
  overflow-x: auto;
  max-width: 100%;
}

.kg-note-preview-empty {
  display: block;
  font-size: 14px;
  color: rgba(241, 245, 249, 0.35);
}

.kg-note-preview-attachments {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid rgba(226, 232, 240, 0.08);
}

.kg-note-preview-attach-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(241, 245, 249, 0.5);
  margin-bottom: 10px;
}

.kg-note-preview-attach-item {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  margin-bottom: 6px;
}

.kg-note-preview-attach-name {
  font-size: 12px;
  color: rgba(241, 245, 249, 0.6);
}

.kg-note-preview-meta {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kg-note-preview-meta-text {
  font-size: 11px;
  color: rgba(241, 245, 249, 0.3);
}
</style>
