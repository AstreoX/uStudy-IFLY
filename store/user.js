import { defineStore } from 'pinia'
import { getUser, setUser as persistUser, clearAuth } from '@/utils/storage'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: getUser()
  }),
  actions: {
    setUser(user) {
      this.user = user
      persistUser(user)
    },
    clear() {
      this.user = null
      clearAuth()
    }
  }
})
