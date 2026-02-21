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
