import { defineStore } from 'pinia'
import { getMyInvite } from '@/api/invite'

export const useInviteStore = defineStore('invite', {
  state: () => ({
    info: null,
    loading: false
  }),
  getters: {
    code: (state) => state.info?.code || '',
    inviteUrl: (state) => state.info?.invite_url || '',
    totalInvites: (state) => state.info?.total_invites || 0,
    totalRewardCents: (state) => state.info?.total_reward_cents || 0
  },
  actions: {
    async refresh() {
      this.loading = true
      try {
        this.info = await getMyInvite()
        return this.info
      } finally {
        this.loading = false
      }
    }
  }
})

