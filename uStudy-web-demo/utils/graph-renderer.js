import { getMasteryColor, getMasteryGlowColor } from './mastery-colors'
import {
  UNMASTERED_NODE_COLOR, UNMASTERED_NODE_GLOW, UNMASTERED_NODE_OUTLINE,
  KNOWLEDGE_EDGE_COLOR, KNOWLEDGE_EDGE_WIDTH,
  LABEL_LAYOUT_CONFIG,
  getNodeBaseRadius, getLabelBoxByPosition, clamp
} from './graph-layout'

// --- Edge drawing ---

export function drawEdges(ctx, edgeBuckets, options = {}) {
  const { isPathHighlightOn, visibleNodeIds, viewportNodeIds } = options
  const buckets = edgeBuckets || { treeEdges: [], advancedEdges: [], pathEdges: [] }
  let renderedCount = 0

  // When path is highlighted, dim non-path edges
  if (isPathHighlightOn) {
    ctx.globalAlpha = 0.15
  }

  // 1. Tree edges (gray solid)
  buckets.treeEdges.forEach(edge => {
    if (visibleNodeIds && (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to))) return
    if (viewportNodeIds && !viewportNodeIds.has(edge.from) && !viewportNodeIds.has(edge.to)) return

    const fromNode = edge.fromNode
    const toNode = edge.toNode
    if (!fromNode || !toNode) return

    ctx.beginPath()
    ctx.moveTo(fromNode.x, fromNode.y)
    ctx.lineTo(toNode.x, toNode.y)
    ctx.strokeStyle = KNOWLEDGE_EDGE_COLOR
    ctx.lineWidth = KNOWLEDGE_EDGE_WIDTH
    ctx.setLineDash([])
    ctx.stroke()
    renderedCount++
  })

  // 2. Advanced edges (purple dashed)
  if (options.showAdvancedEdges !== false) {
    buckets.advancedEdges.forEach(edge => {
      if (visibleNodeIds && (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to))) return
      if (viewportNodeIds && !viewportNodeIds.has(edge.from) && !viewportNodeIds.has(edge.to)) return

      const fromNode = edge.fromNode
      const toNode = edge.toNode
      if (!fromNode || !toNode) return

      ctx.beginPath()
      ctx.moveTo(fromNode.x, fromNode.y)
      ctx.lineTo(toNode.x, toNode.y)
      ctx.strokeStyle = 'rgba(139, 92, 246, 0.5)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([5, 5])
      ctx.stroke()
      ctx.setLineDash([])
      renderedCount++
    })
  }

  // Restore alpha before drawing path edges
  if (isPathHighlightOn) {
    ctx.globalAlpha = 1.0
  }

  // 3. Learning path edges (blue solid + mid-arrow)
  if (isPathHighlightOn) {
    buckets.pathEdges.forEach(edge => {
      if (visibleNodeIds && (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to))) return
      if (viewportNodeIds && !viewportNodeIds.has(edge.from) && !viewportNodeIds.has(edge.to)) return

      const fromNode = edge.fromNode
      const toNode = edge.toNode
      if (!fromNode || !toNode) return

      drawPathEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y)
      renderedCount++
    })
  }

  return renderedCount
}

function drawPathEdge(ctx, x1, y1, x2, y2) {
  const color = '#0088FF'

  // Line
  ctx.beginPath()
  ctx.strokeStyle = color
  ctx.lineWidth = 3
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()

  // Arrow at midpoint
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2
  const angle = Math.atan2(y2 - y1, x2 - x1)
  const arrowSize = 8

  ctx.beginPath()
  ctx.fillStyle = color
  ctx.moveTo(midX + arrowSize * Math.cos(angle), midY + arrowSize * Math.sin(angle))
  ctx.lineTo(midX + arrowSize * Math.cos(angle + 2.5), midY + arrowSize * Math.sin(angle + 2.5))
  ctx.lineTo(midX + arrowSize * Math.cos(angle - 2.5), midY + arrowSize * Math.sin(angle - 2.5))
  ctx.closePath()
  ctx.fill()
}

// --- Rounded rect utility ---

export function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.max(0, Math.min(radius, Math.min(width, height) / 2))
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + width - r, y)
  ctx.arcTo(x + width, y, x + width, y + r, r)
  ctx.lineTo(x + width, y + height - r)
  ctx.arcTo(x + width, y + height, x + width - r, y + height, r)
  ctx.lineTo(x + r, y + height)
  ctx.arcTo(x, y + height, x, y + height - r, r)
  ctx.lineTo(x, y + r)
  ctx.arcTo(x, y, x + r, y, r)
  ctx.closePath()
}

// --- Node label block ---

export function drawNodeLabelBlock(ctx, node, options = {}) {
  const { alpha = 1 } = options
  const layout = node.labelSize
  if (!layout) return

  const fallback = getLabelBoxByPosition(node, layout, 'bottom')
  const labelBox = node.labelBox || fallback.box
  const labelAnchor = node.labelAnchor || fallback.anchor

  const nodeRadius = getNodeBaseRadius(node)

  ctx.save()
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0
  ctx.globalAlpha = clamp(alpha, 0, 1)

  // Connector line (when label is not directly below)
  if (labelAnchor.position !== 'bottom') {
    const connectorEndX = labelBox.x + labelBox.width / 2
    const connectorEndY = labelBox.y + labelBox.height / 2
    const dx = connectorEndX - node.x
    const dy = connectorEndY - node.y
    const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy))
    const ux = dx / dist
    const uy = dy / dist

    ctx.beginPath()
    ctx.moveTo(node.x + ux * (nodeRadius + 2), node.y + uy * (nodeRadius + 2))
    ctx.lineTo(connectorEndX - ux * 3, connectorEndY - uy * 3)
    ctx.strokeStyle = LABEL_LAYOUT_CONFIG.connectorColor
    ctx.lineWidth = 1
    ctx.stroke()
  }

  // Background rounded rect
  drawRoundedRect(ctx, labelBox.x, labelBox.y, labelBox.width, labelBox.height, LABEL_LAYOUT_CONFIG.cornerRadius)
  ctx.fillStyle = LABEL_LAYOUT_CONFIG.background
  ctx.fill()
  ctx.strokeStyle = LABEL_LAYOUT_CONFIG.borderColor
  ctx.lineWidth = 1
  ctx.stroke()

  // Text lines
  ctx.fillStyle = '#E2E8F0'
  ctx.font = `${layout.fontSize}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'

  let textY = labelBox.y + layout.paddingY
  layout.lines.forEach(line => {
    ctx.fillText(line, labelBox.x + labelBox.width / 2, textY)
    textY += layout.lineHeight
  })

  ctx.restore()
}

// --- Node drawing ---

export function drawNode(ctx, node, options = {}) {
  const { selectedNodeId, isPathHighlightOn, learningPathSet } = options
  const radius = getNodeBaseRadius(node)
  const isSelected = selectedNodeId === node.id
  const isOnPath = isPathHighlightOn && learningPathSet && learningPathSet.has(node.id)
  const isDimmed = isPathHighlightOn && !isOnPath && !isSelected

  if (isDimmed) ctx.globalAlpha = 0.25

  const fillColor = node.fillColor || (node.mastery == null ? UNMASTERED_NODE_COLOR : getMasteryColor(node.mastery))
  const glowColor = node.glowColor || (node.mastery == null ? UNMASTERED_NODE_GLOW : getMasteryGlowColor(node.mastery, 0.5))
  const outlineColor = node.outlineColor || (node.mastery == null ? UNMASTERED_NODE_OUTLINE : getMasteryGlowColor(node.mastery, 0.2))

  // Glow effect
  ctx.shadowColor = glowColor
  ctx.shadowBlur = 18
  ctx.shadowOffsetX = 0
  ctx.shadowOffsetY = 0

  // Semi-transparent outline circle
  ctx.beginPath()
  ctx.arc(node.x, node.y, radius + 4, 0, Math.PI * 2)
  ctx.fillStyle = outlineColor
  ctx.fill()

  // Main circle
  ctx.beginPath()
  ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
  ctx.fillStyle = fillColor
  ctx.fill()

  // Turn off shadow
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0

  // Selection ring
  if (isSelected) {
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius + 6, 0, Math.PI * 2)
    ctx.strokeStyle = '#FFFFFF'
    ctx.lineWidth = 3
    ctx.stroke()
  }

  // Path ring (blue, non-selected)
  if (isOnPath && !isSelected) {
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius + 5, 0, Math.PI * 2)
    ctx.strokeStyle = '#0088FF'
    ctx.lineWidth = 2
    ctx.stroke()
  }

  // Label
  const labelAlpha = isDimmed ? 0.25 : 1
  drawNodeLabelBlock(ctx, node, { alpha: labelAlpha })

  // Badge for collapsed nodes
  if (node.collapsed && node.childCount > 0) {
    drawBadge(ctx, node.x + radius - 2, node.y - radius + 2, node.childCount)
  }

  // Restore alpha
  if (isDimmed) ctx.globalAlpha = 1.0
}

// --- Learning path animation (ripple rings + edge growth) ---

export const PATH_RIPPLE_DURATION = 2000
const PATH_RIPPLE_COUNT = 3
const PATH_RIPPLE_STAGGER = 300
const PATH_RIPPLE_EXPAND_DURATION = 1200
export const PATH_EDGE_GROW_DURATION = 600

/**
 * Draw blue ripple rings for a node being highlighted in a learning path animation.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} node - Graph node
 * @param {Object} state - { startTime }
 * @returns {boolean} true if animation is still running
 */
export function drawPathHighlightRipple(ctx, node, state) {
  const elapsed = Date.now() - state.startTime
  if (elapsed > PATH_RIPPLE_DURATION) return false

  const radius = getNodeBaseRadius(node)

  ctx.save()
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0

  for (let i = 0; i < PATH_RIPPLE_COUNT; i++) {
    const ringElapsed = elapsed - i * PATH_RIPPLE_STAGGER
    if (ringElapsed < 0 || ringElapsed > PATH_RIPPLE_EXPAND_DURATION) continue

    const t = ringElapsed / PATH_RIPPLE_EXPAND_DURATION
    const easedT = 1 - Math.pow(1 - t, 3)
    const ringRadius = radius + 5 + easedT * 40
    const opacity = 0.5 * (1 - t)
    const lineWidth = 3 - 2.5 * t

    ctx.beginPath()
    ctx.arc(node.x, node.y, ringRadius, 0, Math.PI * 2)
    ctx.strokeStyle = `rgba(0, 136, 255, ${opacity})`
    ctx.lineWidth = Math.max(0.5, lineWidth)
    ctx.stroke()
  }

  ctx.restore()
  return true
}

/**
 * Draw an animated edge that grows from fromNode toward toNode.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} fromNode
 * @param {Object} toNode
 * @param {number} progress - 0..1
 */
export function drawAnimatedPathEdge(ctx, fromNode, toNode, progress) {
  const x1 = fromNode.x
  const y1 = fromNode.y
  const x2 = x1 + (toNode.x - x1) * progress
  const y2 = y1 + (toNode.y - y1) * progress

  ctx.save()
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0

  ctx.beginPath()
  ctx.strokeStyle = '#0088FF'
  ctx.lineWidth = 3
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()

  // Arrow at midpoint only when fully grown
  if (progress >= 0.99) {
    const midX = (fromNode.x + toNode.x) / 2
    const midY = (fromNode.y + toNode.y) / 2
    const angle = Math.atan2(toNode.y - fromNode.y, toNode.x - fromNode.x)
    const arrowSize = 8

    ctx.beginPath()
    ctx.fillStyle = '#0088FF'
    ctx.moveTo(midX + arrowSize * Math.cos(angle), midY + arrowSize * Math.sin(angle))
    ctx.lineTo(midX + arrowSize * Math.cos(angle + 2.5), midY + arrowSize * Math.sin(angle + 2.5))
    ctx.lineTo(midX + arrowSize * Math.cos(angle - 2.5), midY + arrowSize * Math.sin(angle - 2.5))
    ctx.closePath()
    ctx.fill()
  }

  ctx.restore()
}

// --- Mastery highlight animation (ripple rings + color transition) ---

const HIGHLIGHT_DURATION = 3000
const RIPPLE_COUNT = 3
const RIPPLE_STAGGER = 400
const RIPPLE_EXPAND_DURATION = 1500
const COLOR_TRANSITION_DURATION = 1000

/**
 * Draw highlight animation for a node that just received a mastery update.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} node - Graph node
 * @param {Object} state - { startTime, oldFillColor, oldGlowColor, newGlowColor }
 * @returns {boolean} true if animation is still running
 */
export function drawNodeHighlight(ctx, node, state) {
  const elapsed = Date.now() - state.startTime
  if (elapsed > HIGHLIGHT_DURATION) return false

  const radius = getNodeBaseRadius(node)

  ctx.save()
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0

  // Ripple rings
  for (let i = 0; i < RIPPLE_COUNT; i++) {
    const ringElapsed = elapsed - i * RIPPLE_STAGGER
    if (ringElapsed < 0 || ringElapsed > RIPPLE_EXPAND_DURATION) continue

    const t = ringElapsed / RIPPLE_EXPAND_DURATION
    const easedT = 1 - Math.pow(1 - t, 3) // easeOutCubic
    const ringRadius = radius + 5 + easedT * 40
    const opacity = 0.5 * (1 - t)
    const lineWidth = 3 - 2.5 * t

    ctx.beginPath()
    ctx.arc(node.x, node.y, ringRadius, 0, Math.PI * 2)
    ctx.strokeStyle = state.newGlowColor.replace(/[\d.]+\)$/, `${opacity})`)
    ctx.lineWidth = Math.max(0.5, lineWidth)
    ctx.stroke()
  }

  ctx.restore()

  // Color transition: lerp node colors during first 1s
  if (elapsed < COLOR_TRANSITION_DURATION) {
    const t = elapsed / COLOR_TRANSITION_DURATION
    node._highlightFillOverride = lerpColor(state.oldFillColor, node.fillColor, t)
    node._highlightGlowOverride = lerpColor(state.oldGlowColor, node.glowColor, t)
  } else {
    node._highlightFillOverride = null
    node._highlightGlowOverride = null
  }

  return true
}

/** Parse hex (#RRGGBB) or rgba() to {r,g,b,a} */
function parseColor(color) {
  if (!color) return { r: 156, g: 163, b: 175, a: 1 }

  if (color.startsWith('#')) {
    const hex = color.slice(1)
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16),
      a: 1
    }
  }

  const match = color.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/)
  if (match) {
    return {
      r: parseFloat(match[1]),
      g: parseFloat(match[2]),
      b: parseFloat(match[3]),
      a: match[4] !== undefined ? parseFloat(match[4]) : 1
    }
  }

  return { r: 156, g: 163, b: 175, a: 1 }
}

/** Lerp between two color strings, returns same format as target */
function lerpColor(fromStr, toStr, t) {
  const from = parseColor(fromStr)
  const to = parseColor(toStr)
  const r = Math.round(from.r + (to.r - from.r) * t)
  const g = Math.round(from.g + (to.g - from.g) * t)
  const b = Math.round(from.b + (to.b - from.b) * t)

  if (toStr && toStr.startsWith('rgba')) {
    const a = from.a + (to.a - from.a) * t
    return `rgba(${r}, ${g}, ${b}, ${a.toFixed(2)})`
  }
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

// --- Badge for collapsed child count ---

export function drawBadge(ctx, x, y, count) {
  const badgeRadius = 8

  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0

  ctx.beginPath()
  ctx.arc(x, y, badgeRadius, 0, Math.PI * 2)
  ctx.fillStyle = '#818CF8'
  ctx.fill()

  ctx.fillStyle = '#FFFFFF'
  ctx.font = '9px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(count.toString(), x, y)
}
