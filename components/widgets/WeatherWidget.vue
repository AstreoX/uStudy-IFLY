<template>
  <view :class="['widget-card', `widget-card--${variant}`]">

    <!-- ===== MINI (1×1) ===== -->
    <template v-if="variant === 'mini'">
      <view class="mini-header">
        <text class="mini-title">WEATHER</text>
        <view class="mini-uv-dot" :style="{ background: uvColor }"></view>
      </view>
      <view class="mini-body">
        <view class="mini-icon-wrap">
          <svg viewBox="0 0 64 64" class="weather-svg">
            <path d="M48 34a10 10 0 0 0-9.8-8 14 14 0 0 0-27.1 4A8 8 0 0 0 12 46h36a10 10 0 0 0 0-12z"
                  fill="rgba(255,255,255,0.75)" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
            <line x1="22" y1="49" x2="19" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="32" y1="49" x2="29" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="42" y1="49" x2="39" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
          </svg>
        </view>
        <view class="mini-data">
          <text class="mini-temp">{{ currentTemp }}°</text>
          <text class="mini-condition">{{ condition }}</text>
        </view>
      </view>
      <text class="mini-stats">{{ humidity }}% · {{ windSpeed }}km/h</text>
    </template>

    <!-- ===== SMALL (2×1) ===== -->
    <template v-else-if="variant === 'small'">
      <view class="sm-main">
        <view class="sm-icon-wrap">
          <svg viewBox="0 0 64 64" class="weather-svg weather-svg--sm">
            <path d="M48 34a10 10 0 0 0-9.8-8 14 14 0 0 0-27.1 4A8 8 0 0 0 12 46h36a10 10 0 0 0 0-12z"
                  fill="rgba(255,255,255,0.75)" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
            <line x1="22" y1="49" x2="19" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="32" y1="49" x2="29" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="42" y1="49" x2="39" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
          </svg>
        </view>
        <view class="sm-temp-block">
          <text class="sm-temp-text">{{ currentTemp }}°C</text>
          <text class="sm-feels">feels {{ feelsLike }}°C</text>
        </view>
        <view class="sm-cond-block">
          <text class="sm-condition">{{ condition }}</text>
          <text class="sm-description">{{ description }}</text>
        </view>
      </view>
      <view class="sm-divider"></view>
      <view class="sm-stats">
        <view class="sm-stat">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <path d="M8 2C8 2 4 7.5 4 10a4 4 0 0 0 8 0c0-2.5-4-8-4-8z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
          </svg>
          <text class="sm-stat-val">{{ humidity }}%</text>
        </view>
        <view class="sm-stat">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <path d="M2 5c2-1.5 4 1.5 6 0s4 1.5 6 0M2 8.5c2-1.5 4 1.5 6 0s4 1.5 6 0M2 12c2-1.5 4 1.5 6 0s4 1.5 6 0" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
          </svg>
          <text class="sm-stat-val">{{ windSpeed }} km/h</text>
        </view>
        <view class="sm-stat">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.5" />
            <line x1="8" y1="1.5" x2="8" y2="3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="8" y1="12.5" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="1.5" y1="8" x2="3.5" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="12.5" y1="8" x2="14.5" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
          <text class="sm-stat-val">UV {{ uvIndex }}</text>
        </view>
      </view>
    </template>

    <!-- ===== LARGE (2×1) ===== -->
    <template v-else>
      <view class="lg-main">
        <view class="lg-icon-wrap">
          <svg viewBox="0 0 64 64" class="weather-svg weather-svg--lg">
            <path d="M48 34a10 10 0 0 0-9.8-8 14 14 0 0 0-27.1 4A8 8 0 0 0 12 46h36a10 10 0 0 0 0-12z"
                  fill="rgba(255,255,255,0.75)" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
            <line x1="22" y1="49" x2="19" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="32" y1="49" x2="29" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
            <line x1="42" y1="49" x2="39" y2="57" stroke="rgba(59,130,246,0.7)" stroke-width="2.5" stroke-linecap="round" />
          </svg>
        </view>
        <view class="lg-temp-block">
          <text class="lg-temp-text">{{ currentTemp }}°C</text>
          <text class="lg-feels">feels {{ feelsLike }}°C</text>
        </view>
        <view class="lg-cond-block">
          <text class="lg-condition">{{ condition }}</text>
          <text class="lg-description">{{ description }}</text>
        </view>
      </view>
      <view class="lg-divider"></view>
      <view class="lg-stats">
        <view class="lg-stat-pill">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <path d="M8 2C8 2 4 7.5 4 10a4 4 0 0 0 8 0c0-2.5-4-8-4-8z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
          </svg>
          <text class="lg-stat-val">{{ humidity }}%</text>
        </view>
        <view class="lg-stat-pill">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <path d="M2 5c2-1.5 4 1.5 6 0s4 1.5 6 0M2 8.5c2-1.5 4 1.5 6 0s4 1.5 6 0M2 12c2-1.5 4 1.5 6 0s4 1.5 6 0" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
          </svg>
          <text class="lg-stat-val">{{ windSpeed }}km/h</text>
        </view>
        <view class="lg-stat-pill">
          <svg viewBox="0 0 16 16" class="stat-icon">
            <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.5" />
            <line x1="8" y1="1.5" x2="8" y2="3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="8" y1="12.5" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="1.5" y1="8" x2="3.5" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <line x1="12.5" y1="8" x2="14.5" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
          <text class="lg-stat-val">UV {{ uvIndex }}</text>
        </view>
      </view>
      <text class="lg-link">Check recent weather &#8250;</text>
    </template>

  </view>
</template>

<script>
export default {
  props: {
    variant: {
      type: String,
      default: 'small'
    }
  },
  data() {
    return {
      currentTemp: 4,
      feelsLike: 2,
      tempLow: 2,
      tempHigh: 6,
      condition: 'Rain',
      description: 'Showers likely',
      humidity: 62,
      windSpeed: 5,
      uvIndex: 3
    }
  },
  computed: {
    uvColor() {
      if (this.uvIndex <= 2) return 'rgba(74, 222, 128, 0.85)'
      if (this.uvIndex <= 5) return 'rgba(250, 204, 21, 0.85)'
      if (this.uvIndex <= 7) return 'rgba(251, 146, 60, 0.85)'
      return 'rgba(248, 113, 113, 0.85)'
    }
  }
}
</script>

<style scoped>
/* ===== BASE CARD ===== */
.widget-card {
  background: var(--color-widget-bg);
  border: 1px solid var(--color-widget-border);
  border-radius: 16px;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
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

.widget-card--mini {
  padding: 8px 10px;
}

.widget-card--small,
.widget-card--large {
  padding: 10px 14px;
}

/* ===== SVG ICON SHARED ===== */
.weather-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 6px rgba(59, 130, 246, 0.35));
}

/* ===== STAT ICON SHARED ===== */
.stat-icon {
  width: 12px;
  height: 12px;
  color: var(--color-accent-blue, #3b82f6);
  opacity: 0.7;
  flex-shrink: 0;
}

/* ========================================
   MINI VARIANT (1×1, ~89×89px)
   ======================================== */
.mini-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
  flex-shrink: 0;
}

.mini-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-widget-header);
  letter-spacing: 0.8px;
  text-transform: uppercase;
}

.mini-uv-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.2);
}

.mini-body {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  min-height: 0;
}

.mini-icon-wrap {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
}

.mini-data {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.mini-temp {
  font-size: 18px;
  font-weight: 800;
  color: #FFFFFF;
  line-height: 1.1;
  text-shadow: 0 0 10px rgba(59, 130, 246, 0.2);
}

.mini-condition {
  font-size: 11px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.2;
}

.mini-stats {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1;
  flex-shrink: 0;
}

/* ========================================
   SMALL VARIANT (2×1, ~190×89px)
   ======================================== */
.sm-main {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-height: 0;
}

.sm-icon-wrap {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
}

.weather-svg--sm {
  width: 40px;
  height: 40px;
}

.sm-temp-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  flex-shrink: 0;
}

.sm-temp-text {
  font-size: 16px;
  font-weight: 800;
  color: #FFFFFF;
  line-height: 1.2;
}

.sm-feels {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
}

.sm-cond-block {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.sm-condition {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-widget-header);
  line-height: 1.2;
}

.sm-description {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sm-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  margin: 6px 0;
  flex-shrink: 0;
}

.sm-stats {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}

.sm-stat {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
}

.sm-stat-val {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1;
}

/* ========================================
   LARGE VARIANT (2×1, ~190×89px)
   ======================================== */
.lg-main {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.lg-icon-wrap {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
}

.weather-svg--lg {
  width: 36px;
  height: 36px;
}

.lg-temp-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  flex-shrink: 0;
}

.lg-temp-text {
  font-size: 15px;
  font-weight: 800;
  color: #FFFFFF;
  line-height: 1.2;
}

.lg-feels {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
}

.lg-cond-block {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.lg-condition {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-widget-header);
  line-height: 1.2;
}

.lg-description {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lg-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  margin: 5px 0;
  flex-shrink: 0;
}

.lg-stats {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.lg-stat-pill {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 3px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(79, 70, 229, 0.06));
  border: 1px solid rgba(59, 130, 246, 0.12);
  border-radius: 8px;
  padding: 2px 7px;
}

.lg-stat-val {
  font-size: 10px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1;
}

.lg-link {
  font-size: 10px;
  color: var(--color-accent-blue, #3b82f6);
  cursor: pointer;
  margin-top: auto;
  text-align: right;
  opacity: 0.8;
  transition: opacity 0.15s ease, text-shadow 0.15s ease;
}

.lg-link:hover {
  opacity: 1;
  text-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
}
</style>
