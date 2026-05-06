import { defineStore } from 'pinia'
import { getWalletStatus } from '@/api/wallet'

export const useWalletStore = defineStore('wallet', {
  state: () => ({
    status: null,
    loading: false
  }),
  getters: {
    balanceCents: (state) => state.status?.balance_cents || 0,
    availableCents: (state) => state.status?.available_cents || 0
  },
  actions: {
    async refresh() {
      this.loading = true
      try {
        this.status = await getWalletStatus()
        return this.status
      } finally {
        this.loading = false
      }
    }
  }
})
