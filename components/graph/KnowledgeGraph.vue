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
          <svg v-else viewBox="0 0 256 256" class="kg-lock-icon">
            <rect width="256" height="256" fill="none"/>
            <path d="M208,80H176V56a48,48,0,0,0-96,0V80H48A16,16,0,0,0,32,96V208a16,16,0,0,0,16,16H208a16,16,0,0,0,16-16V96A16,16,0,0,0,208,80Zm-80,84a12,12,0,1,1,12-12A12,12,0,0,1,128,164Zm32-84H96V56a32,32,0,0,1,64,0Z" fill="rgba(255,255,255,0.4)"/>
          </svg>
        </view>
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

    <!-- Empty state -->
    <view v-else-if="nodes.length === 0" class="kg-empty">
      <text class="kg-empty-text">No knowledge graph yet</text>
      <text class="kg-empty-sub">Start a conversation to generate one</text>
    </view>
  </view>
</template>

<script>
import { getSpaceGraph } from '@/api/space'
import { getMasteryColor, getMasteryGlowColor } from '@/utils/mastery-colors'
import {
  buildTreeFromEdges, computeLayout, getNodeBaseRadius,
  getLabelBoxByPosition, clamp,
  UNMASTERED_NODE_COLOR, UNMASTERED_NODE_GLOW, UNMASTERED_NODE_OUTLINE
} from '@/utils/graph-layout'
import { drawEdges, drawNode } from '@/utils/graph-renderer'

export default {
  props: {
    spaceId: { type: [String, Number], default: null },
    pathHighlight: { type: Boolean, default: false }
  },

  emits: ['node-selected', 'graph-loaded'],

  data() {
    return {
      loading: false,
      error: null,
      nodes: [],
      edges: [],
      learningPath: [],

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

      // Render throttling
      renderPending: false,
      ctx: null,

      // Minimap
      minimapWidth: 160,
      minimapHeight: 120,
      minimapPending: false,
      lastMinimapRenderAt: 0,
      isMinimapDragging: false
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
    pathHighlight() {
      this.requestRender()
      this.requestMinimapRender(true)
    }
  },

  mounted() {
    this.initCanvas()
    if (this.spaceId) this.loadAndRender()
  },

  beforeUnmount() {
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
      this.loading = true
      this.error = null

      try {
        const { nodes: apiNodes, edges: apiEdges } = await getSpaceGraph(this.spaceId)

        if (!apiNodes || apiNodes.length === 0) {
          this.nodes = []
          this.edges = []
          this.loading = false
          return
        }

        const { nodes, edges, learningPath } = buildTreeFromEdges(apiNodes, apiEdges)
        this.nodes = nodes
        this.edges = edges
        this.learningPath = learningPath

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

      // Child count cache
      this.childCountCache = new Map()
      this.nodes.forEach(n => {
        let count = 0
        const countChildren = (parentId) => {
          this.nodes.forEach(c => {
            if (c.parent === parentId) { count++; countChildren(c.id) }
          })
        }
        countChildren(n.id)
        n.childCount = count
        this.childCountCache.set(n.id, count)
      })

      // Visible nodes
      this.updateVisibleNodesCache()
    },

    updateVisibleNodesCache() {
      this.visibleNodesCache = this.nodes.filter(node => {
        let parent = node.parent ? this.nodeMap.get(node.parent) : null
        while (parent) {
          if (parent.collapsed) return false
          parent = parent.parent ? this.nodeMap.get(parent.parent) : null
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
        showAdvancedEdges: true
      })

      // Draw nodes
      renderNodes.forEach(node => {
        drawNode(ctx, node, {
          selectedNodeId: this.selectedNodeId,
          isPathHighlightOn: this.pathHighlight,
          learningPathSet: this.learningPathSet
        })
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
        ctx.strokeStyle = '#0088FF'
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
        const dotColor = isOnPath ? '#0088FF' : (node.level === 0 ? '#9CA3AF' : '#6B7280')
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
  pointer-events: none;
}

.kg-popup-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.16);
  border-radius: 12px;
  backdrop-filter: blur(12px);
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
</style>
