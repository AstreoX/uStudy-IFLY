<template>
  <view class="grid-wrapper" ref="gridWrapper">
    <!-- Grid overlay (edit mode) -->
    <view v-if="editMode" class="grid-overlay" :style="gridStyle">
      <view
        v-for="cell in overlaCells"
        :key="cell.key"
        class="grid-overlay-cell"
        :class="{ 'cell-highlight': isHighlighted(cell.c, cell.r) }"
        :style="{ 'grid-column': cell.c, 'grid-row': cell.r }"
      ></view>
    </view>

    <!-- Widget grid -->
    <view class="grid-container" ref="gridContainer" :style="gridStyle">
      <view
        v-for="widget in widgets"
        :key="widget.id"
        class="grid-item"
        :class="{
          'grid-item-edit': editMode,
          'grid-item-dragging': draggingId === widget.id
        }"
        :style="getWidgetStyle(widget)"
        @pointerdown.prevent="onPointerDown($event, widget)"
      >
        <view v-if="editMode" class="drag-handle">
          <text class="drag-dots">:::</text>
        </view>
        <view v-if="editMode" class="delete-btn" @pointerdown.stop @tap="$emit('remove:widget', widget.id)">
          <text class="delete-x">&times;</text>
        </view>
        <view
          v-if="editMode && isResizable(widget)"
          class="resize-handle"
          @pointerdown.stop.prevent="onResizeDown($event, widget)"
        >
          <svg class="resize-arc" viewBox="-3 -3 22 22" fill="none">
            <path d="M16 0 C16 8.84 8.84 16 0 16" stroke="rgba(255,255,255,0.9)" stroke-width="4" stroke-linecap="round" fill="none"/>
          </svg>
        </view>
        <CalendarWidget v-if="widget.type === 'calendar'" :variant="widget.variant" />
        <ClockWidget v-else-if="widget.type === 'clock'" :variant="widget.variant" />
        <WeatherWidget v-else-if="widget.type === 'weather'" :variant="widget.variant" />
        <SubjectWidget v-else-if="widget.type === 'subject'" :widget-id="widget.id" :subject="getSubjectData(widget.id)" :spaces="spaces" :editMode="editMode" @select-subject="selectSubject(widget.id, $event)" />
        <PreviousWidget v-else-if="widget.type === 'previous'" :spaces="spaces" :graph-cache="graphCache" />
        <UpdatesWidget v-else-if="widget.type === 'updates'" />
      </view>
    </view>

    <!-- Drag ghost (floating element while dragging) -->
    <view
      v-if="dragGhost"
      class="drag-ghost"
      :style="dragGhostStyle"
    >
      <view class="drag-ghost-inner"></view>
    </view>
  </view>
</template>

<script>
import CalendarWidget from './CalendarWidget.vue'
import ClockWidget from './ClockWidget.vue'
import WeatherWidget from './WeatherWidget.vue'
import SubjectWidget from './SubjectWidget.vue'
import PreviousWidget from './PreviousWidget.vue'
import UpdatesWidget from './UpdatesWidget.vue'
import { getSpaces, getSpaceGraph } from '@/api/space'
import { WIDGET_SIZES } from '@/store/widgets'

const GRID_COLS = 10
const GRID_ROWS = 7
const GAP = 12

export default {
  components: {
    CalendarWidget,
    ClockWidget,
    WeatherWidget,
    SubjectWidget,
    PreviousWidget,
    UpdatesWidget
  },
  props: {
    widgets: {
      type: Array,
      required: true
    },
    editMode: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:widgets', 'remove:widget', 'resize:widget'],
  data() {
    return {
      spaces: [],
      graphCache: {},
      subjectMapping: {},
      isLoading: false,
      cellSize: 0,
      resizeObserver: null,
      draggingId: null,
      dragGhost: null,
      dragGhostStyle: {},
      dragStartCol: 0,
      dragStartRow: 0,
      dragOffsetX: 0,
      dragOffsetY: 0,
      highlightCol: -1,
      highlightRow: -1,
      highlightW: 0,
      highlightH: 0,
      cellWidth: 0,
      cellHeight: 0,
      gridRect: null,
      resizingId: null,
      resizeOrigW: 0,
      resizeOrigCol: 0,
      resizeStartX: 0
    }
  },
  computed: {
    gridStyle() {
      if (!this.cellSize) return {}
      return {
        'grid-template-rows': `repeat(${GRID_ROWS}, ${this.cellSize}px)`
      }
    },
    overlaCells() {
      const cells = []
      for (let r = 1; r <= GRID_ROWS; r++) {
        for (let c = 1; c <= GRID_COLS; c++) {
          cells.push({ key: `${r}-${c}`, r, c })
        }
      }
      return cells
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.calcCellSize()
    })
    this.resizeObserver = new ResizeObserver(() => {
      this.calcCellSize()
    })
    const el = this.$refs.gridContainer
    if (el) {
      const dom = el.$el || el
      this.resizeObserver.observe(dom)
    }
    this.loadSpaces()
    try {
      const saved = uni.getStorageSync('widget_subject_mapping')
      if (saved) {
        this.subjectMapping = JSON.parse(saved)
      }
    } catch (_) {}
  },
  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
    document.removeEventListener('pointermove', this.onPointerMove)
    document.removeEventListener('pointerup', this.onPointerUp)
    document.removeEventListener('pointermove', this.onResizeMove)
    document.removeEventListener('pointerup', this.onResizeUp)
  },
  methods: {
    calcCellSize() {
      const el = this.$refs.gridContainer
      if (!el) return
      const dom = el.$el || el
      const width = dom.clientWidth
      this.cellSize = (width - GAP * (GRID_COLS - 1)) / GRID_COLS
    },
    getWidgetStyle(widget) {
      const w = (this.resizingId === widget.id) ? this.highlightW : widget.w
      const h = (this.resizingId === widget.id) ? this.highlightH : widget.h
      return {
        'grid-column': `${widget.col} / span ${w}`,
        'grid-row': `${widget.row} / span ${h}`
      }
    },
    async loadSpaces() {
      this.isLoading = true
      try {
        const spaces = await getSpaces()
        this.spaces = spaces || []
        const results = await Promise.allSettled(
          this.spaces.map(async s => {
            const raw = await getSpaceGraph(s.id)
            return { spaceId: s.id, raw }
          })
        )
        const cache = {}
        for (const r of results) {
          if (r.status !== 'fulfilled') continue
          const { spaceId, raw } = r.value
          const nodes = (raw.nodes || []).map(n => ({ ...n }))
          const edges = (raw.edges || []).map(e => ({
            ...e,
            from: e.from_node_id || e.from,
            to: e.to_node_id || e.to
          }))
          cache[spaceId] = { nodes, edges }
        }
        this.graphCache = cache
      } catch (err) {
        // API failure — spaces stays empty, widgets show empty state
      } finally {
        this.isLoading = false
      }
    },
    async loadGraphData(spaceId) {
      try {
        const raw = await getSpaceGraph(spaceId)
        const nodes = (raw.nodes || []).map(n => ({ ...n }))
        const edges = (raw.edges || []).map(e => ({
          ...e,
          from: e.from_node_id || e.from,
          to: e.to_node_id || e.to
        }))
        this.graphCache = { ...this.graphCache, [spaceId]: { nodes, edges } }
      } catch (err) {
        console.warn('[WidgetGrid] loadGraphData failed for space', spaceId, err)
      }
    },
    calculateProgress(spaceId) {
      const graphData = this.graphCache[spaceId]
      if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        return { current: 0, total: 0, progress: 0 }
      }
      const total = graphData.nodes.length
      const current = graphData.nodes.filter(n => n.mastery != null && n.mastery >= 70).length
      const progress = Math.round((current / total) * 100)
      return { current, total, progress }
    },
    getSpaceForWidget(widgetId) {
      if (this.spaces.length === 0) return null
      const mappedId = this.subjectMapping[widgetId]
      if (mappedId) {
        return this.spaces.find(s => s.id === mappedId) || null
      }
      // Default: subject-1 → spaces[0], subject-2 → spaces[1]
      const subjectWidgets = this.widgets.filter(w => w.type === 'subject')
      const idx = subjectWidgets.findIndex(w => w.id === widgetId)
      const spaceIdx = Math.min(idx >= 0 ? idx : 0, this.spaces.length - 1)
      return this.spaces[spaceIdx] || null
    },
    getSubjectData(widgetId) {
      const space = this.getSpaceForWidget(widgetId)
      if (!space) {
        return { name: 'No space', current: 0, total: 0, progress: 0, graphData: null }
      }
      const graphData = this.graphCache[space.id] || null
      const { current, total, progress } = this.calculateProgress(space.id)
      return {
        name: space.name || 'Untitled',
        current,
        total,
        progress,
        graphData
      }
    },
    async selectSubject(widgetId, spaceId) {
      if (!spaceId) return
      const updated = {
        ...this.subjectMapping,
        [widgetId]: spaceId
      }
      this.subjectMapping = updated
      try {
        uni.setStorageSync('widget_subject_mapping', JSON.stringify(updated))
      } catch (_) {}
      if (!this.graphCache[spaceId]) {
        await this.loadGraphData(spaceId)
      }
    },
    isHighlighted(c, r) {
      if (!this.draggingId && !this.resizingId) return false
      return (
        c >= this.highlightCol &&
        c < this.highlightCol + this.highlightW &&
        r >= this.highlightRow &&
        r < this.highlightRow + this.highlightH
      )
    },
    measureGrid() {
      const el = this.$refs.gridContainer
      if (!el) return
      const dom = el.$el || el
      const rect = dom.getBoundingClientRect()
      const width = dom.clientWidth
      const cs = (width - GAP * (GRID_COLS - 1)) / GRID_COLS
      this.gridRect = rect
      this.cellSize = cs
      this.cellWidth = cs
      this.cellHeight = cs
    },
    onPointerDown(e, widget) {
      if (!this.editMode) return
      if (this.resizingId) return
      this.measureGrid()
      if (!this.gridRect) return

      this.draggingId = widget.id
      this.highlightW = widget.w
      this.highlightH = widget.h
      this.dragStartCol = widget.col
      this.dragStartRow = widget.row

      const cellTotalW = this.cellWidth + GAP
      const cellTotalH = this.cellHeight + GAP
      const widgetLeft = this.gridRect.left + (widget.col - 1) * cellTotalW
      const widgetTop = this.gridRect.top + (widget.row - 1) * cellTotalH
      this.dragOffsetX = e.clientX - widgetLeft
      this.dragOffsetY = e.clientY - widgetTop

      const ghostW = widget.w * this.cellWidth + (widget.w - 1) * GAP
      const ghostH = widget.h * this.cellHeight + (widget.h - 1) * GAP
      this.dragGhost = { w: ghostW, h: ghostH }
      this.dragGhostStyle = {
        left: (e.clientX - this.dragOffsetX) + 'px',
        top: (e.clientY - this.dragOffsetY) + 'px',
        width: ghostW + 'px',
        height: ghostH + 'px'
      }

      this.highlightCol = widget.col
      this.highlightRow = widget.row

      document.addEventListener('pointermove', this.onPointerMove)
      document.addEventListener('pointerup', this.onPointerUp)
    },
    onPointerMove(e) {
      if (!this.draggingId || !this.gridRect) return

      const ghostLeft = e.clientX - this.dragOffsetX
      const ghostTop = e.clientY - this.dragOffsetY

      this.dragGhostStyle = {
        ...this.dragGhostStyle,
        left: ghostLeft + 'px',
        top: ghostTop + 'px'
      }

      const cellTotalW = this.cellWidth + GAP
      const cellTotalH = this.cellHeight + GAP
      const relX = e.clientX - this.gridRect.left
      const relY = e.clientY - this.gridRect.top

      let col = Math.round(relX / cellTotalW - this.highlightW / 2) + 1
      let row = Math.round(relY / cellTotalH - this.highlightH / 2) + 1

      col = Math.max(1, Math.min(col, GRID_COLS - this.highlightW + 1))
      row = Math.max(1, Math.min(row, GRID_ROWS - this.highlightH + 1))

      this.highlightCol = col
      this.highlightRow = row
    },
    onPointerUp() {
      document.removeEventListener('pointermove', this.onPointerMove)
      document.removeEventListener('pointerup', this.onPointerUp)

      if (!this.draggingId) return

      const targetCol = this.highlightCol
      const targetRow = this.highlightRow

      if (!this.hasCollision(this.draggingId, targetCol, targetRow, this.highlightW, this.highlightH)) {
        this.$emit('update:widgets', {
          id: this.draggingId,
          col: targetCol,
          row: targetRow
        })
      }

      this.draggingId = null
      this.dragGhost = null
      this.highlightCol = -1
      this.highlightRow = -1
    },
    hasCollision(movingId, col, row, w, h) {
      for (const widget of this.widgets) {
        if (widget.id === movingId) continue
        const overlapX = col < widget.col + widget.w && col + w > widget.col
        const overlapY = row < widget.row + widget.h && row + h > widget.row
        if (overlapX && overlapY) return true
      }
      return false
    },
    isResizable(widget) {
      const sizes = WIDGET_SIZES[widget.type]
      return sizes && sizes.length > 1
    },
    onResizeDown(e, widget) {
      this.measureGrid()
      if (!this.gridRect) return

      this.resizingId = widget.id
      this.resizeOrigW = widget.w
      this.resizeOrigCol = widget.col
      this.resizeStartX = e.clientX

      this.highlightCol = widget.col
      this.highlightRow = widget.row
      this.highlightW = widget.w
      this.highlightH = widget.h

      document.addEventListener('pointermove', this.onResizeMove)
      document.addEventListener('pointerup', this.onResizeUp)
    },
    onResizeMove(e) {
      if (!this.resizingId || !this.gridRect) return

      const widget = this.widgets.find(w => w.id === this.resizingId)
      if (!widget) return

      const sizes = WIDGET_SIZES[widget.type]
      if (!sizes) return

      const cellTotalW = this.cellWidth + GAP
      // Widget left edge in viewport coords (stable — widget.col doesn't change during resize)
      const widgetLeftX = this.gridRect.left + (widget.col - 1) * cellTotalW
      // How many columns the mouse is from the widget's left edge (continuous)
      const rawCols = (e.clientX - widgetLeftX) / cellTotalW

      // Snap to the nearest available size
      let best = sizes[0]
      let bestDist = Math.abs(rawCols - best.w)
      for (let i = 1; i < sizes.length; i++) {
        const dist = Math.abs(rawCols - sizes[i].w)
        if (dist < bestDist) {
          best = sizes[i]
          bestDist = dist
        }
      }

      const newW = best.w
      const newH = best.h

      if (widget.col + newW - 1 > GRID_COLS) return
      if (widget.row + newH - 1 > GRID_ROWS) return
      if ((newW !== this.highlightW || newH !== this.highlightH) &&
          this.hasCollision(widget.id, widget.col, widget.row, newW, newH)) return

      this.highlightW = newW
      this.highlightH = newH
    },
    onResizeUp() {
      document.removeEventListener('pointermove', this.onResizeMove)
      document.removeEventListener('pointerup', this.onResizeUp)

      if (!this.resizingId) return

      const widget = this.widgets.find(w => w.id === this.resizingId)
      if (widget && (this.highlightW !== widget.w || this.highlightH !== widget.h)) {
        if (!this.hasCollision(widget.id, widget.col, widget.row, this.highlightW, this.highlightH)) {
          this.$emit('resize:widget', { id: widget.id, w: this.highlightW, h: this.highlightH })
        }
      }

      this.resizingId = null
      this.dragGhost = null
      this.highlightCol = -1
      this.highlightRow = -1
    }
  }
}
</script>

<style scoped>
.grid-wrapper {
  position: relative;
  width: 100%;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  grid-template-rows: repeat(7, 1fr);
  gap: 12px;
  width: 100%;
  position: relative;
  z-index: 1;
}

.grid-item {
  min-width: 0;
  min-height: 0;
  position: relative;
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.grid-item-edit {
  cursor: grab;
}

.grid-item-edit:hover {
  transform: scale(1.01);
}

.grid-item-dragging {
  opacity: 0.3;
  cursor: grabbing;
}

.drag-handle {
  position: absolute;
  top: 6px;
  right: 8px;
  z-index: 10;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  cursor: grab;
}

.drag-dots {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 1px;
}

.delete-btn {
  position: absolute;
  top: -6px;
  left: -6px;
  z-index: 10;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 1);
  transform: scale(1.15);
}

.delete-x {
  font-size: 14px;
  color: #FFFFFF;
  line-height: 1;
  font-weight: 600;
}

/* Grid overlay for edit mode */
.grid-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  grid-template-rows: repeat(7, 1fr);
  gap: 12px;
  z-index: 0;
  pointer-events: none;
}

.grid-overlay-cell {
  border: 1px dashed rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  transition: background 0.15s ease;
}

.cell-highlight {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.3);
}

/* Drag ghost */
.drag-ghost {
  position: fixed;
  z-index: 1000;
  pointer-events: none;
}

.drag-ghost-inner {
  width: 100%;
  height: 100%;
  border: 2px solid var(--color-accent-blue);
  border-radius: 16px;
  background: rgba(59, 130, 246, 0.08);
  opacity: 0.7;
}

/* Resize handle — arc matches widget border-radius: 16px */
.resize-handle {
  position: absolute;
  bottom: -8px;
  right: -8px;
  z-index: 10;
  width: 36px;
  height: 36px;
  cursor: nwse-resize;
}

.resize-arc {
  position: absolute;
  bottom: 5px;
  right: 5px;
  width: 22px;
  height: 22px;
  filter: drop-shadow(0 0 6px rgba(255, 255, 255, 0.25));
  transition: filter 0.15s;
}

.resize-handle:hover .resize-arc {
  filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.5));
}
</style>
