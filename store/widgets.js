import { defineStore } from 'pinia'

const STORAGE_KEY = 'ustudy_widget_layout'
const MIGRATIONS_KEY = 'ustudy_widget_layout_migrations'
const MIGRATION_ADD_RADAR_V1 = 'add_radar_widget_v1'
const MIGRATION_WEATHER_UNIFY_V1 = 'weather_unify_v1'

const GRID_COLS = 10
const GRID_ROWS = 7

const DEFAULT_LAYOUT = [
  { id: 'cal-lg',     type: 'calendar',  variant: 'large',   col: 1,  row: 1, w: 2, h: 2 },
  { id: 'weather-sm', type: 'weather',   variant: 'default', col: 3,  row: 1, w: 2, h: 1 },
  { id: 'clock-dig',  type: 'clock',     variant: 'digital', col: 5,  row: 1, w: 2, h: 1 },
  { id: 'weather-lg', type: 'weather',   variant: 'default', col: 3,  row: 2, w: 2, h: 1 },
  { id: 'clock-ana',  type: 'clock',     variant: 'analog',  col: 5,  row: 2, w: 2, h: 1 },
  { id: 'subject-1',  type: 'subject',   variant: 'default', col: 1,  row: 3, w: 4, h: 2 },
  { id: 'radar-profile', type: 'radar',  variant: 'default', col: 1,  row: 5, w: 3, h: 2 },
  { id: 'previous',   type: 'previous',  variant: 'default', col: 5,  row: 3, w: 2, h: 3 },
  { id: 'subject-2',  type: 'subject',   variant: 'default', col: 7,  row: 1, w: 4, h: 2 },
  { id: 'updates',    type: 'updates',   variant: 'default', col: 8,  row: 3, w: 3, h: 3 }
]

export const WIDGET_CATALOG = [
  { type: 'calendar',  variant: 'large',   w: 2, h: 2, label: '日历',             icon: '/static/icons/phosphor/widget-picker/widget-calendar.svg',        desc: '2\u00D72 month view' },
  { type: 'clock',     variant: 'digital', w: 2, h: 1, label: '数字时钟',         icon: '/static/icons/phosphor/widget-picker/widget-digital-clock.svg',   desc: '2\u00D71 time display' },
  { type: 'clock',     variant: 'analog',  w: 2, h: 1, label: '模拟时钟',         icon: '/static/icons/phosphor/widget-picker/widget-analog-clock.svg',    desc: '2\u00D71 clock face' },
  { type: 'weather',   variant: 'default', w: 2, h: 1, label: '天气',             icon: '/static/icons/phosphor/widget-picker/widget-weather.svg',         desc: '2\u00D71 resizable' },
  { type: 'subject',   variant: 'default', w: 3, h: 2, label: '学习空间卡片',     icon: '/static/icons/phosphor/widget-picker/widget-space-card.svg',      desc: '3\u00D72 progress card' },
  { type: 'radar',     variant: 'default', w: 3, h: 2, label: '学习雷达',         icon: '/static/icons/phosphor/widget-picker/widget-radar.svg',           desc: '3\u00D72 radar + stats' },
  { type: 'previous',  variant: 'default', w: 2, h: 3, label: '学习空间（汇总）', icon: '/static/icons/phosphor/widget-picker/widget-space-summary.svg',   desc: '2\u00D73 history list' },
  { type: 'updates',   variant: 'default', w: 3, h: 3, label: '学习动态',         icon: '/static/icons/phosphor/widget-picker/widget-updates.svg',         desc: '3\u00D73 notifications' }
]

export const WIDGET_SIZES = {
  weather: [
    { w: 1, h: 1 },
    { w: 2, h: 1 }
  ],
  radar: [
    { w: 2, h: 2 },
    { w: 3, h: 2 }
  ],
  subject: [
    { w: 2, h: 2 },
    { w: 3, h: 2 },
    { w: 4, h: 2 }
  ]
}

let _nextId = 1

function generateId(type) {
  return `${type}-${Date.now()}-${_nextId++}`
}

function loadMigrations() {
  try {
    const saved = uni.getStorageSync(MIGRATIONS_KEY)
    if (!saved) return new Set()
    const parsed = typeof saved === 'string' ? JSON.parse(saved) : saved
    if (Array.isArray(parsed)) {
      return new Set(parsed.filter(item => typeof item === 'string'))
    }
  } catch {
    // ignore
  }
  return new Set()
}

function saveMigrations(migrations) {
  try {
    uni.setStorageSync(MIGRATIONS_KEY, JSON.stringify([...migrations]))
  } catch {
    // ignore
  }
}

function buildRadarWidget(widgets, col, row) {
  const baseId = 'radar-profile'
  const usedIds = new Set((widgets || []).map(w => w.id))
  let id = baseId
  let suffix = 1
  while (usedIds.has(id)) {
    id = `${baseId}-${suffix++}`
  }
  return {
    id,
    type: 'radar',
    variant: 'default',
    col,
    row,
    w: 3,
    h: 2
  }
}

function normalizeWeatherWidget(widget) {
  if (widget.type !== 'weather') return widget
  const w = Number(widget.w)
  const h = Number(widget.h)
  const isMini = w === 1 && h === 1
  return {
    ...widget,
    variant: 'default',
    w: isMini ? 1 : 2,
    h: 1
  }
}

function migrateLayout(layout) {
  if (!Array.isArray(layout)) return layout

  const applied = loadMigrations()
  let nextLayout = layout
  let changed = false

  if (!applied.has(MIGRATION_ADD_RADAR_V1)) {
    const hasRadar = nextLayout.some(w => w.type === 'radar')
    if (!hasRadar) {
      const spot = findEmptySpot(nextLayout, 3, 2)
      if (spot) {
        const migratedRadar = buildRadarWidget(nextLayout, spot.col, spot.row)
        nextLayout = [...nextLayout, migratedRadar]
        changed = true
      }
    }
    applied.add(MIGRATION_ADD_RADAR_V1)
  }

  if (!applied.has(MIGRATION_WEATHER_UNIFY_V1)) {
    let weatherChanged = false
    const normalized = nextLayout.map(widget => {
      const updated = normalizeWeatherWidget(widget)
      if (
        updated !== widget &&
        (updated.variant !== widget.variant || updated.w !== widget.w || updated.h !== widget.h)
      ) {
        weatherChanged = true
      }
      return updated
    })
    if (weatherChanged) {
      nextLayout = normalized
      changed = true
    }
    applied.add(MIGRATION_WEATHER_UNIFY_V1)
  }

  if (changed) {
    saveLayout(nextLayout)
  }

  saveMigrations(applied)
  return nextLayout
}

function loadLayout() {
  try {
    const saved = uni.getStorageSync(STORAGE_KEY)
    if (saved) {
      const parsed = typeof saved === 'string' ? JSON.parse(saved) : saved
      const migrated = migrateLayout(parsed)
      if (Array.isArray(migrated)) {
        return migrated
      }
    }
  } catch {
    // ignore
  }
  return null
}

function saveLayout(widgets) {
  try {
    uni.setStorageSync(STORAGE_KEY, JSON.stringify(widgets))
  } catch {
    // ignore
  }
}

function findEmptySpot(widgets, w, h) {
  // Build occupancy grid
  const occupied = new Set()
  for (const wgt of widgets) {
    for (let c = wgt.col; c < wgt.col + wgt.w; c++) {
      for (let r = wgt.row; r < wgt.row + wgt.h; r++) {
        occupied.add(`${c},${r}`)
      }
    }
  }

  // Scan row by row, column by column for a free w×h block
  for (let r = 1; r <= GRID_ROWS - h + 1; r++) {
    for (let c = 1; c <= GRID_COLS - w + 1; c++) {
      let fits = true
      for (let dc = 0; dc < w && fits; dc++) {
        for (let dr = 0; dr < h && fits; dr++) {
          if (occupied.has(`${c + dc},${r + dr}`)) {
            fits = false
          }
        }
      }
      if (fits) {
        return { col: c, row: r }
      }
    }
  }

  return null
}

export const useWidgetStore = defineStore('widgets', {
  state: () => ({
    widgets: loadLayout() || DEFAULT_LAYOUT.map(w => ({ ...w }))
  }),
  actions: {
    updateWidgetPosition(id, col, row) {
      this.widgets = this.widgets.map(w =>
        w.id === id ? { ...w, col, row } : w
      )
      saveLayout(this.widgets)
    },
    addWidget(catalogItem) {
      const spot = findEmptySpot(this.widgets, catalogItem.w, catalogItem.h)
      if (!spot) return null

      const newWidget = {
        id: generateId(catalogItem.type),
        type: catalogItem.type,
        variant: catalogItem.variant,
        col: spot.col,
        row: spot.row,
        w: catalogItem.w,
        h: catalogItem.h
      }

      this.widgets = [...this.widgets, newWidget]
      saveLayout(this.widgets)
      return newWidget
    },
    updateWidgetSize(id, w, h) {
      this.widgets = this.widgets.map(wgt =>
        wgt.id === id ? { ...wgt, w, h } : wgt
      )
      saveLayout(this.widgets)
    },
    removeWidget(id) {
      this.widgets = this.widgets.filter(w => w.id !== id)
      saveLayout(this.widgets)
    },
    resetLayout() {
      this.widgets = DEFAULT_LAYOUT.map(w => ({ ...w }))
      saveLayout(this.widgets)
    }
  }
})
