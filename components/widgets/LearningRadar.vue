<template>
  <view ref="container" class="radar-container">
    <view
      class="radar-canvas-wrapper"
      :style="{ width: canvasSize + 'px', height: canvasSize + 'px' }"
    >
      <canvas
        :id="canvasId"
        :canvas-id="canvasId"
        class="radar-canvas"
        :style="{ width: canvasSize + 'px', height: canvasSize + 'px' }"
      />
      <view
        v-for="anchor in labelAnchors"
        :key="anchor.index"
        class="label-tap-target"
        :style="tapTargetStyle(anchor)"
        @click.stop="onLabelTap(anchor)"
      />
    </view>
    <view v-if="showLegend" class="radar-legend">
      <view class="legend-item">
        <view class="legend-dot legend-dot--current" />
        <text class="legend-text">本周</text>
      </view>
      <view v-if="lastWeekValues" class="legend-item">
        <view class="legend-dot legend-dot--last" />
        <text class="legend-text">上周</text>
      </view>
    </view>
  </view>
</template>

<script>
const DIMENSIONS = ['连续性', '专注度', '深入程度', '理解程度', '知识结构', '复习情况']
const CURRENT_DEFAULTS = [0, 0, 0, 0, 0, 0]
const GRID_LEVELS = [20, 40, 60, 80, 100]
const TAP_TARGET_SIZE = 56

const COLORS = {
  grid: 'rgba(255, 255, 255, 0.08)',
  axis: 'rgba(255, 255, 255, 0.06)',
  current: {
    fill: 'rgba(52, 211, 153, 0.15)',
    stroke: 'rgba(52, 211, 153, 0.72)'
  },
  lastWeek: {
    fill: 'rgba(251, 191, 36, 0.10)',
    stroke: 'rgba(251, 191, 36, 0.45)'
  },
  label: 'rgba(255, 255, 255, 0.62)'
}

export default {
  name: 'LearningRadar',

  props: {
    currentValues: {
      type: Array,
      default: () => CURRENT_DEFAULTS
    },
    lastWeekValues: {
      type: Array,
      default: () => null
    },
    labels: {
      type: Array,
      default: () => DIMENSIONS
    },
    showLegend: {
      type: Boolean,
      default: true
    },
    layoutKey: {
      type: String,
      default: ''
    }
  },

  data() {
    return {
      canvasId: `learningRadar_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      canvasSize: 180,
      ctx: null,
      isDestroyed: false,
      _initRetryTimer: null,
      _drawTimer: null,
      resizeObserver: null,
      labelAnchors: []
    }
  },

  watch: {
    currentValues: {
      handler() {
        this.scheduleDraw()
      },
      deep: true
    },
    lastWeekValues: {
      handler() {
        this.scheduleDraw()
      },
      deep: true
    },
    labels: {
      handler() {
        this.scheduleDraw()
      },
      deep: true
    },
    showLegend() {
      this.measureSize()
      this.scheduleDraw()
    },
    layoutKey() {
      this.$nextTick(() => {
        this.measureSize()
        this.scheduleDraw()
      })
    }
  },

  mounted() {
    this.$nextTick(() => {
      this.measureSize()
      this.initCanvas()
      this.setupResizeObserver()
    })
  },

  beforeUnmount() {
    this.isDestroyed = true
    if (this._initRetryTimer) {
      clearTimeout(this._initRetryTimer)
      this._initRetryTimer = null
    }
    if (this._drawTimer) {
      clearTimeout(this._drawTimer)
      this._drawTimer = null
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
      this.resizeObserver = null
    }
    this.ctx = null
  },

  methods: {
    setupResizeObserver() {
      const container = this.$refs.container
      if (!container || typeof ResizeObserver === 'undefined') return

      const dom = container.$el || container
      this.resizeObserver = new ResizeObserver(() => {
        const changed = this.measureSize()
        if (changed) {
          this.scheduleDraw()
        }
      })
      this.resizeObserver.observe(dom)
    },

    measureSize() {
      const container = this.$refs.container
      if (!container) return false

      const dom = container.$el || container
      const width = dom.clientWidth || 0
      const height = dom.clientHeight || 0
      if (width <= 0) return false

      const legendReserve = this.showLegend ? 30 : 0
      const usableHeight = height > 0 ? Math.max(0, height - legendReserve) : width
      const measured = Math.max(120, Math.floor(Math.min(width, usableHeight)))
      if (measured === this.canvasSize) return false

      this.canvasSize = measured
      return true
    },

    tapTargetStyle(anchor) {
      const half = TAP_TARGET_SIZE / 2
      return {
        left: (anchor.x - half) + 'px',
        top: (anchor.y - half) + 'px',
        width: TAP_TARGET_SIZE + 'px',
        height: TAP_TARGET_SIZE + 'px'
      }
    },

    onLabelTap(anchor) {
      this.$emit('dimension-click', { index: anchor.index, label: anchor.label })
    },

    initCanvas(retryCount = 0) {
      if (this.isDestroyed) return

      try {
        this.ctx = uni.createCanvasContext(this.canvasId, this)
      } catch (_e) {
        this.ctx = null
      }

      if (!this.ctx) {
        if (retryCount < 8) {
          this._initRetryTimer = setTimeout(() => this.initCanvas(retryCount + 1), 160)
        }
        return
      }

      this.scheduleDraw()
    },

    scheduleDraw() {
      if (this.isDestroyed) return
      if (!this.ctx) {
        this.initCanvas()
        return
      }
      if (this._drawTimer) {
        clearTimeout(this._drawTimer)
      }
      this._drawTimer = setTimeout(() => {
        if (!this.isDestroyed) {
          this.drawRadar()
        }
      }, 16)
    },

    drawRadar() {
      if (!this.ctx || this.isDestroyed) return
      const sides = this.labels.length
      if (sides < 3) return

      const ctx = this.ctx
      const size = this.canvasSize
      const cx = size / 2
      const cy = size / 2
      const maxRadius = size * 0.30

      try {
        ctx.clearRect(0, 0, size, size)
        this.drawHexGridLines(ctx, cx, cy, maxRadius, sides)
        this.drawAxisLines(ctx, cx, cy, maxRadius, sides)
        if (this.lastWeekValues) {
          this.drawDataPolygon(ctx, cx, cy, maxRadius, sides, this.lastWeekValues, COLORS.lastWeek, false)
        }
        this.drawDataPolygon(ctx, cx, cy, maxRadius, sides, this.currentValues, COLORS.current, true)
        this.drawLabels(ctx, cx, cy, maxRadius, sides)
      } catch (_e) {
        // Keep widget resilient on draw failures
      }

      ctx.draw()
    },

    getHexPoint(cx, cy, radius, index, total) {
      const angle = (Math.PI * 2 / total) * index - Math.PI / 2
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle)
      }
    },

    drawHexGridLines(ctx, cx, cy, maxRadius, sides) {
      GRID_LEVELS.forEach(level => {
        const radius = (level / 100) * maxRadius
        ctx.beginPath()
        for (let i = 0; i <= sides; i++) {
          const point = this.getHexPoint(cx, cy, radius, i % sides, sides)
          if (i === 0) ctx.moveTo(point.x, point.y)
          else ctx.lineTo(point.x, point.y)
        }
        ctx.closePath()
        ctx.setStrokeStyle(COLORS.grid)
        ctx.setLineWidth(1)
        ctx.stroke()
      })
    },

    drawAxisLines(ctx, cx, cy, maxRadius, sides) {
      for (let i = 0; i < sides; i++) {
        const point = this.getHexPoint(cx, cy, maxRadius, i, sides)
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(point.x, point.y)
        ctx.setStrokeStyle(COLORS.axis)
        ctx.setLineWidth(1)
        ctx.stroke()
      }
    },

    normalizeValues(values, sides) {
      const arr = Array.isArray(values) ? values : []
      if (arr.length >= sides) return arr.slice(0, sides)
      return [...arr, ...Array(sides - arr.length).fill(0)]
    },

    trySetLineDash(ctx, pattern) {
      try {
        if (typeof ctx.setLineDash === 'function') {
          ctx.setLineDash(pattern)
        }
      } catch (_e) {
        // setLineDash may not be supported on every renderer
      }
    },

    drawPolygonPath(ctx, points) {
      ctx.beginPath()
      for (let i = 0; i < points.length; i++) {
        if (i === 0) ctx.moveTo(points[i].x, points[i].y)
        else ctx.lineTo(points[i].x, points[i].y)
      }
      ctx.closePath()
    },

    drawDataPolygon(ctx, cx, cy, maxRadius, sides, values, colors, isCurrentWeek) {
      const dataValues = this.normalizeValues(values, sides)
      const points = dataValues.map((value, index) => {
        const clamped = Math.min(100, Math.max(0, Number(value) || 0))
        const radius = (clamped / 100) * maxRadius
        return this.getHexPoint(cx, cy, radius, index, sides)
      })

      this.drawPolygonPath(ctx, points)
      ctx.setFillStyle(colors.fill)
      ctx.fill()

      this.drawPolygonPath(ctx, points)
      if (!isCurrentWeek) {
        this.trySetLineDash(ctx, [4, 4])
      }
      ctx.setStrokeStyle(colors.stroke)
      ctx.setLineWidth(isCurrentWeek ? 2 : 1.5)
      ctx.stroke()
      if (!isCurrentWeek) {
        this.trySetLineDash(ctx, [])
      }
    },

    drawLabels(ctx, cx, cy, maxRadius, sides) {
      const values = this.normalizeValues(this.currentValues, sides)
      const scoreFontSize = Math.max(11, Math.min(14, this.canvasSize / 17))
      const labelFontSize = Math.max(9, Math.min(12, this.canvasSize / 20))
      const preferredRadius = maxRadius + Math.max(18, this.canvasSize * 0.09)
      // Reserve horizontal safe area for label text so it stays inside the widget card.
      const labelSafePadding = Math.max(34, this.canvasSize * 0.19)
      const anchorRadius = Math.min(preferredRadius, Math.max(0, cx - labelSafePadding))
      const gap = 1
      const anchors = []

      const setHAlign = point => {
        if (typeof ctx.setTextAlign !== 'function') return
        if (Math.abs(point.x - cx) < 2) ctx.setTextAlign('center')
        else if (point.x < cx) ctx.setTextAlign('right')
        else ctx.setTextAlign('left')
      }

      this.labels.forEach((label, index) => {
        const point = this.getHexPoint(cx, cy, anchorRadius, index, sides)
        const yNudge = index === 0 ? -8 : (index === 3 ? 8 : 0)
        const labelY = point.y + yNudge
        anchors.push({ x: point.x, y: labelY, index, label })
        setHAlign(point)

        ctx.setFontSize(scoreFontSize)
        ctx.setFillStyle('rgba(52, 211, 153, 0.95)')
        if (typeof ctx.setTextBaseline === 'function') ctx.setTextBaseline('bottom')
        ctx.fillText(String(Math.round(values[index])), point.x, labelY - gap)

        ctx.setFontSize(labelFontSize)
        ctx.setFillStyle(COLORS.label)
        if (typeof ctx.setTextBaseline === 'function') ctx.setTextBaseline('top')
        ctx.fillText(label, point.x, labelY + gap)
      })

      this.labelAnchors = anchors
    }
  }
}
</script>

<style scoped>
.radar-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 0;
}

.radar-canvas-wrapper {
  position: relative;
  flex-shrink: 0;
}

.radar-canvas {
  display: block;
}

.label-tap-target {
  position: absolute;
  z-index: 1;
}

.radar-legend {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 8px;
}

.legend-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot--current {
  background-color: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.55);
}

.legend-dot--last {
  background-color: #fbbf24;
  opacity: 0.8;
}

.legend-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.62);
  line-height: 1;
}
</style>
