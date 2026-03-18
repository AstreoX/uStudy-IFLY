import { defineStore } from 'pinia'

export const useNotificationStore = defineStore('notification', {
  state: () => ({
    unreadCount: 0,
  }),
  actions: {
    setUnreadCount(count) {
      this.unreadCount = count
    },
    increment() {
      this.unreadCount++
    },
    decrement() {
      if (this.unreadCount > 0) this.unreadCount--
    },
    clearUnread() {
      this.unreadCount = 0
    },
  },
})
