<template>
  <view class="knowledge-tree-mini-container" :class="{ 'knowledge-tree-mini-interactive': interactive }">
    <canvas
      v-if="hasData"
      :canvas-id="canvasId"
      class="mini-graph-canvas"
      :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
    />
    <!-- 交互模式：透明触摸层（canvas 在 uni-app 中不可靠地接收 touch） -->
    <view
      v-if="interactive && hasData"
      class="touch-overlay"
      @touchstart="onCanvasTouchStart"
      @touchmove.stop.prevent="onCanvasTouchMove"
      @touchend="onCanvasTouchEnd"
    />
    <view v-if="!hasData" class="empty-state">
      <text class="empty-text">暂无数据</text>
    </view>
  </view>
</template>

<script>
// 掌握度颜色渐变端点 (0-100 分段插值)
const MASTERY_COLOR_START = { r: 255, g: 50, b: 66 }   // #FF3242 (mastery=0, 珊瑚红)
const MASTERY_COLOR_MID = { r: 255, g: 217, b: 61 }    // #FFD93D (mastery=50, 浅黄色)
const MASTERY_COLOR_END = { r: 73, g: 255, b: 170 }    // #49FFAA (mastery=100, 薄荷绿)

/**
 * 根据掌握度 (0-100) 计算分段渐变 RGB 值
 */
function interpolateMasteryRGB(mastery) {
  const clampedMastery = Math.max(0, Math.min(100, mastery ?? 0))

  let r, g, b

  if (clampedMastery <= 50) {
    const t = clampedMastery / 50
    r = Math.round(MASTERY_COLOR_START.r + (MASTERY_COLOR_MID.r - MASTERY_COLOR_START.r) * t)
    g = Math.round(MASTERY_COLOR_START.g + (MASTERY_COLOR_MID.g - MASTERY_COLOR_START.g) * t)
    b = Math.round(MASTERY_COLOR_START.b + (MASTERY_COLOR_MID.b - MASTERY_COLOR_START.b) * t)
  } else {
    const t = (clampedMastery - 50) / 50
    r = Math.round(MASTERY_COLOR_MID.r + (MASTERY_COLOR_END.r - MASTERY_COLOR_MID.r) * t)
    g = Math.round(MASTERY_COLOR_MID.g + (MASTERY_COLOR_END.g - MASTERY_COLOR_MID.g) * t)
    b = Math.round(MASTERY_COLOR_MID.b + (MASTERY_COLOR_END.b - MASTERY_COLOR_MID.b) * t)
  }

  return { r, g, b }
}

/**
 * 根据掌握度 (0-100) 计算分段渐变颜色 (Hex)
 */
function getMasteryColor(mastery) {
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * 根据掌握度计算发光颜色 (RGBA)
 */
function getMasteryGlowColor(mastery, opacity = 0.5) {
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}

/**
 * 简单哈希函数，用于伪随机散布节点
 */
function simpleHash(str) {
  if (!str || typeof str !== 'string') {
    return 1  // 返回非零默认值
  }
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash) || 1  // 确保返回非零值
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function hashToUnit(hash, salt = 0) {
  const x = Math.sin((hash + salt) * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

const LABEL_CONFIG = {
  fontSizeMin: 8,
  fontSizeMax: 12,
  lineHeightRatio: 1.15,
  maxWidthRatio: 0.26,
  paddingY: 4
}

// 力导向布局配置
const FORCE_CONFIG = {
  iterations: 80,           // 模拟迭代次数
  damping: 0.78,            // 速度衰减系数
  minMovement: 0.05,        // 收敛阈值
  nodeRepulsion: 2000,      // 节点间斥力系数
  minNodeDistance: 30,      // 最小节点间距
  extraNodeSpacing: 12,     // 额外节点间距
  borderRepulsion: 900,     // 边界斥力系数
  borderPadding: 12,        // 边界安全距离
  borderSoftRange: 30,      // 边界缓冲区范围
  arrowRepulsion: 900,      // 箭头斥力系数
  arrowCenter: { xRatio: 0.90, yRatio: 0.857 },
  arrowRadius: 32,          // 箭头避让半径
  anchorStrength: 0.18,     // 目标位置吸引力系数
  pathJitterX: 6,           // 路径节点 X 方向扰动
  pathJitterY: 6,           // 路径节点 Y 方向扰动
  pathWaveFrequency: 1.1,   // 波形频率
  adjacentMaxPerNode: 2,    // 邻接节点最大数量
  adjacentRadiusMin: 28,    // 邻接节点最小半径
  adjacentRadiusMax: 60,    // 邻接节点最大半径
  adjacentAngleSpread: 120  // 邻接节点分布角度范围
}

export default {
  name: 'KnowledgeTreeMini',

  props: {
    spaceId: {
      type: String,
      required: true
    },
    nodes: {
      type: Array,
      default: () => []
    },
    edges: {
      type: Array,
      default: () => []
    },
    canvasWidth: {
      type: Number,
      default: 200
    },
    canvasHeight: {
      type: Number,
      default: 120
    },
    forceTreeMode: {
      type: Boolean,
      default: false
    },
    canvasIdSuffix: {
      type: String,
      default: ''
    },
    interactive: {
      type: Boolean,
      default: false
    },
    highlightNodeLabels: {
      type: Array,
      default: () => []
    },
    highlightColor: {
      type: String,
      default: '#4A6CF7'
    },
    highlightMode: {
      type: String,
      default: 'static'
    },
    highlightEdgePairs: {
      type: Array,
      default: () => []
    },
    highlightEdgeColor: {
      type: String,
      default: '#FFD93D'
    }
  },

  data() {
    return {
      ctx: null,
      nodeMap: new Map(),
      layoutNodes: [],
      isDestroyed: false,
      treeScale: 1,
      // 交互模式：视口变换
      viewOffsetX: 0,
      viewOffsetY: 0,
      viewScale: 1,
      touchState: null,
      drawThrottleTimer: null
    }
  },

  computed: {
    canvasId() {
      return `miniGraph_${this.spaceId}${this.canvasIdSuffix}`
    },

    hasData() {
      return this.nodes && this.nodes.length > 0
    },

    hasLearningPath() {
      return this.edges && this.edges.some(e => e.type === 'learning_path')
    },

    highlightLabelSet() {
      return new Set(this.highlightNodeLabels || [])
    }
  },

  watch: {
    nodes: {
      handler() {
        this.scheduleRedraw()
      },
      deep: true
    },
    edges: {
      handler() {
        this.scheduleRedraw()
      },
      deep: true
    },
    canvasWidth() {
      this.scheduleRedraw()
    },
    canvasHeight() {
      this.scheduleRedraw()
    },
    highlightNodeLabels: {
      handler() {
        if (!this.ctx || this.layoutNodes.length === 0) return
        this.drawMiniGraph()
      }
    }
  },

  mounted() {
    this.$nextTick(() => {
      this.initCanvas()
    })
  },

  beforeDestroy() {
    this.isDestroyed = true
    this.ctx = null
    if (this.drawThrottleTimer) {
      clearTimeout(this.drawThrottleTimer)
      this.drawThrottleTimer = null
    }
  },

  methods: {
    initCanvas(retryCount = 0) {
      if (this.isDestroyed) return

      const maxRetries = 5
      this.ctx = uni.createCanvasContext(this.canvasId, this)

      if (!this.ctx) {
        if (retryCount < maxRetries) {
          setTimeout(() => this.initCanvas(retryCount + 1), 100)
        }
        return
      }

      this.prepareAndDraw()
    },

    scheduleRedraw() {
      if (this.isDestroyed) return

      this.$nextTick(() => {
        if (this.ctx) {
          this.prepareAndDraw()
        } else {
          this.initCanvas()
        }
      })
    },

    prepareAndDraw() {
      if (!this.hasData || !this.ctx) return

      // Build node map
      this.nodeMap = new Map()
      this.nodes.forEach(n => this.nodeMap.set(n.id, { ...n }))

      // Compute layout
      if (this.hasLearningPath && !this.forceTreeMode) {
        this.computePathLayout()
      } else {
        this.computeConcentricLayout()
      }

      // Recenter on highlighted nodes if any
      this.recenterOnHighlights()

      // Draw
      this.drawMiniGraph()

    },

    /**
     * 将视口中心移到高亮节点的质心，使变更节点始终居中显示
     */
    recenterOnHighlights() {
      if (this.highlightLabelSet.size === 0 || this.layoutNodes.length === 0) return

      const highlighted = this.layoutNodes.filter(n => this.highlightLabelSet.has(n.label))
      if (highlighted.length === 0) return

      // 计算高亮节点质心
      const cx = highlighted.reduce((sum, n) => sum + n.x, 0) / highlighted.length
      const cy = highlighted.reduce((sum, n) => sum + n.y, 0) / highlighted.length

      // 偏移量：质心 → 画布中心
      const dx = this.canvasWidth / 2 - cx
      const dy = this.canvasHeight / 2 - cy

      // 平移所有节点
      this.layoutNodes = this.layoutNodes.map(n => ({
        ...n,
        x: n.x + dx,
        y: n.y + dy
      }))
    },

    getLabelMetrics() {
      const base = Math.min(this.canvasWidth, this.canvasHeight)
      const scale = clamp(this.treeScale || 1, 0.9, 1.8)
      const fontSize = clamp(Math.round((base / 14) * scale), LABEL_CONFIG.fontSizeMin, LABEL_CONFIG.fontSizeMax)
      const lineHeight = Math.round(fontSize * LABEL_CONFIG.lineHeightRatio)
      const maxWidth = Math.round(Math.min(this.canvasWidth * LABEL_CONFIG.maxWidthRatio * scale, 110))
      const maxChars = Math.max(4, Math.floor(maxWidth / (fontSize * 0.9)))
      return {
        fontSize,
        lineHeight,
        maxWidth,
        maxChars,
        paddingY: LABEL_CONFIG.paddingY
      }
    },

    getNodeLabel(node) {
      if (!node || node.showLabel === false) return ''
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

    getNodePadding(node, metrics) {
      const radius = node.radius || 5
      const label = this.formatNodeLabel(this.getNodeLabel(node), metrics)
      if (!label) return radius
      const labelWidth = this.estimateLabelWidth(label, metrics)
      const labelHeight = metrics.lineHeight + metrics.paddingY
      return Math.max(radius, labelWidth / 2) + labelHeight * 0.75
    },

    getNodeSafeBounds(node, metrics) {
      const radius = node.radius || 5
      const label = this.formatNodeLabel(this.getNodeLabel(node), metrics)
      const labelWidth = label ? this.estimateLabelWidth(label, metrics) : 0
      const labelHeight = label ? (metrics.lineHeight + metrics.paddingY) : 0

      const paddingX = FORCE_CONFIG.borderPadding + Math.max(radius, labelWidth / 2)
      const paddingTop = FORCE_CONFIG.borderPadding + radius
      const paddingBottom = FORCE_CONFIG.borderPadding + radius + labelHeight

      const minX = Math.min(paddingX, this.canvasWidth / 2)
      const maxX = Math.max(this.canvasWidth - paddingX, this.canvasWidth / 2)
      const minY = Math.min(paddingTop, this.canvasHeight / 2)
      const maxY = Math.max(this.canvasHeight - paddingBottom, this.canvasHeight / 2)

      return { minX, maxX, minY, maxY }
    },

    // ========== Layout Algorithms ==========

    /**
     * 力导向布局模拟
     * 将所有约束统一为斥力系统，避免节点重合
     * @param {Array} inputNodes - 节点数组（包含初始位置和目标位置 targetX/targetY）
     * @returns {Array} 新节点数组，包含更新后的位置
     */
    applyForceDirectedLayout(inputNodes) {
      // 边界情况：空数组或单节点无需模拟
      if (!inputNodes || inputNodes.length <= 1) {
        return inputNodes
      }

      // 节点数量上限保护（O(n^2) 算法）
      const MAX_NODES = 200
      if (inputNodes.length > MAX_NODES) {
        return inputNodes
      }

      const config = FORCE_CONFIG
      const canvasWidth = this.canvasWidth
      const canvasHeight = this.canvasHeight
      const labelMetrics = this.getLabelMetrics()

      // 创建工作副本，避免修改输入对象（不可变性原则）
      const nodes = inputNodes.map(n => ({
        ...n,
        vx: 0,
        vy: 0
      }))

      const arrowX = canvasWidth * config.arrowCenter.xRatio
      const arrowY = canvasHeight * config.arrowCenter.yRatio

      // 力大小上限，防止数值爆炸
      const MAX_FORCE = 1000

      for (let iter = 0; iter < config.iterations; iter++) {
        let totalMovement = 0

        // 计算每个节点受到的力
        nodes.forEach((node, i) => {
          let fx = 0
          let fy = 0

          // 1. 节点间斥力（库仑力）
          nodes.forEach((other, j) => {
            if (i === j) return
            const dx = node.x - other.x
            const dy = node.y - other.y
            const dist = Math.sqrt(dx * dx + dy * dy) || 0.1

            const nodePadding = this.getNodePadding(node, labelMetrics)
            const otherPadding = this.getNodePadding(other, labelMetrics)
            const pathExtra = (node.isOnPath || other.isOnPath) ? 6 : 0
            const minDist = Math.max(
              config.minNodeDistance,
              nodePadding + otherPadding + config.extraNodeSpacing + pathExtra
            )

            if (dist < minDist) {
              const forceScale = (minDist - dist) / minDist
              const force = Math.min(MAX_FORCE, config.nodeRepulsion / (dist * dist)) * forceScale
              fx += (dx / dist) * force
              fy += (dy / dist) * force
            }
          })

          // 2. 边界斥力
          const borderForce = this.calcBorderForce(node, MAX_FORCE, labelMetrics)
          fx += borderForce.bfx
          fy += borderForce.bfy

          // 3. 箭头障碍物斥力
          const arrowForce = this.calcArrowForce(node, arrowX, arrowY, MAX_FORCE)
          fx += arrowForce.afx
          fy += arrowForce.afy

          // 4. 锚点吸引力（拉向目标位置，保持布局结构）
          if (node.targetX !== undefined && node.targetY !== undefined) {
            fx += (node.targetX - node.x) * config.anchorStrength
            fy += (node.targetY - node.y) * config.anchorStrength
          }

          // 更新速度（带阻尼）
          node.vx = (node.vx + fx) * config.damping
          node.vy = (node.vy + fy) * config.damping
        })

        // 应用速度更新位置
        nodes.forEach(node => {
          node.x += node.vx
          node.y += node.vy

          // 硬边界约束（防止跑出画布）
          const bounds = this.getNodeSafeBounds(node, labelMetrics)
          node.x = clamp(node.x, bounds.minX, bounds.maxX)
          node.y = clamp(node.y, bounds.minY, bounds.maxY)

          totalMovement += Math.abs(node.vx) + Math.abs(node.vy)
        })

        // 收敛检查
        if (totalMovement < config.minMovement * nodes.length) break
      }

      // 返回新数组，移除临时速度属性
      return nodes.map(({ vx, vy, ...rest }) => rest)
    },

    /**
     * 计算边界斥力
     * @param {Object} node - 节点对象，包含 x, y 坐标
     * @param {number} maxForce - 力大小上限
     * @returns {Object} 边界斥力 { bfx, bfy }
     */
    calcBorderForce(node, maxForce, labelMetrics) {
      const config = FORCE_CONFIG
      const metrics = labelMetrics || this.getLabelMetrics()
      const bounds = this.getNodeSafeBounds(node, metrics)
      const softRange = config.borderSoftRange

      let bfx = 0
      let bfy = 0

      // 左边界
      const leftDist = node.x - bounds.minX
      if (leftDist < softRange) {
        const rawForce = config.borderRepulsion / Math.pow(leftDist + 1, 2)
        bfx += Math.min(maxForce, rawForce)
      }
      // 右边界
      const rightDist = bounds.maxX - node.x
      if (rightDist < softRange) {
        const rawForce = config.borderRepulsion / Math.pow(rightDist + 1, 2)
        bfx -= Math.min(maxForce, rawForce)
      }
      // 上边界
      const topDist = node.y - bounds.minY
      if (topDist < softRange) {
        const rawForce = config.borderRepulsion / Math.pow(topDist + 1, 2)
        bfy += Math.min(maxForce, rawForce)
      }
      // 下边界
      const bottomDist = bounds.maxY - node.y
      if (bottomDist < softRange) {
        const rawForce = config.borderRepulsion / Math.pow(bottomDist + 1, 2)
        bfy -= Math.min(maxForce, rawForce)
      }

      return { bfx, bfy }
    },

    /**
     * 计算箭头障碍物斥力
     * @param {Object} node - 节点对象，包含 x, y 坐标
     * @param {number} arrowX - 箭头中心 X 坐标
     * @param {number} arrowY - 箭头中心 Y 坐标
     * @param {number} maxForce - 力大小上限
     * @returns {Object} 箭头斥力 { afx, afy }
     */
    calcArrowForce(node, arrowX, arrowY, maxForce) {
      const config = FORCE_CONFIG
      const dx = node.x - arrowX
      const dy = node.y - arrowY
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.1

      let afx = 0
      let afy = 0

      if (dist < config.arrowRadius * 1.5) {
        const force = Math.min(maxForce, config.arrowRepulsion / (dist * dist))
        afx = (dx / dist) * force
        afy = (dy / dist) * force
      }

      return { afx, afy }
    },

    /**
     * Path mode: concentric layout centered on learning path geometry
     */
    computePathLayout() {
      const pathEdges = this.edges.filter(e => e.type === 'learning_path')
      const pathNodeSet = new Set()
      pathEdges.forEach(edge => {
        pathNodeSet.add(edge.from)
        pathNodeSet.add(edge.to)
      })

      if (pathNodeSet.size === 0) {
        this.computeConcentricLayout()
        return
      }

      // Build parent-child relationships from knowledge_tree edges
      const treeEdges = this.edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      const parentMap = new Map()
      const childrenMap = new Map()

      treeEdges.forEach(e => {
        parentMap.set(e.to, e.from)
        if (!childrenMap.has(e.from)) {
          childrenMap.set(e.from, [])
        }
        childrenMap.get(e.from).push(e.to)
      })

      // Find root nodes (no parent)
      const nodeIds = new Set(this.nodes.map(n => n.id))
      const roots = this.nodes.filter(n => !parentMap.has(n.id))
      if (roots.length === 0) return

      // BFS to compute levels
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

      // Same layout proportions as learningSpace
      const baseRadius = 120
      const levelSpacing = 100

      const graphNodes = []

      // Layout root at origin
      const root = roots[0]
      graphNodes.push({
        ...this.nodeMap.get(root.id),
        x: 0,
        y: 0,
        level: 0,
        radius: 18
      })

      // Recursive layout in graph space (center at 0,0)
      this.layoutSubtree(root.id, 0, Math.PI * 2, childrenMap, levels, baseRadius, levelSpacing, graphNodes)

      // Path nodes in graph space
      const pathGraphNodes = graphNodes.filter(node => pathNodeSet.has(node.id))
      if (pathGraphNodes.length === 0) {
        this.computeConcentricLayout()
        return
      }

      // Compute path center (geometric center)
      const pathCenter = pathGraphNodes.reduce((acc, node) => {
        acc.x += node.x
        acc.y += node.y
        return acc
      }, { x: 0, y: 0 })
      pathCenter.x /= pathGraphNodes.length
      pathCenter.y /= pathGraphNodes.length

      // Compute bounds around path nodes for center-crop
      let minX = Infinity
      let maxX = -Infinity
      let minY = Infinity
      let maxY = -Infinity
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

    /**
     * Extract ordered path chain from path edges
     */
    extractPathChain(pathEdges) {
      if (pathEdges.length === 0) return []

      // Build adjacency
      const nextMap = new Map()
      const prevSet = new Set()

      pathEdges.forEach(e => {
        nextMap.set(e.from, e.to)
        prevSet.add(e.to)
      })

      // Find start node (not a target of any edge)
      let startNode = null
      for (const e of pathEdges) {
        if (!prevSet.has(e.from)) {
          startNode = e.from
          break
        }
      }

      if (!startNode) {
        startNode = pathEdges[0].from
      }

      // Build chain
      const chain = [startNode]
      let current = startNode
      const visited = new Set([startNode])

      while (nextMap.has(current)) {
        const next = nextMap.get(current)
        if (visited.has(next)) break
        chain.push(next)
        visited.add(next)
        current = next
      }

      return chain
    },

    /**
     * Concentric circle layout (for trees without learning path).
     * Render like learningSpace and then center-crop to fit card ratio.
     */
    computeConcentricLayout() {
      // Build parent-child relationships from knowledge_tree edges
      const treeEdges = this.edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      const parentMap = new Map()
      const childrenMap = new Map()

      treeEdges.forEach(e => {
        parentMap.set(e.to, e.from)
        if (!childrenMap.has(e.from)) {
          childrenMap.set(e.from, [])
        }
        childrenMap.get(e.from).push(e.to)
      })

      // Find root nodes (no parent)
      const nodeIds = new Set(this.nodes.map(n => n.id))
      const roots = this.nodes.filter(n => !parentMap.has(n.id))

      if (roots.length === 0) return

      // BFS to compute levels
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

      // Same layout proportions as learningSpace
      const baseRadius = 120
      const levelSpacing = 100

      const graphNodes = []

      // Layout root at origin
      const root = roots[0]
      graphNodes.push({
        ...this.nodeMap.get(root.id),
        x: 0,
        y: 0,
        level: 0,
        radius: 18
      })

      // Recursive layout in graph space (center at 0,0)
      this.layoutSubtree(root.id, 0, Math.PI * 2, childrenMap, levels, baseRadius, levelSpacing, graphNodes)

      // Compute graph bounds for center-crop
      let minX = Infinity
      let maxX = -Infinity
      let minY = Infinity
      let maxY = -Infinity
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

    getSubtreeSize(nodeId, childrenMap) {
      const children = childrenMap.get(nodeId) || []
      if (children.length === 0) return 1
      return 1 + children.reduce((sum, cid) => sum + this.getSubtreeSize(cid, childrenMap), 0)
    },

    layoutSubtree(parentId, angleStart, angleEnd, childrenMap, levels, baseRadius, levelSpacing, graphNodes) {
      const children = childrenMap.get(parentId) || []
      if (children.length === 0) return

      // Calculate subtree sizes for proportional angle allocation
      const subtreeSizes = children.map(cid => this.getSubtreeSize(cid, childrenMap))
      const totalSize = subtreeSizes.reduce((a, b) => a + b, 0)

      // Guard against division by zero
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

        // Recursively layout children
        this.layoutSubtree(childId, currentAngle, currentAngle + angleRange, childrenMap, levels, baseRadius, levelSpacing, graphNodes)

        currentAngle += angleRange
      })
    },

    // ========== Drawing Methods ==========

    drawMiniGraph() {
      if (!this.ctx || this.layoutNodes.length === 0) return

      const ctx = this.ctx

      // Clear canvas
      ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)

      try {
        // 交互模式：应用视口变换（平移 + 缩放）
        if (this.interactive) {
          ctx.save()
          // 先移到画布中心，再缩放，再移回 + 偏移
          ctx.translate(
            this.viewOffsetX + this.canvasWidth / 2,
            this.viewOffsetY + this.canvasHeight / 2
          )
          ctx.scale(this.viewScale, this.viewScale)
          ctx.translate(-this.canvasWidth / 2, -this.canvasHeight / 2)
        }

        if (this.hasLearningPath && !this.forceTreeMode) {
          this.drawPathMode(ctx)
        } else {
          this.drawTreeMode(ctx)
        }

        if (this.interactive) {
          ctx.restore()
        }
      } catch (err) {
        console.error('[KnowledgeTreeMini] draw error:', err)
      }

      ctx.draw()
    },

    /**
     * Draw path mode: learning path highlighted
     */
    drawPathMode(ctx) {
      const pathNodes = this.layoutNodes.filter(n => n.isOnPath)
      const otherNodes = this.layoutNodes.filter(n => !n.isOnPath)
      const nodeById = new Map()
      this.layoutNodes.forEach(n => nodeById.set(n.id, n))
      const edgeWidth = Math.max(1, 1 * (this.treeScale || 1))

      // Draw tree edges (dimmed, learningSpace style)
      const treeEdges = this.edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      ctx.setGlobalAlpha(0.35)
      treeEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          this.drawEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y, 'rgba(255, 255, 255, 0.25)', edgeWidth)
        }
      })
      ctx.setGlobalAlpha(1.0)

      // Build highlight edge lookup (label→label)
      const highlightEdgeSet = new Set()
      if (this.highlightEdgePairs && this.highlightEdgePairs.length > 0) {
        this.highlightEdgePairs.forEach(pair => {
          highlightEdgeSet.add(pair[0] + '→' + pair[1])
        })
      }

      // Draw path edges (highlight)
      const pathEdges = this.edges.filter(e => e.type === 'learning_path')
      pathEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          const edgeKey = fromNode.label + '→' + toNode.label
          const edgeColor = highlightEdgeSet.has(edgeKey) ? this.highlightEdgeColor : null
          const scale = this.treeScale || 1
          const outlineSize = Math.max(2, 3 * scale)
          const fromR = fromNode.isOnPath ? (fromNode.radius || 5) + outlineSize : 0
          const toR = toNode.isOnPath ? (toNode.radius || 5) + outlineSize : 0
          const clipped = this.clipEdgeToRing(fromNode.x, fromNode.y, toNode.x, toNode.y, fromR, toR)
          if (clipped) {
            this.drawPathEdge(ctx, clipped[0], clipped[1], clipped[2], clipped[3], edgeColor)
          }
        }
      })

      // Draw nodes (dim non-path)
      ctx.setGlobalAlpha(0.4)
      otherNodes.forEach(node => {
        this.drawNode(ctx, node)
      })
      ctx.setGlobalAlpha(1.0)
      pathNodes.forEach(node => {
        this.drawPathNode(ctx, node)
      })

      // Draw labels (path nodes only) — skip when too many path nodes to avoid overlap
      if (pathNodes.length <= 7) {
        this.drawNodeLabels(ctx, pathNodes, { alpha: 0.9 })
      }
    },

    /**
     * Draw tree mode: all nodes with mastery colors
     */
    drawTreeMode(ctx) {
      // Build node map for quick lookup
      const nodeById = new Map()
      this.layoutNodes.forEach(n => nodeById.set(n.id, n))
      const edgeWidth = Math.max(1, 1 * (this.treeScale || 1))
      const hasHighlight = this.highlightLabelSet.size > 0

      // Draw all edges
      const treeEdges = this.edges.filter(e => e.type === 'knowledge_tree' || !e.type)
      treeEdges.forEach(edge => {
        const fromNode = nodeById.get(edge.from)
        const toNode = nodeById.get(edge.to)
        if (fromNode && toNode) {
          if (hasHighlight) {
            const fromLabel = fromNode.label
            const toLabel = toNode.label
            const isHighlightEdge = this.highlightLabelSet.has(fromLabel) && this.highlightLabelSet.has(toLabel)
            if (isHighlightEdge) {
              const scale = this.treeScale || 1
              const fromRadius = fromNode.radius || 5
              const toRadius = toNode.radius || 5
              const outlineSize = Math.max(2, 4 * scale)
              const ringOffset = outlineSize + 4 * scale
              const clipped = this.clipEdgeToRing(
                fromNode.x, fromNode.y, toNode.x, toNode.y,
                fromRadius + ringOffset, toRadius + ringOffset
              )
              if (clipped) {
                this.drawEdge(ctx, clipped[0], clipped[1], clipped[2], clipped[3], this.highlightColor, edgeWidth * 2.5)
              }
            } else {
              this.drawEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y, 'rgba(255, 255, 255, 0.25)', edgeWidth)
            }
          } else {
            this.drawEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y, 'rgba(255, 255, 255, 0.25)', edgeWidth)
          }
        }
      })

      // Draw all nodes
      this.layoutNodes.forEach(node => {
        this.drawNode(ctx, node)
      })

      // Draw labels only when node count <= 7 (too many nodes cause label overlap)
      if (this.nodes.length <= 7) {
        const labelNodes = this.layoutNodes.filter(node =>
          node.level === 0 || node.level === 1 || this.highlightLabelSet.has(node.label)
        )
        this.drawNodeLabels(ctx, labelNodes, { alpha: 0.85 })
      }
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

    /**
     * Draw a simple edge
     */
    drawEdge(ctx, x1, y1, x2, y2, color, lineWidth) {
      ctx.beginPath()
      ctx.setStrokeStyle(color)
      ctx.setLineWidth(lineWidth)
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()
    },

    /**
     * Clip edge endpoints to stop at node ring boundaries instead of node centers.
     * Returns adjusted [x1, y1, x2, y2] coordinates, or null if nodes overlap.
     */
    clipEdgeToRing(x1, y1, x2, y2, r1, r2) {
      const dx = x2 - x1
      const dy = y2 - y1
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist <= r1 + r2) return null
      const ux = dx / dist
      const uy = dy / dist
      return [x1 + ux * r1, y1 + uy * r1, x2 - ux * r2, y2 - uy * r2]
    },

    /**
     * Draw path edge with arrow (blue highlighted)
     */
    drawPathEdge(ctx, x1, y1, x2, y2, overrideColor) {
      const color = overrideColor || '#0088FF'
      const scale = this.treeScale || 1
      const lineWidth = Math.max(2, 3 * scale)

      // Draw line
      ctx.beginPath()
      ctx.setStrokeStyle(color)
      ctx.setLineWidth(lineWidth)
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()

      // Draw arrow at midpoint
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

    /**
     * Draw a node with mastery color and glow
     */
    drawNode(ctx, node) {
      const radius = node.radius || 5
      const isUnmastered = node.mastery == null
      const outlineSize = Math.max(2, 4 * (this.treeScale || 1))
      const glowSize = Math.max(8, 18 * (this.treeScale || 1))

      if (isUnmastered) {
        const grayColor = '#6B7280'
        const glowColor = 'rgba(107, 114, 128, 0.5)'
        const outlineColor = 'rgba(107, 114, 128, 0.2)'

        // Glow
        ctx.setShadow(0, 0, glowSize, glowColor)

        // Outline
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        // Main circle
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(grayColor)
        ctx.fill()
      } else {
        const color = getMasteryColor(node.mastery)
        const glowColor = getMasteryGlowColor(node.mastery, 0.5)
        const outlineColor = getMasteryGlowColor(node.mastery, 0.2)

        // Glow
        ctx.setShadow(0, 0, glowSize, glowColor)

        // Outline
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        // Main circle
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(color)
        ctx.fill()
      }

      // Highlight ring for mutation tools
      if (this.highlightLabelSet.has(node.label)) {
        const ringRadius = radius + outlineSize + 4 * (this.treeScale || 1)
        const ringWidth = Math.max(1.5, 2.5 * (this.treeScale || 1))

        ctx.setShadow(0, 0, glowSize * 2, this.highlightColor)
        ctx.beginPath()
        ctx.arc(node.x, node.y, ringRadius, 0, Math.PI * 2)
        ctx.setStrokeStyle(this.highlightColor)
        ctx.setLineWidth(ringWidth)
        ctx.setGlobalAlpha(0.9)
        ctx.stroke()
        ctx.setGlobalAlpha(1.0)
      }

      // Reset shadow
      ctx.setShadow(0, 0, 0, 'transparent')
    },

    /**
     * Draw path node with blue outline
     */
    drawPathNode(ctx, node) {
      // Draw base node
      this.drawNode(ctx, node)

      // Add blue outline for path nodes
      ctx.beginPath()
      const outlineSize = Math.max(2, 3 * (this.treeScale || 1))
      ctx.arc(node.x, node.y, node.radius + outlineSize, 0, Math.PI * 2)  // 蓝圈加大
      ctx.setStrokeStyle('#0088FF')
      ctx.setLineWidth(Math.max(1, 1.5 * (this.treeScale || 1)))
      ctx.stroke()
    },

    // ========== Touch Interaction (interactive mode) ==========

    onCanvasTouchStart(e) {
      if (!this.interactive) return
      const touches = e.touches
      if (touches.length === 1) {
        this.touchState = {
          type: 'pan',
          startX: touches[0].clientX,
          startY: touches[0].clientY,
          startOffsetX: this.viewOffsetX,
          startOffsetY: this.viewOffsetY
        }
      } else if (touches.length === 2) {
        this.initPinch(touches)
      }
    },

    onCanvasTouchMove(e) {
      if (!this.interactive || !this.touchState) return
      const touches = e.touches

      if (touches.length === 2 && this.touchState.type === 'pan') {
        // 单指拖动中第二根手指落下 → 切换为缩放
        this.initPinch(touches)
        return
      }

      if (this.touchState.type === 'pan' && touches.length === 1) {
        this.viewOffsetX = this.touchState.startOffsetX + (touches[0].clientX - this.touchState.startX)
        this.viewOffsetY = this.touchState.startOffsetY + (touches[0].clientY - this.touchState.startY)
      } else if (this.touchState.type === 'pinch' && touches.length === 2) {
        const dx = touches[1].clientX - touches[0].clientX
        const dy = touches[1].clientY - touches[0].clientY
        const dist = Math.sqrt(dx * dx + dy * dy)
        const ratio = dist / this.touchState.startDist
        this.viewScale = clamp(this.touchState.startScale * ratio, 0.3, 5)

        // 缩放时同步平移
        const midX = (touches[0].clientX + touches[1].clientX) / 2
        const midY = (touches[0].clientY + touches[1].clientY) / 2
        this.viewOffsetX = this.touchState.startOffsetX + (midX - this.touchState.startMidX)
        this.viewOffsetY = this.touchState.startOffsetY + (midY - this.touchState.startMidY)
      }

      this.throttledDraw()
    },

    onCanvasTouchEnd(e) {
      if (!this.interactive) return
      if (e.touches.length === 0) {
        this.touchState = null
      } else if (e.touches.length === 1) {
        // 缩放结束、还剩一根手指 → 切回拖动
        this.touchState = {
          type: 'pan',
          startX: e.touches[0].clientX,
          startY: e.touches[0].clientY,
          startOffsetX: this.viewOffsetX,
          startOffsetY: this.viewOffsetY
        }
      }
    },

    initPinch(touches) {
      const dx = touches[1].clientX - touches[0].clientX
      const dy = touches[1].clientY - touches[0].clientY
      this.touchState = {
        type: 'pinch',
        startDist: Math.sqrt(dx * dx + dy * dy) || 1,
        startScale: this.viewScale,
        startMidX: (touches[0].clientX + touches[1].clientX) / 2,
        startMidY: (touches[0].clientY + touches[1].clientY) / 2,
        startOffsetX: this.viewOffsetX,
        startOffsetY: this.viewOffsetY
      }
    },

    throttledDraw() {
      if (this.drawThrottleTimer) return
      this.drawThrottleTimer = setTimeout(() => {
        this.drawThrottleTimer = null
        this.drawMiniGraph()
      }, 16)
    }
  }
}
</script>

<style scoped>
.knowledge-tree-mini-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

.knowledge-tree-mini-interactive {
  position: relative;
}

.mini-graph-canvas {
  display: block;
}

.touch-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

.empty-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.3);
}
</style>
