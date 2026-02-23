<template>
  <view class="widget-card" :class="['radar-widget-card', { 'radar-widget-card--compact': isCompactRadar }]">
    <view class="analytics-row" :class="{ 'analytics-row--compact': isCompactRadar }">
      <view class="analytics-left" :class="{ 'analytics-left--compact': isCompactRadar }">
        <LearningRadar
          :current-values="radarCurrentValues"
          :last-week-values="radarLastWeekValues"
          :show-legend="!isCompactRadar"
        />
      </view>
      <view v-if="!isCompactRadar" class="analytics-right">
        <view class="detail-grid">
          <view class="detail-row">
            <view class="detail-cell">
              <text class="detail-value">{{ studyDays }}</text>
              <text class="detail-label">学习天数</text>
            </view>
            <view class="detail-cell">
              <text class="detail-value">{{ displayAvgMastery }}</text>
              <text class="detail-label">平均掌握分</text>
            </view>
          </view>
          <view class="detail-row">
            <view class="detail-cell">
              <text class="detail-value">{{ formattedStudyHours }}</text>
              <text class="detail-label">总学时</text>
            </view>
            <view class="detail-cell">
              <text class="detail-value">{{ displayNodeCoverage }}%</text>
              <text class="detail-label">节点覆盖率</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import LearningRadar from './LearningRadar.vue'
import {
  getProfileStats,
  getContinuityScore,
  getFocusScore,
  getDepthScore,
  getComprehensionScore,
  getKnowledgeStructureScore,
  getReviewScore
} from '@/api/assessment'
import { saveRadarSnapshot, getLastWeekSnapshot } from '@/utils/radar-snapshot'

function toNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function formatOneDecimal(value) {
  const n = toNumber(value, 0)
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(1)
}

export default {
  name: 'RadarSummaryWidget',
  components: {
    LearningRadar
  },
  props: {
    widgetId: {
      type: String,
      default: ''
    },
    widgetW: {
      type: Number,
      default: 3
    },
    widgetH: {
      type: Number,
      default: 2
    }
  },
  data() {
    return {
      radarCurrentValues: [0, 0, 0, 0, 0, 0],
      radarLastWeekValues: null,
      studyDays: 0,
      totalStudyHours: 0,
      avgMastery: 0,
      nodeCoverage: 0
    }
  },
  computed: {
    formattedStudyHours() {
      const h = toNumber(this.totalStudyHours, 0)
      if (h <= 0) return '0h'
      if (h < 1) return `${h}h`
      return `${Math.round(h)}h`
    },
    displayAvgMastery() {
      return formatOneDecimal(this.avgMastery)
    },
    displayNodeCoverage() {
      return formatOneDecimal(this.nodeCoverage)
    },
    isCompactRadar() {
      return this.widgetW === 2 && this.widgetH === 2
    }
  },
  mounted() {
    this.radarLastWeekValues = getLastWeekSnapshot()
    this.loadAllData()
  },
  methods: {
    async loadAllData() {
      await Promise.allSettled([
        this.loadProfileStats(),
        this.loadRadarScoresAndSnapshot()
      ])
    },

    async loadProfileStats() {
      try {
        const result = await getProfileStats()
        this.studyDays = Math.round(toNumber(result.study_days, 0))
        this.totalStudyHours = toNumber(result.total_study_hours, 0)
        this.avgMastery = toNumber(result.avg_mastery, 0)
        this.nodeCoverage = toNumber(result.node_coverage_percent, 0)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadRadarScoresAndSnapshot() {
      await Promise.allSettled([
        this.loadContinuityScore(),
        this.loadFocusScore(),
        this.loadDepthScore(),
        this.loadComprehensionScore(),
        this.loadKnowledgeStructureScore(),
        this.loadReviewScore()
      ])
      saveRadarSnapshot(this.radarCurrentValues)
    },

    updateRadarValue(index, value) {
      const updated = [...this.radarCurrentValues]
      updated[index] = Math.round(toNumber(value, 0))
      this.radarCurrentValues = updated
    },

    async loadContinuityScore() {
      try {
        const result = await getContinuityScore()
        this.updateRadarValue(0, result.score)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadFocusScore() {
      try {
        const result = await getFocusScore(0)
        this.updateRadarValue(1, result.score)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadDepthScore() {
      try {
        const result = await getDepthScore(0)
        this.updateRadarValue(2, result.score)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadComprehensionScore() {
      try {
        const result = await getComprehensionScore()
        this.updateRadarValue(3, result.score)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadKnowledgeStructureScore() {
      try {
        const result = await getKnowledgeStructureScore()
        this.updateRadarValue(4, result.score)
      } catch (_e) {
        // Keep defaults
      }
    },

    async loadReviewScore() {
      try {
        const result = await getReviewScore()
        this.updateRadarValue(5, result.score)
      } catch (_e) {
        // Keep defaults
      }
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
  padding: 12px 14px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
}

.radar-widget-card {
  min-width: 0;
  min-height: 0;
}

.radar-widget-card--compact {
  padding: 8px;
}

.analytics-row {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  min-width: 0;
  min-height: 0;
}

.analytics-row--compact {
  align-items: center;
  justify-content: center;
}

.analytics-left {
  flex: 0 0 58%;
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-right: 10px;
}

.analytics-left--compact {
  flex: 1;
  width: 100%;
  height: 100%;
  padding-right: 0;
}

.analytics-right {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
}

.detail-grid {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-row {
  flex: 1;
  display: flex;
  flex-direction: row;
}

.detail-row + .detail-row {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.detail-cell {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 6px;
}

.detail-cell + .detail-cell {
  border-left: 1px solid rgba(255, 255, 255, 0.07);
}

.detail-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.05;
  color: rgba(255, 255, 255, 0.95);
  white-space: nowrap;
}

.detail-label {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.2;
  color: rgba(255, 255, 255, 0.48);
  white-space: nowrap;
}

@media (max-width: 1500px) {
  .detail-value {
    font-size: 20px;
  }

  .detail-label {
    font-size: 11px;
  }
}
</style>
