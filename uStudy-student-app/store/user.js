import { defineStore } from 'pinia'
import { getUser, setUser as persistUser, clearAuth } from '@/utils/storage'
import { startTracking, stopTracking } from '@/utils/appUsageTracker'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: getUser()
  }),
  actions: {
    setUser(user) {
      this.user = user
      persistUser(user)
      if (user) {
        startTracking()
      }
    },
    updateNickname(nickname) {
      if (this.user) {
        this.user = { ...this.user, nickname }
        persistUser(this.user)
      }
    },
    updateAvatarUrl(avatar_url) {
      if (this.user) {
        this.user = { ...this.user, avatar_url }
        persistUser(this.user)
      }
    },
    updateSubscription(subscription_tier, subscription_expires_at) {
      if (this.user) {
        this.user = {
          ...this.user,
          subscription_tier,
          subscription_expires_at
        }
        persistUser(this.user)
      }
    },
    clear() {
      stopTracking()
      this.user = null
      clearAuth()
    }
  }
})
