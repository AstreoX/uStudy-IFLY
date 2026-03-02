<template>
  <view class="widget-card" :class="{ 'subject-edit-mode': editMode }">
    <view class="subject-title-area" :class="{ 'title-area-edit': editMode }" @tap="onTitleTap" @pointerdown.stop="editMode && void 0">
      <text class="subject-title">{{ subject.name }}</text>
      <text v-if="editMode" class="title-switch-hint">&#x25BC; choose</text>
    </view>

    <!-- Space selector dropdown -->
    <view v-if="showMenu" class="space-menu-overlay" @pointerdown.stop @tap="showMenu = false">
      <view class="space-menu" @tap.stop>
        <view class="space-menu-header">
          <text class="space-menu-title">Select Space</text>
        </view>
        <scroll-view scroll-y class="space-menu-list" :style="{ maxHeight: menuMaxHeight + 'px' }">
          <view
            v-for="space in spaces"
            :key="space.id"
            class="space-menu-item"
            :class="{ 'space-menu-item-active': space.name === subject.name }"
            @tap="onSelectSpace(space.id)"
          >
            <text class="space-menu-item-name">{{ space.name || 'Untitled' }}</text>
            <text v-if="space.name === subject.name" class="space-menu-check">&#x2713;</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <view class="subject-info-row">
      <text class="info-part">Part {{ subject.current }}/{{ subject.total }}</text>
      <text class="info-percent">{{ progressPercent }}%</text>
    </view>

    <view class="progress-bar">
      <view class="progress-fill" :style="{ width: progressPercent + '%' }"></view>
    </view>

    <view class="tree-container" ref="treeContainer">
      <canvas
        v-if="hasGraphData"
        :canvas-id="canvasId"
        class="tree-canvas"
        :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
      ></canvas>
      <view v-else class="tree-empty">
        <text class="tree-empty-text">No graph data</text>
      </view>
    </view>

  </view>
</template>

<script>
import { getMasteryColor, getMasteryGlowColor } from '@/utils/mastery-colors'

const LABEL_CONFIG = {
  fontSizeMin: 8,
  fontSizeMax: 12,
  lineHeightRatio: 1.15,
  maxWidthRatio: 0.26,
  paddingY: 4
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

export default {
  emits: ['select-subject'],
  props: {
    subject: {
      type: Object,
      default: () => ({
        name: 'No space',
        current: 0,
        total: 0,
        progress: 0,
        graphData: null
      })
    },
    editMode: {
      type: Boolean,
      default: false
    },
    widgetId: {
      type: String,
      default: 'default'
    },
    spaces: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      ctx: null,
      showMenu: false,
      menuMaxHeight: 200,
      canvasWidth: 200,
      canvasHeight: 80,
      resizeObserver: null,
      nodeMap: new Map(),
      layoutNodes: [],
      treeScale: 1,
      isUnmounted: false
    }
  },
  computed: {
    canvasId() {
      return `subjectTree_${this.widgetId}`
    },
    progressPercent() {
      if (this.subject.progress != null) return this.subject.progress
      if (!this.subject.total) return 0
      return Math.round((this.subject.current / this.subject.total) * 100)
    },
    hasGraphData() {
      const gd = this.subject.graphData
      return gd && gd.nodes && gd.nodes.length > 0
    },
    hasPathEdges() {
      const gd = this.subject.graphData
      if (!gd || !gd.edges) return false
      return gd.edges.some(e => e.type === 'learning_path')
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.setupResizeObserver()
      this.initCanvas()
    })
  },
  beforeUnmount() {
    this.isUnmounted = true
    this.ctx = null
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
  },
  watch: {
    'subject.graphData': {
      handler() {
        this.$nextTick(() => {
          if (this.ctx) {
            this.measureAndDraw()
          } else {
            this.initCanvas()
          }
        })
      },
      deep: true
    }
  },
  methods: {
    onTitleTap() {
      if (!this.editMode) return
      if (this.spaces.length === 0) return
      this.showMenu = true
    },
    onSelectSpace(spaceId) {
      this.showMenu = false
      this.$emit('select-subject', spaceId)
    },
    initCanvas(retryCount = 0) {
      if (this.isUnmounted) return
      const maxRetries = 5
      this.ctx = uni.createCanvasContext(this.canvasId, this)
      if (!this.ctx) {
        if (retryCount < maxRetries) {
          setTimeout(() => this.initCanvas(retryCount + 1), 100)
        }
        return
      }
      this.measureAndDraw()
    },

    setupResizeObserver() {
      const container = this.$refs.treeContainer
      if (!container) return
      const dom = container.$el || container
      this.resizeObserver = new ResizeObserver(() => {
        this.measureAndDraw()
      })
      this.resizeObserver.observe(dom)
    },

    measureAndDraw() {
      if (this.isUnmounted) return
      const container = this.$refs.treeContainer
      if (!container) return
      const dom = container.$el || container
      const w = dom.clientWidth
      const h = dom.clientHeight
      if (w > 0 && h > 0) {
        this.canvasWidth = w
        this.canvasHeight = h
        this.$nextTick(() => this.drawTree())
      }
    },

    drawTree() {
      if (this.isUnmounted || !this.hasGraphData || !this.ctx) return
      const ctx = this.ctx
      const gd = this.subject.graphData

      // Build node map (same as APP prepareAndDraw)
      this.nodeMap = new Map()
      gd.nodes.forEach(n => this.nodeMap.set(n.id, { ...n }))

      // Compute layout (no force-directed — same as APP)
      if (this.hasPathEdges) {
        this.computePathLayout()
      } else {
        this.computeConcentricLayout()
      }

      // Draw (same as APP drawMiniGraph)
      if (this.layoutNodes.length === 0) return
      ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)
      try {
        if (this.hasPathEdges) {
          this.drawPathMode(ctx)
        } else {
          this.drawTreeMode(ctx)
        }
      } catch (err) {
        console.error('[SubjectWidget] draw error:', err)
      }
      ctx.draw()
    },

    // ========== Label metrics (ported from knowledge-tree-mini.vue) ==========

    getLabelMetrics() {
      const base = Math.min(this.canvasWidth, this.canvasHeight)
      const scale = clamp(this.treeScale || 1, 0.9, 1.8)
      const fontSize = clamp(Math.round((base / 14) * scale), LABEL_CONFIG.fontSizeMin, LABEL_CONFIG.fontSizeMax)
      const lineHeight = Math.round(fontSize * LABEL_CONFIG.lineHeightRatio)
      const maxWidth = Math.round(Math.min(this.canvasWidth * LABEL_CONFIG.maxWidthRatio * scale, 110))
      const maxChars = Math.max(4, Math.floor(maxWidth / (fontSize * 0.9)))
      return { fontSize, lineHeight, maxWidth, maxChars, paddingY: LABEL_CONFIG.paddingY }
    },

    getNodeLabel(node) {
      if (!node) return ''
      return String(node.label || node.title || node.name || '').trim()
    },

    formatNodeLabel(label, metrics) {
      if (!label) return ''
      const clean = label.replace(/\s+/g, ' ')
      if (clean.length <= metrics.maxChars) return clean
      if (metrics.maxChars <= 3) return clean.slice(0, metrics.maxChars)
      return clean.slice(0, metrics.maxChars - 3) + '...'
    },

    estimateLabelWidth(text, metrics) {
      if (!text) return 0
      return Math.min(metrics.maxWidth, Math.round(text.length * metrics.fontSize * 0.9))
    },

    // ========== Layout (from knowledge-tree-mini.vue) ==========

    computeConcentricLayout() {
      const nodes = this.subject.graphData.nodes
      const edges = this.subject.graphData.edges

      const treeEdges = edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      const parentMap = new Map()
      const childrenMap = new Map()

      treeEdges.forEach(e => {
        parentMap.set(e.to, e.from)
        if (!childrenMap.has(e.from)) {
          childrenMap.set(e.from, [])
        }
        childrenMap.get(e.from).push(e.to)
      })

      const nodeIds = new Set(nodes.map(n => n.id))
      const roots = nodes.filter(n => !parentMap.has(n.id))
      if (roots.length === 0) return

      const levels = new Map()
      const queue = roots.map(r => ({ id: r.id, level: 0 }))
      while (queue.length > 0) {
        const { id, level } = queue.shift()
        levels.set(id, level)
        const children = childrenMap.get(id) || []
        children.forEach(cid => {
          if (nodeIds.has(cid) && !levels.has(cid)) {
            queue.push({ id: cid, level: level + 1 })
          }
        })
      }

      const baseRadius = 120
      const levelSpacing = 100
      const graphNodes = []

      const root = roots[0]
      graphNodes.push({
        ...this.nodeMap.get(root.id),
        x: 0,
        y: 0,
        level: 0,
        radius: 18
      })

      this.layoutSubtree(root.id, 0, Math.PI * 2, childrenMap, levels, baseRadius, levelSpacing, graphNodes)

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
      graphNodes.forEach(node => {
        const r = node.radius || 0
        minX = Math.min(minX, node.x - r)
        maxX = Math.max(maxX, node.x + r)
        minY = Math.min(minY, node.y - r)
        maxY = Math.max(maxY, node.y + r)
      })

      if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
        this.layoutNodes = []
        return
      }

      const labelBase = Math.min(this.canvasWidth, this.canvasHeight)
      const labelFontSize = clamp(Math.round(labelBase / 14), LABEL_CONFIG.fontSizeMin, LABEL_CONFIG.fontSizeMax)
      const labelLineHeight = Math.round(labelFontSize * LABEL_CONFIG.lineHeightRatio)
      const labelMaxWidth = Math.round(Math.min(this.canvasWidth * LABEL_CONFIG.maxWidthRatio, 110))
      const labelHalfWidth = labelMaxWidth / 2
      const labelHeight = labelLineHeight + LABEL_CONFIG.paddingY

      minX -= labelHalfWidth
      maxX += labelHalfWidth
      maxY += labelHeight

      const cropPadding = 16
      const graphHalfW = (maxX - minX) / 2 + cropPadding
      const graphHalfH = (maxY - minY) / 2 + cropPadding
      const ratio = this.canvasWidth / Math.max(1, this.canvasHeight)

      let cropHalfW = graphHalfW
      let cropHalfH = graphHalfH

      if (graphHalfW / graphHalfH >= ratio) {
        cropHalfH = graphHalfH
        cropHalfW = cropHalfH * ratio
      } else {
        cropHalfW = graphHalfW
        cropHalfH = cropHalfW / ratio
      }

      const baseScale = cropHalfW > 0 ? this.canvasWidth / (cropHalfW * 2) : 1
      const zoomFactor = 1.5
      const scale = Math.min(2.2, baseScale * zoomFactor)
      this.treeScale = scale

      const centerX = this.canvasWidth / 2
      const centerY = this.canvasHeight / 2

      this.layoutNodes = graphNodes.map(node => {
        const scaledRadius = Math.max(2, (node.radius || 3) * scale)
        return {
          ...node,
          x: node.x * scale + centerX,
          y: node.y * scale + centerY,
          radius: scaledRadius
        }
      })
    },

    computePathLayout() {
      const nodes = this.subject.graphData.nodes
      const edges = this.subject.graphData.edges

      const pathEdges = edges.filter(e => e.type === 'learning_path')
      const pathNodeSet = new Set()
      pathEdges.forEach(e => {
        pathNodeSet.add(e.from)
        pathNodeSet.add(e.to)
      })

      if (pathNodeSet.size === 0) {
        this.computeConcentricLayout()
        return
      }

      const treeEdges = edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      const parentMap = new Map()
      const childrenMap = new Map()

      treeEdges.forEach(e => {
        parentMap.set(e.to, e.from)
        if (!childrenMap.has(e.from)) {
          childrenMap.set(e.from, [])
        }
        childrenMap.get(e.from).push(e.to)
      })

      const nodeIds = new Set(nodes.map(n => n.id))
      const roots = nodes.filter(n => !parentMap.has(n.id))
      if (roots.length === 0) return

      const levels = new Map()
      const queue = roots.map(r => ({ id: r.id, level: 0 }))
      while (queue.length > 0) {
        const { id, level } = queue.shift()
        levels.set(id, level)
        const children = childrenMap.get(id) || []
        children.forEach(cid => {
          if (nodeIds.has(cid) && !levels.has(cid)) {
            queue.push({ id: cid, level: level + 1 })
          }
        })
      }

      const baseRadius = 120
      const levelSpacing = 100
      const graphNodes = []

      const root = roots[0]
      graphNodes.push({
        ...this.nodeMap.get(root.id),
        x: 0,
        y: 0,
        level: 0,
        radius: 18
      })

      this.layoutSubtree(root.id, 0, Math.PI * 2, childrenMap, levels, baseRadius, levelSpacing, graphNodes)

      const pathGraphNodes = graphNodes.filter(node => pathNodeSet.has(node.id))
      if (pathGraphNodes.length === 0) {
        this.computeConcentricLayout()
        return
      }

      const pathCenter = pathGraphNodes.reduce((acc, node) => {
        acc.x += node.x
        acc.y += node.y
        return acc
      }, { x: 0, y: 0 })
      pathCenter.x /= pathGraphNodes.length
      pathCenter.y /= pathGraphNodes.length

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
      pathGraphNodes.forEach(node => {
        const r = node.radius || 0
        minX = Math.min(minX, node.x - r)
        maxX = Math.max(maxX, node.x + r)
        minY = Math.min(minY, node.y - r)
        maxY = Math.max(maxY, node.y + r)
      })

      if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
        this.layoutNodes = []
        return
      }

      const labelBase = Math.min(this.canvasWidth, this.canvasHeight)
      const labelFontSize = clamp(Math.round(labelBase / 14), LABEL_CONFIG.fontSizeMin, LABEL_CONFIG.fontSizeMax)
      const labelLineHeight = Math.round(labelFontSize * LABEL_CONFIG.lineHeightRatio)
      const labelMaxWidth = Math.round(Math.min(this.canvasWidth * LABEL_CONFIG.maxWidthRatio, 110))
      const labelHalfWidth = labelMaxWidth / 2
      const labelHeight = labelLineHeight + LABEL_CONFIG.paddingY

      minX -= labelHalfWidth
      maxX += labelHalfWidth
      maxY += labelHeight

      const cropPadding = 16
      let halfW = Math.max(pathCenter.x - minX, maxX - pathCenter.x) + cropPadding
      let halfH = Math.max(pathCenter.y - minY, maxY - pathCenter.y) + cropPadding
      const ratio = this.canvasWidth / Math.max(1, this.canvasHeight)

      if (halfW / halfH >= ratio) {
        halfH = halfW / ratio
      } else {
        halfW = halfH * ratio
      }

      const fitScale = halfW > 0 ? this.canvasWidth / (halfW * 2) : 1
      const scale = Math.min(2.2, fitScale)
      this.treeScale = scale

      const centerX = this.canvasWidth / 2
      const centerY = this.canvasHeight / 2

      this.layoutNodes = graphNodes.map(node => ({
        ...node,
        x: (node.x - pathCenter.x) * scale + centerX,
        y: (node.y - pathCenter.y) * scale + centerY,
        radius: Math.max(2, (node.radius || 3) * scale),
        isOnPath: pathNodeSet.has(node.id)
      }))
    },

    // ========== Subtree helpers (from knowledge-tree-mini.vue) ==========

    getSubtreeSize(nodeId, childrenMap) {
      const children = childrenMap.get(nodeId) || []
      if (children.length === 0) return 1
      return 1 + children.reduce((sum, cid) => sum + this.getSubtreeSize(cid, childrenMap), 0)
    },

    layoutSubtree(parentId, angleStart, angleEnd, childrenMap, levels, baseRadius, levelSpacing, graphNodes) {
      const children = childrenMap.get(parentId) || []
      if (children.length === 0) return

      const subtreeSizes = children.map(cid => this.getSubtreeSize(cid, childrenMap))
      const totalSize = subtreeSizes.reduce((a, b) => a + b, 0)
      if (totalSize === 0) return

      let currentAngle = angleStart
      const parentLevel = levels.get(parentId) || 0
      const ringRadius = baseRadius + parentLevel * levelSpacing

      children.forEach((childId, i) => {
        const angleRange = (subtreeSizes[i] / totalSize) * (angleEnd - angleStart)
        const childAngle = currentAngle + angleRange / 2

        const node = this.nodeMap.get(childId)
        if (!node) return

        const level = levels.get(childId) || 0
        const x = Math.cos(childAngle) * ringRadius
        const y = Math.sin(childAngle) * ringRadius

        const nodeRadius = level === 0 ? 18 : (level === 1 ? 14 : (level === 2 ? 11 : 8))

        graphNodes.push({
          ...node,
          x,
          y,
          level,
          radius: nodeRadius
        })

        this.layoutSubtree(childId, currentAngle, currentAngle + angleRange, childrenMap, levels, baseRadius, levelSpacing, graphNodes)
        currentAngle += angleRange
      })
    },

    // ========== Drawing Methods (from knowledge-tree-mini.vue) ==========

    drawPathMode(ctx) {
      const pathNodes = this.layoutNodes.filter(n => n.isOnPath)
      const otherNodes = this.layoutNodes.filter(n => !n.isOnPath)
      const nodeById = new Map()
      this.layoutNodes.forEach(n => nodeById.set(n.id, n))
      const edgeWidth = Math.max(1, 1 * (this.treeScale || 1))

      const edges = this.subject.graphData.edges || []
      const treeEdges = edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      ctx.setGlobalAlpha(0.35)
      treeEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          this.drawEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y, 'rgba(255, 255, 255, 0.25)', edgeWidth)
        }
      })
      ctx.setGlobalAlpha(1.0)

      const pathEdges = edges.filter(e => e.type === 'learning_path')
      pathEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          this.drawPathEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y)
        }
      })

      ctx.setGlobalAlpha(0.4)
      otherNodes.forEach(node => {
        this.drawNode(ctx, node)
      })
      ctx.setGlobalAlpha(1.0)
      pathNodes.forEach(node => {
        this.drawPathNode(ctx, node)
      })

      this.drawNodeLabels(ctx, pathNodes, { alpha: 0.9 })
    },

    drawTreeMode(ctx) {
      const nodeById = new Map()
      this.layoutNodes.forEach(n => nodeById.set(n.id, n))
      const edgeWidth = Math.max(1, 1 * (this.treeScale || 1))

      const edges = this.subject.graphData.edges || []
      const treeEdges = edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      treeEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          this.drawEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y, 'rgba(255, 255, 255, 0.25)', edgeWidth)
        }
      })

      this.layoutNodes.forEach(node => {
        this.drawNode(ctx, node)
      })

      const labelNodes = this.layoutNodes.filter(node => node.level === 0 || node.level === 1)
      this.drawNodeLabels(ctx, labelNodes, { alpha: 0.85 })
    },

    drawNodeLabels(ctx, nodes, options = {}) {
      if (!nodes || nodes.length === 0) return
      if (!ctx || typeof ctx.fillText !== 'function') return
      if (typeof ctx.setFontSize !== 'function') return

      const metrics = this.getLabelMetrics()
      const alpha = options.alpha == null ? 0.75 : options.alpha

      ctx.setGlobalAlpha(alpha)
      ctx.setFontSize(metrics.fontSize)
      ctx.setFillStyle('#FFFFFF')
      if (typeof ctx.setTextAlign === 'function') {
        ctx.setTextAlign('center')
      }
      if (typeof ctx.setTextBaseline === 'function') {
        ctx.setTextBaseline('top')
      }
      if (typeof ctx.setShadow === 'function') {
        ctx.setShadow(0, 1, 2, 'rgba(0, 0, 0, 0.45)')
      }

      nodes.forEach(node => {
        const label = this.formatNodeLabel(this.getNodeLabel(node), metrics)
        if (!label) return
        const radius = node.radius || 5
        const labelX = node.x
        const labelY = node.y + radius + metrics.paddingY
        ctx.fillText(label, labelX, labelY)
      })

      if (typeof ctx.setShadow === 'function') {
        ctx.setShadow(0, 0, 0, 'transparent')
      }
      ctx.setGlobalAlpha(1.0)
    },

    drawEdge(ctx, x1, y1, x2, y2, color, lineWidth) {
      ctx.beginPath()
      ctx.setStrokeStyle(color)
      ctx.setLineWidth(lineWidth)
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()
    },

    drawPathEdge(ctx, x1, y1, x2, y2) {
      const color = '#0088FF'
      const scale = this.treeScale || 1
      const lineWidth = Math.max(2, 3 * scale)

      ctx.beginPath()
      ctx.setStrokeStyle(color)
      ctx.setLineWidth(lineWidth)
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()

      const midX = (x1 + x2) / 2
      const midY = (y1 + y2) / 2
      const angle = Math.atan2(y2 - y1, x2 - x1)
      const arrowSize = Math.max(4, 5 * scale)

      ctx.beginPath()
      ctx.setFillStyle(color)
      ctx.moveTo(
        midX + arrowSize * Math.cos(angle),
        midY + arrowSize * Math.sin(angle)
      )
      ctx.lineTo(
        midX + arrowSize * Math.cos(angle + 2.5),
        midY + arrowSize * Math.sin(angle + 2.5)
      )
      ctx.lineTo(
        midX + arrowSize * Math.cos(angle - 2.5),
        midY + arrowSize * Math.sin(angle - 2.5)
      )
      ctx.closePath()
      ctx.fill()
    },

    drawNode(ctx, node) {
      const radius = node.radius || 5
      const isUnmastered = node.mastery == null
      const outlineSize = Math.max(2, 4 * (this.treeScale || 1))
      const glowSize = Math.max(8, 18 * (this.treeScale || 1))

      if (isUnmastered) {
        const grayColor = '#6B7280'
        const glowColor = 'rgba(107, 114, 128, 0.5)'
        const outlineColor = 'rgba(107, 114, 128, 0.2)'

        ctx.setShadow(0, 0, glowSize, glowColor)

        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(grayColor)
        ctx.fill()
      } else {
        const color = getMasteryColor(node.mastery)
        const glowColor = getMasteryGlowColor(node.mastery, 0.5)
        const outlineColor = getMasteryGlowColor(node.mastery, 0.2)

        ctx.setShadow(0, 0, glowSize, glowColor)

        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(color)
        ctx.fill()
      }

      ctx.setShadow(0, 0, 0, 'transparent')
    },

    drawPathNode(ctx, node) {
      this.drawNode(ctx, node)

      ctx.beginPath()
      const outlineSize = Math.max(2, 3 * (this.treeScale || 1))
      ctx.arc(node.x, node.y, node.radius + outlineSize, 0, Math.PI * 2)
      ctx.setStrokeStyle('#0088FF')
      ctx.setLineWidth(Math.max(1, 1.5 * (this.treeScale || 1)))
      ctx.stroke()
    }
  }
}
</script>

<style scoped>
.widget-card {
  background: var(--color-widget-bg);
  border: 1px solid var(--color-widget-border);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  padding: 14px 16px 14px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  transition: border 0.2s ease, background 0.2s ease;
}

/* Edit mode: dashed blue border + light blue tint */
.subject-edit-mode {
  border-color: transparent;
  outline: 2px dashed rgba(59, 130, 246, 0.5);
  outline-offset: -2px;
  background:
    linear-gradient(rgba(59, 130, 246, 0.06), rgba(59, 130, 246, 0.06)),
    var(--color-widget-bg);
}

.subject-title-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  margin: -4px -8px 6px;
  border: 1.5px dashed transparent;
  border-radius: 8px;
  transition: background 0.15s, border-color 0.15s;
}

.title-area-edit {
  border-color: rgba(59, 130, 246, 0.35);
  cursor: pointer;
}

.title-area-edit:hover {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.6);
}

.subject-title {
  font-size: 16px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-switch-hint {
  font-size: 10px;
  color: rgba(59, 130, 246, 0.5);
  white-space: nowrap;
  margin-left: 8px;
}

.subject-info-row {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.info-part {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.info-percent {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.progress-bar {
  height: 5px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  background: rgba(59, 130, 246, 0.8);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.tree-container {
  flex: 1;
  min-height: 0;
  background: rgba(10, 10, 10, 0.4);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tree-canvas {
  display: block;
}

.tree-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.tree-empty-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.25);
}

/* Space selector menu */
.space-menu-overlay {
  position: absolute;
  inset: 0;
  z-index: 50;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.space-menu {
  width: 100%;
  max-width: 240px;
  background: rgba(30, 32, 44, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.space-menu-header {
  padding: 10px 14px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.space-menu-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.45);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.space-menu-list {
  padding: 4px 0;
}

.space-menu-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.space-menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.space-menu-item-active {
  background: rgba(59, 130, 246, 0.12);
}

.space-menu-item-active:hover {
  background: rgba(59, 130, 246, 0.18);
}

.space-menu-item-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.space-menu-item-active .space-menu-item-name {
  color: rgba(59, 130, 246, 1);
  font-weight: 500;
}

.space-menu-check {
  font-size: 14px;
  color: rgba(59, 130, 246, 1);
  margin-left: 8px;
  flex-shrink: 0;
}

</style>
