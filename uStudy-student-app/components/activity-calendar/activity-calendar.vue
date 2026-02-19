<template>
  <view class="activity-calendar">
    <view class="calendar-wrapper">
      <!-- Fixed labels column -->
      <view class="labels-column">
        <view class="label-spacer" />
        <view v-for="dayIndex in 7" :key="'l' + dayIndex" class="label-cell">
          <text v-if="dayLabels[dayIndex - 1]" class="day-label-text">{{ dayLabels[dayIndex - 1] }}</text>
        </view>
      </view>

      <!-- Scrollable grid -->
      <scroll-view
        scroll-x
        :scroll-left="scrollLeft"
        :show-scrollbar="false"
        class="grid-scroll"
      >
        <view class="grid-inner" :style="{ width: gridWidth + 'rpx' }">
          <!-- Month header row -->
          <view class="month-row">
            <view v-for="(week, wi) in weeks" :key="'m' + wi" class="month-cell">
              <text v-if="monthLabelMap[wi]" class="month-text">{{ monthLabelMap[wi] }}</text>
            </view>
          </view>

          <!-- 7 day rows (Mon=0 to Sun=6) -->
          <view v-for="dayIndex in 7" :key="dayIndex" class="day-row">
            <view
              v-for="(week, wi) in weeks"
              :key="'c' + wi"
              class="day-cell"
              :class="week[dayIndex - 1].isEmpty ? 'level-empty' : levelClass(week[dayIndex - 1].count)"
            />
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- Legend -->
    <view class="legend">
      <text class="legend-text">少</text>
      <view class="legend-cell level-0" />
      <view class="legend-cell level-1" />
      <view class="legend-cell level-2" />
      <view class="legend-cell level-3" />
      <text class="legend-text">多</text>
    </view>
  </view>
</template>

<script>
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const DAY_LABELS = ['一', '', '三', '', '五', '', '']
const CELL_SIZE = 20
const CELL_GAP = 4

export default {
  name: 'ActivityCalendar',

  props: {
    records: {
      type: Array,
      default: () => []
    },
    months: {
      type: Number,
      default: 3
    }
  },

  data() {
    return {
      dayLabels: DAY_LABELS,
      scrollLeft: 0
    }
  },

  computed: {
    recordMap() {
      const map = {}
      for (const r of this.records) {
        map[r.date] = r.activity_count
      }
      return map
    },

    weeks() {
      const today = new Date()
      const todayStr = this.fmtDate(today)

      const startDate = new Date(today.getFullYear(), today.getMonth() - this.months + 1, 1)
      const startDateStr = this.fmtDate(startDate)

      // Rewind to Monday of start date's week
      const dow = startDate.getDay()
      const mondayOffset = dow === 0 ? -6 : 1 - dow
      const gridStart = new Date(startDate)
      gridStart.setDate(gridStart.getDate() + mondayOffset)

      const result = []
      const cur = new Date(gridStart)

      while (this.fmtDate(cur) <= todayStr) {
        const week = []
        for (let d = 0; d < 7; d++) {
          const ds = this.fmtDate(cur)
          const isEmpty = ds < startDateStr || ds > todayStr
          week.push({
            date: ds,
            count: isEmpty ? 0 : (this.recordMap[ds] || 0),
            isEmpty
          })
          cur.setDate(cur.getDate() + 1)
        }
        result.push(week)
      }

      return result
    },

    gridWidth() {
      return this.weeks.length * (CELL_SIZE + CELL_GAP) - CELL_GAP
    },

    monthLabelMap() {
      const map = {}
      let prev = -1
      for (let i = 0; i < this.weeks.length; i++) {
        const firstVisible = this.weeks[i].find(c => !c.isEmpty)
        if (!firstVisible) continue
        const mi = Number(firstVisible.date.split('-')[1]) - 1
        if (mi !== prev) {
          map[i] = MONTH_NAMES[mi]
          prev = mi
        }
      }
      return map
    }
  },

  watch: {
    weeks: {
      immediate: true,
      handler() {
        this.scrollToEnd()
      }
    }
  },

  methods: {
    fmtDate(d) {
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${y}-${m}-${day}`
    },

    levelClass(count) {
      if (count === 0) return 'level-0'
      if (count <= 2) return 'level-1'
      if (count <= 5) return 'level-2'
      return 'level-3'
    },

    scrollToEnd() {
      this.scrollLeft = 0
      this.$nextTick(() => {
        this.$nextTick(() => {
          this.scrollLeft = 99999
        })
      })
    }
  }
}
</script>

<style scoped>
.activity-calendar {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.calendar-wrapper {
  display: flex;
  flex-direction: row;
}

.labels-column {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  margin-right: 4rpx;
}

.label-spacer {
  height: 28rpx;
}

.label-cell {
  height: 20rpx;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.day-label-text {
  font-size: 18rpx;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
}

.grid-scroll {
  flex: 1;
  min-width: 0;
}

.grid-inner {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

/* Month header */
.month-row {
  display: flex;
  flex-direction: row;
  gap: 4rpx;
  height: 28rpx;
  align-items: flex-end;
}

.month-cell {
  width: 20rpx;
  flex-shrink: 0;
  overflow: visible;
}

.month-text {
  font-size: 18rpx;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  line-height: 1;
}

/* Day rows */
.day-row {
  display: flex;
  flex-direction: row;
  gap: 4rpx;
}

.day-cell {
  width: 20rpx;
  height: 20rpx;
  border-radius: 4rpx;
  flex-shrink: 0;
}

/* Cell levels */
.level-empty {
  background: transparent;
}

.level-0 {
  background: rgba(255, 255, 255, 0.06);
}

.level-1 {
  background: rgba(52, 211, 153, 0.3);
}

.level-2 {
  background: rgba(52, 211, 153, 0.6);
}

.level-3 {
  background: rgba(52, 211, 153, 0.9);
}

/* Legend */
.legend {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;
  gap: 6rpx;
  margin-top: 12rpx;
}

.legend-cell {
  width: 20rpx;
  height: 20rpx;
  border-radius: 4rpx;
}

.legend-text {
  font-size: 18rpx;
  color: rgba(255, 255, 255, 0.4);
}
</style>
