// Concentric circle layout configuration
export const LAYOUT_CONFIG = {
  baseRadius: 120,
  levelSpacing: 100
}

// Label layout configuration
export const LABEL_LAYOUT_CONFIG = {
  fontSize: 11,
  lineHeightRatio: 1.28,
  paddingX: 8,
  paddingY: 5,
  nodeLabelGap: 8,
  maxWidthRatio: 0.34,
  maxWidthCap: 240,
  minWidth: 96,
  collisionPadding: 10,
  connectorColor: 'rgba(226, 232, 240, 0.32)',
  background: 'rgba(15, 23, 42, 0.64)',
  borderColor: 'rgba(226, 232, 240, 0.18)',
  cornerRadius: 8,
  candidatePositions: ['bottom', 'right', 'left', 'top', 'br', 'bl', 'tr', 'tl']
}

// Node color constants
export const UNMASTERED_NODE_COLOR = '#E2E8F0'
export const UNMASTERED_NODE_GLOW = 'rgba(226, 232, 240, 0.50)'
export const UNMASTERED_NODE_OUTLINE = 'rgba(241, 245, 249, 0.30)'
export const KNOWLEDGE_EDGE_COLOR = 'rgba(245, 248, 255, 0.42)'
export const KNOWLEDGE_EDGE_WIDTH = 1.8

// --- Helpers ---

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

export function normalizeAnglePositive(angle) {
  const twoPi = Math.PI * 2
  let normalized = angle % twoPi
  if (normalized < 0) normalized += twoPi
  return normalized
}

export function normalizeAngleDiff(angle) {
  const twoPi = Math.PI * 2
  let normalized = (angle + Math.PI) % twoPi
  if (normalized < 0) normalized += twoPi
  return normalized - Math.PI
}

export function getNodeBaseRadius(node) {
  if (!node) return 8
  if (node.baseRadius != null) return node.baseRadius
  if (node.level === 0) return 18
  if (node.level === 1) return 14
  if (node.level === 2) return 11
  return 8
}

// --- Text measurement (character-width heuristic, no canvas needed) ---

const textWidthCache = new Map()

export function measureTextApprox(text, fontSize = LABEL_LAYOUT_CONFIG.fontSize) {
  const source = text == null ? '' : String(text)
  if (!source) return 0

  const cacheKey = `${fontSize}:${source}`
  const cached = textWidthCache.get(cacheKey)
  if (cached != null) return cached

  let width = 0
  for (const ch of source) {
    if (ch === ' ') { width += fontSize * 0.32; continue }
    if (/[A-Z]/.test(ch)) { width += fontSize * 0.64; continue }
    if (/[a-z0-9]/.test(ch)) { width += fontSize * 0.56; continue }
    if (/[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]/.test(ch)) { width += fontSize * 1.0; continue }
    if (/[.,;:!?'"`~_\-+=|/\\()[\]{}<>]/.test(ch)) { width += fontSize * 0.38; continue }
    width += fontSize * 0.74
  }

  const rounded = Math.ceil(width)
  if (textWidthCache.size > 6000) textWidthCache.clear()
  textWidthCache.set(cacheKey, rounded)
  return rounded
}

function normalizeLabelText(label) {
  if (label == null) return ''
  return String(label).replace(/\r\n/g, '\n').replace(/[ \t]+/g, ' ').trim()
}

export function wrapLabelLines(text, maxWidth, fontSize = LABEL_LAYOUT_CONFIG.fontSize) {
  const raw = String(text || '')
  if (!raw) return ['']
  const safeMaxWidth = Math.max(12, maxWidth)
  const paragraphs = raw.split('\n')
  const lines = []

  paragraphs.forEach(paragraph => {
    if (!paragraph) { lines.push(''); return }
    let current = ''
    for (const ch of paragraph) {
      const candidate = current + ch
      if (current && measureTextApprox(candidate, fontSize) > safeMaxWidth) {
        lines.push(current)
        current = ch
      } else {
        current = candidate
      }
    }
    if (current) lines.push(current)
  })

  return lines.length ? lines : ['']
}

// --- Label layout building ---

function getLabelMaxWidth(canvasWidth) {
  const width = canvasWidth || 360
  return clamp(
    Math.round(width * LABEL_LAYOUT_CONFIG.maxWidthRatio),
    LABEL_LAYOUT_CONFIG.minWidth,
    LABEL_LAYOUT_CONFIG.maxWidthCap
  )
}

export function buildNodeLabelLayout(node, canvasWidth) {
  const fontSize = LABEL_LAYOUT_CONFIG.fontSize
  const lineHeight = Math.round(fontSize * LABEL_LAYOUT_CONFIG.lineHeightRatio)
  const maxWidth = getLabelMaxWidth(canvasWidth)
  const text = normalizeLabelText(node && node.label)
  const innerMaxWidth = Math.max(12, maxWidth - LABEL_LAYOUT_CONFIG.paddingX * 2)
  const lines = wrapLabelLines(text, innerMaxWidth, fontSize)
  const contentWidth = lines.reduce(
    (max, line) => Math.max(max, measureTextApprox(line, fontSize)), 0
  )
  const width = clamp(
    Math.ceil(contentWidth + LABEL_LAYOUT_CONFIG.paddingX * 2),
    LABEL_LAYOUT_CONFIG.minWidth,
    maxWidth
  )
  const height = Math.max(
    lineHeight + LABEL_LAYOUT_CONFIG.paddingY * 2,
    Math.ceil(lines.length * lineHeight + LABEL_LAYOUT_CONFIG.paddingY * 2)
  )

  return { lines, width, height, fontSize, lineHeight, paddingX: LABEL_LAYOUT_CONFIG.paddingX, paddingY: LABEL_LAYOUT_CONFIG.paddingY, text }
}

function getNodeLabelLayout(node, layoutCache, canvasWidth) {
  if (node.labelSize && node.labelLines) return node.labelSize
  if (layoutCache) {
    const cached = layoutCache.get(node.id)
    if (cached) return cached
  }
  return buildNodeLabelLayout(node, canvasWidth)
}

function getNodeLayoutFootprint(node, layout) {
  const radius = getNodeBaseRadius(node)
  if (!layout) return radius + 8
  const halfW = layout.width / 2
  const verticalExtent = radius + LABEL_LAYOUT_CONFIG.nodeLabelGap + layout.height / 2
  const diagonalReach = Math.sqrt(halfW * halfW + verticalExtent * verticalExtent)
  return Math.max(radius + 8, diagonalReach + LABEL_LAYOUT_CONFIG.collisionPadding)
}

export function getLabelBoxByPosition(node, layout, position) {
  const radius = getNodeBaseRadius(node)
  const gap = LABEL_LAYOUT_CONFIG.nodeLabelGap
  const halfW = layout.width / 2
  const halfH = layout.height / 2
  const diagonalX = radius + gap + halfW * 0.72
  const diagonalY = radius + gap + halfH * 0.72
  let centerX = node.x
  let centerY = node.y + radius + gap + halfH

  switch (position) {
    case 'top': centerY = node.y - radius - gap - halfH; break
    case 'left': centerX = node.x - radius - gap - halfW; centerY = node.y; break
    case 'right': centerX = node.x + radius + gap + halfW; centerY = node.y; break
    case 'br': centerX = node.x + diagonalX; centerY = node.y + diagonalY; break
    case 'bl': centerX = node.x - diagonalX; centerY = node.y + diagonalY; break
    case 'tr': centerX = node.x + diagonalX; centerY = node.y - diagonalY; break
    case 'tl': centerX = node.x - diagonalX; centerY = node.y - diagonalY; break
    case 'bottom': default: centerX = node.x; centerY = node.y + radius + gap + halfH; break
  }

  return {
    box: { x: centerX - halfW, y: centerY - halfH, width: layout.width, height: layout.height },
    anchor: { position, x: centerX, y: centerY }
  }
}

// --- Tree building from API data ---

export function buildTreeFromEdges(apiNodes, apiEdges) {
  const safeEdges = apiEdges || []
  const treeEdges = safeEdges.filter(e => e.type === 'knowledge_tree')
  const parentMap = new Map()
  const childrenMap = new Map()

  treeEdges.forEach(e => {
    parentMap.set(e.to_node_id, e.from_node_id)
    if (!childrenMap.has(e.from_node_id)) childrenMap.set(e.from_node_id, [])
    childrenMap.get(e.from_node_id).push(e.to_node_id)
  })

  // Detect and break cycles in parent chain (defense in depth)
  const detectCycle = (nodeId, visited = new Set()) => {
    if (visited.has(nodeId)) return true
    visited.add(nodeId)
    const parentId = parentMap.get(nodeId)
    if (parentId) return detectCycle(parentId, visited)
    return false
  }

  const nodesToFix = []
  apiNodes.forEach(n => {
    if (parentMap.has(n.id) && detectCycle(n.id)) {
      nodesToFix.push(n.id)
    }
  })
  nodesToFix.forEach(id => {
    console.warn(`[graph-layout] Breaking cycle for node: ${id}`)
    parentMap.delete(id)
  })

  // BFS to assign levels
  const roots = apiNodes.filter(n => !parentMap.has(n.id))
  const levels = new Map()
  const queue = roots.map(r => ({ id: r.id, level: 0 }))

  let head = 0
  while (head < queue.length) {
    const { id, level } = queue[head++]
    if (levels.has(id)) continue
    levels.set(id, level)
    const children = childrenMap.get(id) || []
    children.forEach(cid => {
      if (!levels.has(cid)) queue.push({ id: cid, level: level + 1 })
    })
  }

  // Convert to local node format
  const nodes = apiNodes.map(n => ({
    id: n.id,
    label: n.label,
    level: levels.get(n.id) || 0,
    mastery: n.mastery,
    parent: parentMap.get(n.id) || null,
    collapsed: false,
    x: 0, y: 0,
    labelLines: [],
    labelSize: null,
    labelBox: null,
    labelAnchor: null,
    layoutFootprint: 0,
    targetX: 0, targetY: 0,
    angle: 0, targetAngle: 0
  }))

  const edges = safeEdges.map(e => ({
    from: e.from_node_id,
    to: e.to_node_id,
    type: e.type
  }))

  // Build learning path
  const pathEdges = safeEdges.filter(e => e.type === 'learning_path')
  const learningPath = []
  if (pathEdges.length > 0) {
    const pathNodeSet = new Set()
    pathEdges.forEach(e => {
      pathNodeSet.add(e.from_node_id)
      pathNodeSet.add(e.to_node_id)
    })
    learningPath.push(...Array.from(pathNodeSet))
  }

  return { nodes, edges, learningPath, childrenMap }
}

// --- Concentric circle layout ---

export function computeLayout(nodes, canvasWidth, canvasHeight) {
  if (!nodes || nodes.length === 0) return

  const layoutCache = new Map()

  // Build label layout cache
  nodes.forEach(node => {
    const layout = buildNodeLabelLayout(node, canvasWidth)
    layoutCache.set(node.id, layout)
    node.labelLines = layout.lines
    node.labelSize = layout
    node.layoutFootprint = getNodeLayoutFootprint(node, layout)
    if (!node.labelAnchor) {
      node.labelAnchor = {
        position: 'bottom',
        x: node.x || 0,
        y: (node.y || 0) + getNodeBaseRadius(node) + LABEL_LAYOUT_CONFIG.nodeLabelGap + layout.height / 2
      }
    }
    if (!node.labelBox) {
      node.labelBox = getLabelBoxByPosition(node, layout, 'bottom').box
    }
  })

  // Build level radius map
  const levelRadiusMap = buildLevelRadiusMap(nodes, layoutCache, canvasWidth)

  // Build childrenMap and nodeMap for efficient lookups
  const childrenMap = new Map()
  const nodeMap = new Map()
  nodes.forEach(n => {
    nodeMap.set(n.id, n)
    if (n.parent != null) {
      if (!childrenMap.has(n.parent)) childrenMap.set(n.parent, [])
      childrenMap.get(n.parent).push(n.id)
    }
  })

  const root = nodes.find(n => n.level === 0)
  if (!root) return

  // Root at center
  root.x = 0
  root.y = 0
  root.angle = 0
  root.targetAngle = 0

  // Recursive subtree layout
  layoutSubtree(nodes, root, 0, Math.PI * 2, levelRadiusMap, childrenMap, nodeMap)

  // Save target positions
  nodes.forEach(node => {
    node.targetX = node.x
    node.targetY = node.y
  })

  // Collision resolution
  resolveNodeAndLabelCollisions(nodes, levelRadiusMap, layoutCache, canvasWidth)

  // Greedy label placement
  placeLabelsGreedy(nodes, layoutCache, canvasWidth, canvasHeight)
}

function buildLevelRadiusMap(nodes, layoutCache, canvasWidth) {
  const map = new Map()
  if (!nodes || nodes.length === 0) return map

  const root = nodes.find(n => n.level === 0)
  let prevRadius = 0
  let prevFootprint = root ? getNodeLayoutFootprint(root, getNodeLabelLayout(root, layoutCache, canvasWidth)) : 0
  const maxLevel = nodes.reduce((max, node) => Math.max(max, node.level || 0), 0)

  for (let level = 1; level <= maxLevel; level++) {
    const levelNodes = nodes.filter(n => n.level === level)
    if (levelNodes.length === 0) continue

    const baseRadius = LAYOUT_CONFIG.baseRadius + (level - 1) * LAYOUT_CONFIG.levelSpacing
    let requiredCircumference = 0
    let maxFootprint = 0

    levelNodes.forEach(node => {
      const layout = getNodeLabelLayout(node, layoutCache, canvasWidth)
      const footprint = getNodeLayoutFootprint(node, layout)
      requiredCircumference += Math.max(
        footprint * 1.42,
        getNodeBaseRadius(node) * 2 + LABEL_LAYOUT_CONFIG.collisionPadding * 2
      )
      maxFootprint = Math.max(maxFootprint, footprint)
    })

    const radiusByCircumference = requiredCircumference / (Math.PI * 2)
    const radialGap = Math.max(
      LAYOUT_CONFIG.levelSpacing * 0.72,
      prevFootprint + maxFootprint * 0.62 + LABEL_LAYOUT_CONFIG.nodeLabelGap * 2
    )
    const radiusByPrevLevel = prevRadius > 0 ? prevRadius + radialGap : baseRadius
    const radius = Math.max(baseRadius, radiusByCircumference, radiusByPrevLevel)

    map.set(level, radius)
    prevRadius = radius
    prevFootprint = maxFootprint
  }

  return map
}

function getLevelRadius(level, levelRadiusMap) {
  if (level <= 0) return 0
  if (levelRadiusMap && levelRadiusMap.has(level)) return levelRadiusMap.get(level)
  return LAYOUT_CONFIG.baseRadius + (level - 1) * LAYOUT_CONFIG.levelSpacing
}

function getSubtreeSize(nodeId, childrenMap) {
  const children = childrenMap.get(nodeId) || []
  if (children.length === 0) return 1
  return 1 + children.reduce((sum, cid) => sum + getSubtreeSize(cid, childrenMap), 0)
}

function layoutSubtree(nodes, parent, angleStart, angleEnd, levelRadiusMap, childrenMap, nodeMap) {
  const childIds = childrenMap.get(parent.id) || []
  const children = childIds.map(cid => nodeMap.get(cid)).filter(Boolean)
  if (children.length === 0) return

  const subtreeSizes = children.map(c => getSubtreeSize(c.id, childrenMap))
  const totalSize = subtreeSizes.reduce((a, b) => a + b, 0)
  const radius = getLevelRadius(parent.level + 1, levelRadiusMap)

  let currentAngle = angleStart
  children.forEach((child, i) => {
    const angleRange = (subtreeSizes[i] / totalSize) * (angleEnd - angleStart)
    const childAngle = currentAngle + angleRange / 2

    child.x = Math.cos(childAngle) * radius
    child.y = Math.sin(childAngle) * radius
    child.angle = normalizeAnglePositive(childAngle)
    child.targetAngle = child.angle

    layoutSubtree(nodes, child, currentAngle, currentAngle + angleRange, levelRadiusMap, childrenMap, nodeMap)
    currentAngle += angleRange
  })
}

function resolveNodeAndLabelCollisions(nodes, levelRadiusMap, layoutCache, canvasWidth) {
  if (!nodes || nodes.length <= 1) return

  const iterations = 140
  const springStrength = 0.14
  const pushScale = 0.9
  const maxStep = 0.12
  const byLevel = new Map()

  nodes.forEach(node => {
    const level = node.level || 0
    if (level <= 0) return
    if (!byLevel.has(level)) byLevel.set(level, [])

    const angle = normalizeAnglePositive(Math.atan2(node.y, node.x))
    node.angle = angle
    node.targetAngle = node.targetAngle == null ? angle : normalizeAnglePositive(node.targetAngle)
    node.layoutFootprint = getNodeLayoutFootprint(node, getNodeLabelLayout(node, layoutCache, canvasWidth))
    byLevel.get(level).push(node)
  })

  for (let iter = 0; iter < iterations; iter++) {
    byLevel.forEach((levelNodes, level) => {
      if (!levelNodes || levelNodes.length === 0) return
      const radius = getLevelRadius(level, levelRadiusMap)
      if (!radius || radius <= 1) return

      const angleDelta = new Map()
      levelNodes.forEach(node => angleDelta.set(node.id, 0))

      for (let i = 0; i < levelNodes.length; i++) {
        const a = levelNodes[i]
        for (let j = i + 1; j < levelNodes.length; j++) {
          const b = levelNodes[j]
          const minAngle = Math.min(
            Math.PI - 0.02,
            ((a.layoutFootprint || getNodeLayoutFootprint(a)) +
              (b.layoutFootprint || getNodeLayoutFootprint(b)) +
              LABEL_LAYOUT_CONFIG.collisionPadding) / radius
          )
          const diff = normalizeAngleDiff(b.angle - a.angle)
          const absDiff = Math.abs(diff)
          if (absDiff >= minAngle) continue

          const overlap = minAngle - absDiff
          const sign = diff >= 0 ? 1 : -1
          const push = overlap * 0.5

          angleDelta.set(a.id, angleDelta.get(a.id) - sign * push)
          angleDelta.set(b.id, angleDelta.get(b.id) + sign * push)
        }
      }

      levelNodes.forEach(node => {
        const collisionPush = angleDelta.get(node.id) || 0
        const toTarget = normalizeAngleDiff(node.targetAngle - node.angle)
        const step = clamp(
          collisionPush * pushScale + toTarget * springStrength,
          -maxStep, maxStep
        )
        node.angle = normalizeAnglePositive(node.angle + step)
        node.x = Math.cos(node.angle) * radius
        node.y = Math.sin(node.angle) * radius
      })
    })
  }

  const root = nodes.find(n => n.level === 0)
  if (root) {
    root.x = 0
    root.y = 0
    root.angle = 0
    root.targetAngle = 0
  }
}

function getRectOverlapArea(a, b) {
  const left = Math.max(a.x, b.x)
  const right = Math.min(a.x + a.width, b.x + b.width)
  const top = Math.max(a.y, b.y)
  const bottom = Math.min(a.y + a.height, b.y + b.height)
  if (right <= left || bottom <= top) return 0
  return (right - left) * (bottom - top)
}

function placeLabelsGreedy(nodes, layoutCache, canvasWidth, canvasHeight) {
  if (!nodes || nodes.length === 0) return

  const width = canvasWidth || 360
  const height = canvasHeight || 640
  const halfW = Math.max(width * 0.95, 240)
  const halfH = Math.max(height * 0.95, 320)
  const bounds = { minX: -halfW, maxX: halfW, minY: -halfH, maxY: halfH }

  const placed = []
  const sortedNodes = [...nodes].sort((a, b) => {
    const layoutA = getNodeLabelLayout(a, layoutCache, canvasWidth)
    const layoutB = getNodeLabelLayout(b, layoutCache, canvasWidth)
    return layoutB.width * layoutB.height - layoutA.width * layoutA.height
  })

  sortedNodes.forEach(node => {
    const layout = getNodeLabelLayout(node, layoutCache, canvasWidth)
    let best = null

    LABEL_LAYOUT_CONFIG.candidatePositions.forEach((position, index) => {
      const candidate = getLabelBoxByPosition(node, layout, position)
      const box = candidate.box
      let score = index * 2.5

      placed.forEach(item => {
        const overlapArea = getRectOverlapArea(box, item.box)
        if (overlapArea > 0) score += overlapArea * 3.5
      })

      nodes.forEach(other => {
        if (other.id === node.id) return
        const otherRadius = getNodeBaseRadius(other) + 4
        const nearestX = clamp(other.x, box.x, box.x + box.width)
        const nearestY = clamp(other.y, box.y, box.y + box.height)
        const dx = other.x - nearestX
        const dy = other.y - nearestY
        const distSq = dx * dx + dy * dy
        const safeDistSq = otherRadius * otherRadius
        if (distSq < safeDistSq) score += (safeDistSq - distSq) * 1.8
      })

      if (box.x < bounds.minX) score += (bounds.minX - box.x) * 6
      if (box.y < bounds.minY) score += (bounds.minY - box.y) * 6
      if (box.x + box.width > bounds.maxX) score += (box.x + box.width - bounds.maxX) * 6
      if (box.y + box.height > bounds.maxY) score += (box.y + box.height - bounds.maxY) * 6

      const anchorDx = candidate.anchor.x - node.x
      const anchorDy = candidate.anchor.y - node.y
      score += Math.sqrt(anchorDx * anchorDx + anchorDy * anchorDy) * 0.32

      if (!best || score < best.score) best = { ...candidate, score }
    })

    if (!best) best = getLabelBoxByPosition(node, layout, 'bottom')

    node.labelBox = best.box
    node.labelAnchor = best.anchor
    node.labelLines = layout.lines
    node.labelSize = layout

    const anchorDx = Math.abs(best.anchor.x - node.x) + layout.width / 2
    const anchorDy = Math.abs(best.anchor.y - node.y) + layout.height / 2
    const labelReach = Math.sqrt(anchorDx * anchorDx + anchorDy * anchorDy)
    node.layoutFootprint = Math.max(
      getNodeLayoutFootprint(node, layout),
      labelReach + LABEL_LAYOUT_CONFIG.collisionPadding
    )

    placed.push({ nodeId: node.id, box: best.box })
  })
}
