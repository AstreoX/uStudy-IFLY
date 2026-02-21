<template>
  <view class="widget-card">
    <text class="prev-title">Previous</text>
    <scroll-view scroll-y class="prev-list">
      <view v-for="space in spaces" :key="space.id" class="prev-item">
        <text class="prev-name">{{ space.name || 'Untitled' }}</text>
        <text class="prev-part">Part {{ getMastered(space.id) }}/{{ getTotal(space.id) }}</text>
        <template v-if="pathNodesMap[space.id] && pathNodesMap[space.id].length > 0">
          <view class="prev-path-wrap">
            <svg viewBox="0 0 200 24" class="prev-path">
              <!-- Baseline -->
              <line x1="10" y1="12" x2="190" y2="12" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round" />
              <!-- Arrows between consecutive nodes -->
              <polygon
                v-for="idx in (pathNodesMap[space.id].length - 1)"
                :key="'a-' + idx"
                :points="getArrowPoints(idx - 1, pathNodesMap[space.id].length)"
                fill="rgba(255,255,255,0.35)"
              />
              <!-- Mastery circles -->
              <circle
                v-for="(node, idx) in pathNodesMap[space.id]"
                :key="node.id"
                :cx="getCircleX(idx, pathNodesMap[space.id].length)"
                cy="12"
                r="5"
                :fill="getMasteryColor(node.mastery)"
                :stroke="getMasteryColor(node.mastery)"
                stroke-width="1.5"
                stroke-opacity="0.3"
              />
            </svg>
            <!-- Node labels (HTML, not SVG <text> which uni-app hijacks) -->
            <view class="prev-labels">
              <text
                v-for="(node, idx) in pathNodesMap[space.id]"
                :key="'t-' + node.id"
                class="prev-label"
                :style="{ left: getLabelPercent(idx, pathNodesMap[space.id].length) + '%' }"
              >{{ truncateLabel(node, pathNodesMap[space.id].length) }}</text>
            </view>
          </view>
        </template>
        <text v-else class="prev-no-path">暂无学习路径</text>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { getMasteryColor } from '@/utils/mastery-colors'

export default {
  props: {
    spaces: {
      type: Array,
      default: () => []
    },
    graphCache: {
      type: Object,
      default: () => ({})
    }
  },
  computed: {
    pathNodesMap() {
      const map = {}
      for (const space of this.spaces) {
        map[space.id] = this.getPathNodes(space.id)
      }
      return map
    }
  },
  methods: {
    getMasteryColor,

    getTotal(spaceId) {
      const graph = this.graphCache[spaceId]
      if (!graph || !graph.nodes) return 0
      return graph.nodes.length
    },

    getMastered(spaceId) {
      const graph = this.graphCache[spaceId]
      if (!graph || !graph.nodes) return 0
      return graph.nodes.filter(n => n.mastery != null && n.mastery >= 70).length
    },

    getPathNodes(spaceId) {
      const graph = this.graphCache[spaceId]
      if (!graph || !graph.edges || !graph.nodes) return []

      const pathEdges = graph.edges.filter(e => e.type === 'learning_path')
      if (pathEdges.length === 0) return []

      // Build nextNode map and toNodes set
      const nextNode = new Map()
      const toNodes = new Set()
      for (const edge of pathEdges) {
        nextNode.set(edge.from, edge.to)
        toNodes.add(edge.to)
      }

      // Find start node: appears in from but not in to
      let start = null
      for (const edge of pathEdges) {
        if (!toNodes.has(edge.from)) {
          start = edge.from
          break
        }
      }
      if (!start) return []

      // Walk the chain
      const nodeMap = new Map()
      for (const node of graph.nodes) {
        nodeMap.set(node.id, node)
      }

      const ordered = []
      const visited = new Set()
      let current = start
      const maxSteps = graph.nodes.length

      while (current && !visited.has(current) && ordered.length < maxSteps) {
        visited.add(current)
        const node = nodeMap.get(current)
        if (node) {
          ordered.push(node)
        }
        current = nextNode.get(current)
      }

      return ordered
    },

    getCircleX(idx, total) {
      if (total <= 1) return 100
      return 10 + (idx / (total - 1)) * 180
    },

    getArrowPoints(fromIdx, total) {
      const x1 = this.getCircleX(fromIdx, total)
      const x2 = this.getCircleX(fromIdx + 1, total)
      const midX = (x1 + x2) / 2
      // Right-pointing triangle at midpoint on the baseline (y=12)
      return `${midX + 3.5},12 ${midX - 2},8.5 ${midX - 2},15.5`
    },

    getLabelPercent(idx, total) {
      // Maps to same X positions as SVG circles: x=10..190 in viewBox 0..200
      if (total <= 1) return 50
      return 5 + (idx / (total - 1)) * 90
    },

    truncateLabel(node, total) {
      const label = (node.label || node.title || node.name || '').trim()
      if (!label) return ''
      if (total <= 1) return label.length > 16 ? label.slice(0, 15) + '\u2026' : label
      // Labels use percentage positioning matching SVG; each slot = 90%/(total-1) of container width
      // At font-size 10px, ~6px per char average. Container ~250px → slot ~250*0.9/(total-1) px
      // Conservative: allow slot_percent / 6 chars where slot_percent = 90/(total-1)
      const slotPercent = 90 / (total - 1)
      const maxChars = Math.max(1, Math.floor(slotPercent / 6))
      if (label.length <= maxChars) return label
      if (maxChars <= 1) return label.slice(0, 1)
      return label.slice(0, maxChars - 1) + '\u2026'
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

.prev-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-widget-header);
  margin-bottom: 12px;
}

.prev-list {
  flex: 1;
  overflow-y: auto;
}

/* Custom Scrollbar — matches dark glassmorphic theme */
.prev-list :deep(.uni-scroll-view)::-webkit-scrollbar {
  width: 6px;
}

.prev-list :deep(.uni-scroll-view)::-webkit-scrollbar-track {
  background: transparent;
}

.prev-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.prev-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.prev-list :deep(.uni-scroll-view) {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.prev-item {
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.prev-item:last-child {
  border-bottom: none;
}

.prev-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prev-part {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 6px;
}

.prev-path-wrap {
  position: relative;
}

.prev-path {
  display: block;
  width: 100%;
  height: auto;
}

.prev-labels {
  position: relative;
  height: 16px;
}

.prev-label {
  position: absolute;
  transform: translateX(-50%);
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
  line-height: 1;
}

.prev-no-path {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
}
</style>
