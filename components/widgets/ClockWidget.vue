<template>
  <view class="widget-card">
    <template v-if="variant === 'digital'">
      <view class="clock-digital">
        <text class="clock-time">{{ timeStr }}</text>
        <text class="clock-date">{{ dateStr }}</text>
      </view>
    </template>

    <template v-else>
      <view class="clock-analog">
        <svg viewBox="0 0 100 100" class="clock-svg">
          <!-- Face -->
          <circle cx="50" cy="50" r="46" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="1" />
          <!-- Hour markers -->
          <line v-for="i in 12" :key="i"
            :x1="50 + 40 * Math.cos((i * 30 - 90) * Math.PI / 180)"
            :y1="50 + 40 * Math.sin((i * 30 - 90) * Math.PI / 180)"
            :x2="50 + 44 * Math.cos((i * 30 - 90) * Math.PI / 180)"
            :y2="50 + 44 * Math.sin((i * 30 - 90) * Math.PI / 180)"
            stroke="rgba(255,255,255,0.3)" stroke-width="1.5" stroke-linecap="round"
          />
          <!-- Hour hand -->
          <line x1="50" y1="50"
            :x2="50 + 24 * Math.cos(hourAngle)"
            :y2="50 + 24 * Math.sin(hourAngle)"
            stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round"
          />
          <!-- Minute hand -->
          <line x1="50" y1="50"
            :x2="50 + 32 * Math.cos(minuteAngle)"
            :y2="50 + 32 * Math.sin(minuteAngle)"
            stroke="#FFFFFF" stroke-width="1.5" stroke-linecap="round"
          />
          <!-- Second hand -->
          <line x1="50" y1="50"
            :x2="50 + 36 * Math.cos(secondAngle)"
            :y2="50 + 36 * Math.sin(secondAngle)"
            stroke="var(--color-accent-blue)" stroke-width="0.8" stroke-linecap="round"
          />
          <!-- Center dot -->
          <circle cx="50" cy="50" r="2" fill="#FFFFFF" />
        </svg>
        <text class="clock-zone">Local Time</text>
      </view>
    </template>
  </view>
</template>

<script>
export default {
  props: {
    variant: {
      type: String,
      default: 'digital'
    }
  },
  data() {
    const now = new Date()
    return {
      hours: now.getHours(),
      minutes: now.getMinutes(),
      seconds: now.getSeconds(),
      timer: null
    }
  },
  computed: {
    timeStr() {
      const h = String(this.hours).padStart(2, '0')
      const m = String(this.minutes).padStart(2, '0')
      return `${h}:${m}`
    },
    dateStr() {
      const now = new Date()
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
      return days[now.getDay()]
    },
    hourAngle() {
      return ((this.hours % 12) * 30 + this.minutes * 0.5 - 90) * Math.PI / 180
    },
    minuteAngle() {
      return (this.minutes * 6 + this.seconds * 0.1 - 90) * Math.PI / 180
    },
    secondAngle() {
      return (this.seconds * 6 - 90) * Math.PI / 180
    }
  },
  mounted() {
    this.timer = setInterval(() => {
      const now = new Date()
      this.hours = now.getHours()
      this.minutes = now.getMinutes()
      this.seconds = now.getSeconds()
    }, 1000)
  },
  beforeUnmount() {
    if (this.timer) {
      clearInterval(this.timer)
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
  padding: 16px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.clock-digital {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 2px;
}

.clock-time {
  font-size: 36px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: 2px;
  line-height: 1;
}

.clock-date {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.clock-analog {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 4px;
}

.clock-svg {
  width: 80%;
  max-width: 120px;
  aspect-ratio: 1;
}

.clock-zone {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
