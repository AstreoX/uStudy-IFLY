<template>
  <view class="kg-root">
    <!-- Canvas container (native canvas created programmatically to bypass uni-app wrapper) -->
    <view ref="canvasWrap" class="kg-canvas"></view>

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

      // Caches
      nodeMap: new Map(),
      edgeBuckets: { treeEdges: [], advancedEdges: [], pathEdges: [], nonPathEdges: [] },
      learningPathSet: new Set(),
      visibleNodesCache: null,
      visibleNodeIdSetCache: new Set(),
      childCountCache: new Map(),

      // Render throttling
      renderPending: false,
      ctx: null
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
      this._canvasEl.remove()
      this._canvasEl = null
    }
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

      this.dpr = window.devicePixelRatio || 1
      this.resizeCanvas()

      // ResizeObserver on the container
      this._resizeObserver = new ResizeObserver(() => {
        this.resizeCanvas()
        this.requestRender()
      })
      this._resizeObserver.observe(parentEl)
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
</style>
