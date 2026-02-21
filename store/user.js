import { defineStore } from 'pinia'
import { getUser, setUser as persistUser, clearAuth } from '@/utils/storage'
import { useSpacesStore } from '@/store/spaces'

function resolveUserKey(user) {
  if (!user) return ''
  if (user.id !== undefined && user.id !== null) return `id:${user.id}`
  if (user.email) return `email:${user.email}`
  if (user.nickname) return `nick:${user.nickname}`
  return 'authed'
}

export const useUserStore = defineStore('user', {
  state: () => ({
    user: getUser()
  }),
  actions: {
    setUser(user) {
      const previousUserKey = resolveUserKey(this.user)
      const nextUserKey = resolveUserKey(user)
      this.user = user
      persistUser(user)
      if (previousUserKey !== nextUserKey) {
        const spacesStore = useSpacesStore()
        spacesStore.clear(nextUserKey)
      }
    },
    updateSubscription(subscription_tier, subscription_expires_at) {
      if (!this.user) return
      this.user = {
        ...this.user,
        subscription_tier,
        subscription_expires_at
      }
      persistUser(this.user)
    },
    clear() {
      this.user = null
      clearAuth()
      const spacesStore = useSpacesStore()
      spacesStore.clear()
    }
  }
})
