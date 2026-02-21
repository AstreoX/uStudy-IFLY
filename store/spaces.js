import { defineStore } from 'pinia'
import { getSpaces, getSpaceGraph } from '@/api/space'

const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

export const useSpacesStore = defineStore('spaces', {
  state: () => ({
    spaces: [],
    spaceProgress: {},
    loading: false,
    lastFetchedAt: 0
  }),
  getters: {
    isCacheValid() {
      return this.spaces.length > 0 && (Date.now() - this.lastFetchedAt) < CACHE_TTL
    }
  },
  actions: {
    async loadSpaces(force = false) {
      if (!force && this.isCacheValid) return
      if (this.loading) return

      this.loading = true
      try {
        const res = await getSpaces()
        this.spaces = res.data || res || []
        await this.loadAllProgress()
        this.lastFetchedAt = Date.now()
      } catch (error) {
        console.error('[SpacesStore] Failed to load spaces:', error)
        if (this.spaces.length === 0) {
          this.spaces = []
        }
      } finally {
        this.loading = false
      }
    },
    async loadAllProgress() {
      if (this.spaces.length === 0) return
      const results = await Promise.allSettled(
        this.spaces.map(space => getSpaceGraph(space.id))
      )
      const progress = {}
      results.forEach((result, index) => {
        const spaceId = this.spaces[index].id
        if (result.status === 'fulfilled') {
          const graph = result.value.data || result.value || {}
          const nodes = graph.nodes || []
          if (nodes.length === 0) {
            progress[spaceId] = 0
          } else {
            const mastered = nodes.filter(n => (n.mastery || 0) >= 70).length
            progress[spaceId] = Math.round((mastered / nodes.length) * 100)
          }
        } else {
          progress[spaceId] = 0
        }
      })
      this.spaceProgress = progress
    },
    invalidate() {
      this.lastFetchedAt = 0
    }
  }
})
