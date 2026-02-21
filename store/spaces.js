import { defineStore } from 'pinia'
import { getSpaces, getSpaceGraph } from '@/api/space'
import { getUser } from '@/utils/storage'

const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

function resolveOwnerKey() {
  const user = getUser()
  if (!user) return ''
  if (user.id !== undefined && user.id !== null) return `id:${user.id}`
  if (user.email) return `email:${user.email}`
  if (user.nickname) return `nick:${user.nickname}`
  return 'authed'
}

export const useSpacesStore = defineStore('spaces', {
  state: () => ({
    spaces: [],
    spaceProgress: {},
    loading: false,
    lastFetchedAt: 0,
    cacheOwnerKey: ''
  }),
  getters: {
    isCacheValid() {
      const currentOwnerKey = resolveOwnerKey()
      return (
        this.spaces.length > 0 &&
        !!this.cacheOwnerKey &&
        this.cacheOwnerKey === currentOwnerKey &&
        (Date.now() - this.lastFetchedAt) < CACHE_TTL
      )
    }
  },
  actions: {
    syncOwnerScope() {
      const ownerKey = resolveOwnerKey()
      if (ownerKey !== this.cacheOwnerKey) {
        this.clear(ownerKey)
      }
      return ownerKey
    },
    async loadSpaces(force = false) {
      const ownerKey = this.syncOwnerScope()
      if (!ownerKey) {
        this.clear('')
        return
      }

      if (!force && this.isCacheValid) return
      if (this.loading) return

      this.loading = true
      try {
        const res = await getSpaces()
        this.spaces = res.data || res || []
        this.cacheOwnerKey = ownerKey
        await this.loadAllProgress()
        this.lastFetchedAt = Date.now()
      } catch (error) {
        console.error('[SpacesStore] Failed to load spaces:', error)
        if (this.spaces.length === 0) {
          this.spaces = []
          this.spaceProgress = {}
        }
      } finally {
        this.loading = false
      }
    },
    async loadAllProgress() {
      if (this.spaces.length === 0) {
        this.spaceProgress = {}
        return
      }
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
    },
    clear(ownerKey = '') {
      this.spaces = []
      this.spaceProgress = {}
      this.loading = false
      this.lastFetchedAt = 0
      this.cacheOwnerKey = ownerKey
    }
  }
})
