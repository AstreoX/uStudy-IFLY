<template>
  <view class="widget-card">
    <!-- Header -->
    <text class="cal-title">Calendar</text>

    <!-- Date Display -->
    <view class="cal-date-row">
      <view class="cal-date-pill">
        <text class="cal-date-pill-text">{{ todayMonth }}/{{ todayDay }}</text>
      </view>
      <view class="cal-date-info">
        <text class="cal-date-year">{{ year }}</text>
        <text class="cal-date-month">{{ monthName }}</text>
      </view>
    </view>

    <!-- Gradient separator -->
    <view class="cal-divider"></view>

    <!-- Calendar Grid -->
    <view class="cal-grid">
      <text
        v-for="(d, idx) in weekdays"
        :key="'w-' + d"
        class="cal-wh"
        :class="{ 'cal-wh-weekend': idx >= 5 }"
      >{{ d }}</text>
      <view
        v-for="(cell, i) in calendarCells"
        :key="'c-' + i"
        class="cal-cell"
        :class="{
          'cal-cell-other': cell.other,
          'cal-cell-today': cell.today,
          'cal-cell-weekend': cell.weekend && !cell.today && !cell.other,
          'cal-cell-weekend-other': cell.weekend && cell.other
        }"
      >
        <text class="cal-num">{{ cell.day }}</text>
      </view>
    </view>
  </view>
</template>

<script>
const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default {
  props: {
    variant: {
      type: String,
      default: 'large'
    }
  },
  data() {
    return {
      weekdays: WEEKDAYS
    }
  },
  computed: {
    year() {
      return new Date().getFullYear()
    },
    monthName() {
      return MONTH_NAMES[new Date().getMonth()]
    },
    todayDay() {
      return new Date().getDate()
    },
    todayMonth() {
      return new Date().getMonth() + 1
    },
    calendarCells() {
      const now = new Date()
      const y = now.getFullYear()
      const m = now.getMonth()
      const todayDate = now.getDate()
      const todayM = now.getMonth()
      const todayY = now.getFullYear()

      const firstDayOfMonth = new Date(y, m, 1).getDay()
      const startOffset = (firstDayOfMonth + 6) % 7
      const daysInMonth = new Date(y, m + 1, 0).getDate()
      const daysInPrevMonth = new Date(y, m, 0).getDate()

      const cells = []

      for (let i = startOffset - 1; i >= 0; i--) {
        cells.push({ day: daysInPrevMonth - i, other: true, today: false })
      }

      for (let d = 1; d <= daysInMonth; d++) {
        cells.push({
          day: d,
          other: false,
          today: d === todayDate && m === todayM && y === todayY
        })
      }

      let nextDay = 1
      while (cells.length < 42) {
        cells.push({ day: nextDay, other: true, today: false })
        nextDay++
      }

      return cells.map((cell, i) => ({
        ...cell,
        weekend: i % 7 >= 5
      }))
    }
  }
}
</script>

<style scoped>
.widget-card {
  background: var(--color-widget-bg);
  border: 1px solid var(--color-widget-border);
  border-radius: 16px;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  padding: 14px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  position: relative;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 4px 20px rgba(0, 0, 0, 0.15);
}

/* Header */
.cal-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--color-widget-header);
  margin-bottom: 6px;
  letter-spacing: 0.2px;
  position: relative;
  z-index: 1;
}

/* Date display row */
.cal-date-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cal-date-pill {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(79, 70, 229, 0.10));
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 10px;
  padding: 4px 12px;
}

.cal-date-pill-text {
  font-size: 28px;
  font-weight: 800;
  color: #FFFFFF;
  line-height: 1.15;
}

.cal-date-info {
  display: flex;
  flex-direction: column;
}

.cal-date-year {
  font-size: 16px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.2;
}

.cal-date-month {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.2;
}

/* Gradient separator */
.cal-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  margin-bottom: 6px;
  flex-shrink: 0;
}

/* Calendar Grid */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0;
  flex: 1;
  align-content: start;
}

/* Weekday headers */
.cal-wh {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.35);
  text-align: center;
  padding: 2px 0;
  font-weight: 600;
}

.cal-wh-weekend {
  color: rgba(59, 130, 246, 0.4);
}

/* Day cells */
.cal-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2.5px 0;
}

.cal-num {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  text-align: center;
  line-height: 1;
  font-weight: 500;
}

/* Other month days */
.cal-cell-other .cal-num {
  color: rgba(255, 255, 255, 0.18);
}

/* Weekend days — subtle blue tint */
.cal-cell-weekend .cal-num {
  color: rgba(120, 165, 255, 0.55);
}

.cal-cell-weekend-other .cal-num {
  color: rgba(120, 165, 255, 0.18);
}

/* Today highlight with glow */
.cal-cell-today {
  position: relative;
}

.cal-cell-today .cal-num {
  background: var(--color-accent-blue);
  color: #FFFFFF;
  font-weight: 700;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 0 8px rgba(59, 130, 246, 0.45),
    0 0 20px rgba(59, 130, 246, 0.15);
}

</style>
