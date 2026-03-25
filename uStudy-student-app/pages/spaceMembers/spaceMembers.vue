<template>
  <view class="members-page" :class="pageThemeClass">
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">{{ pageTitle }}</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <view v-if="loading" class="state-container">
      <view class="loading-spinner"></view>
      <text class="state-title">正在加载成员...</text>
      <text class="state-sub">稍等一下，正在同步协作空间成员状态</text>
    </view>

    <view v-else-if="loadError" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="state-title">{{ loadError }}</text>
      <view class="state-btn" @click="loadMembers">
        <text class="state-btn-text">重试</text>
      </view>
    </view>

    <view v-else-if="members.length === 0" class="state-container">
      <image class="state-icon" src="/static/icons/user.svg" mode="aspectFit"></image>
      <text class="state-title">暂无协作成员</text>
      <text class="state-sub">当前空间还没有其他协作成员加入</text>
    </view>

    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="content-body">
        <view class="hero-card">
          <view class="hero-title-row">
            <view class="hero-icon-wrap">
              <image class="hero-icon" src="/static/icons/user.svg" mode="aspectFit"></image>
            </view>
            <view class="hero-copy">
              <text class="hero-title">{{ spaceName || '当前学习空间' }}</text>
              <text class="hero-sub">{{ heroSubtitle }}</text>
            </view>
          </view>
          <view class="hero-stats">
            <view class="hero-stat">
              <text class="hero-stat-value">{{ members.length }}</text>
              <text class="hero-stat-label">协作成员</text>
            </view>
            <view class="hero-stat">
              <text class="hero-stat-value">{{ ownerCount }}</text>
              <text class="hero-stat-label">管理员</text>
            </view>
            <view class="hero-stat">
              <text class="hero-stat-value">{{ editableCount }}</text>
              <text class="hero-stat-label">可编辑图谱</text>
            </view>
          </view>
        </view>

        <view class="members-card">
          <view class="section-header">
            <text class="section-title">成员列表</text>
            <text class="section-sub">{{ isOwner ? '你可以调整成员图谱权限并移除成员' : '你当前只能查看成员与权限状态' }}</text>
          </view>

          <view
            v-for="member in members"
            :key="member.user_id"
            class="member-row"
            :class="{ 'member-row-self': isSelf(member) }"
          >
            <view class="member-main">
              <view class="member-avatar" :style="{ borderColor: member.color || '#5B8CFF' }">
                <text class="member-avatar-text">{{ getInitial(member.nickname) }}</text>
              </view>
              <view class="member-info">
                <view class="member-name-row">
                  <text class="member-name">{{ member.nickname || '未命名成员' }}</text>
                  <text v-if="member.role === 'owner'" class="member-badge member-badge-owner">管理员</text>
                  <text v-else-if="isSelf(member)" class="member-badge member-badge-self">我</text>
                </view>
                <text class="member-meta">加入于 {{ formatDate(member.joined_at) }}</text>
                <view class="permission-chip" :class="{ 'permission-chip-active': member.role === 'owner' || member.can_edit_graph }">
                  <text class="permission-chip-text">
                    {{ member.role === 'owner' ? '管理员可编辑图谱' : (member.can_edit_graph ? '可编辑知识图谱' : '仅查看知识图谱') }}
                  </text>
                </view>
              </view>
            </view>

            <view
              v-if="isOwner && member.role !== 'owner'"
              class="member-actions"
            >
              <view class="member-switch-row">
                <text class="member-switch-label">图谱编辑</text>
                <switch
                  :checked="!!member.can_edit_graph"
                  color="#5B8CFF"
                  :disabled="updatingMemberId === member.user_id"
                  @change="handleToggleGraphEdit(member, $event)"
                />
              </view>
              <view
                class="member-remove-btn"
                :class="{ 'member-remove-btn-disabled': removingMemberId === member.user_id }"
                @click="confirmRemoveMember(member)"
              >
                <text class="member-remove-btn-text">{{ removingMemberId === member.user_id ? '处理中...' : '移除成员' }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <u-modal
      :visible="showRemoveModal"
      title="移除成员"
      :content="removeModalContent"
      confirm-text="移除"
      confirm-type="danger"
      @confirm="doRemoveMember"
      @close="showRemoveModal = false"
    />

    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import { getSpace, getSpaceMembers, removeSpaceMember, updateMemberPermission } from '@/api/space'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import { useUserStore } from '@/store/user'
import { goBack } from '@/utils/navigation'
import homeThemePageMixin from '@/mixins/homeThemePageMixin'

export default {
  mixins: [homeThemePageMixin],
  components: {
    UModal,
    UToast
  },

  data() {
    return {
      spaceId: '',
      spaceName: '',
      userRole: '',
      currentUserId: '',
      loading: true,
      loadError: '',
      members: [],
      updatingMemberId: '',
      removingMemberId: '',
      showRemoveModal: false,
      memberToRemove: null,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  computed: {
    isOwner() {
      return this.userRole === 'owner'
    },

    pageTitle() {
      return this.isOwner ? '成员管理' : '协作成员'
    },

    heroSubtitle() {
      return this.isOwner
        ? '你当前是管理员，可以控制成员的图谱编辑权限。'
        : '当前空间处于协作模式，你可以查看成员与各自权限。'
    },

    ownerCount() {
      return this.members.filter(member => member.role === 'owner').length
    },

    editableCount() {
      return this.members.filter(member => member.role === 'owner' || member.can_edit_graph).length
    },

    removeModalContent() {
      if (!this.memberToRemove) return ''
      return `确定要移除「${this.memberToRemove.nickname || '该成员'}」吗？移除后对方将退出这个协作学习空间。`
    }
  },

  onLoad(options) {
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    const userStore = useUserStore()
    this.currentUserId = userStore.user?.id || ''
    this.loadMembers()
  },

  onShow() {
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
    if (this.spaceId && !this.loading) {
      this.loadMembers()
    }
  },

  methods: {
    goBack() {
      goBack()
    },

    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    async loadMembers() {
      if (!this.spaceId) {
        this.members = []
        this.loading = false
        return
      }

      this.loading = true
      this.loadError = ''

      try {
        const [space, members] = await Promise.all([
          getSpace(this.spaceId),
          getSpaceMembers(this.spaceId)
        ])
        this.userRole = space?.user_role || ''
        this.members = members?.data || members || []
      } catch (error) {
        this.members = []
        this.loadError = error.message || '加载成员失败'
      } finally {
        this.loading = false
      }
    },

    isSelf(member) {
      return String(member?.user_id || '') === String(this.currentUserId || '')
    },

    getInitial(name) {
      return (name || '?').slice(0, 1).toUpperCase()
    },

    formatDate(dateString) {
      if (!dateString) return '未知时间'
      const date = new Date(dateString)
      if (Number.isNaN(date.getTime())) return '未知时间'
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    },

    async handleToggleGraphEdit(member, event) {
      const nextValue = !!event.detail.value
      const previousValue = !!member.can_edit_graph
      member.can_edit_graph = nextValue
      this.updatingMemberId = member.user_id

      try {
        await updateMemberPermission(this.spaceId, member.user_id, {
          can_edit_graph: nextValue
        })
        this.showCustomToast('成员权限已更新', 'success')
      } catch (error) {
        member.can_edit_graph = previousValue
        this.showCustomToast(error.message || '更新权限失败', 'error')
      } finally {
        this.updatingMemberId = ''
      }
    },

    confirmRemoveMember(member) {
      if (!this.isOwner || !member || member.role === 'owner') return
      this.memberToRemove = member
      this.showRemoveModal = true
    },

    async doRemoveMember() {
      if (!this.memberToRemove || this.removingMemberId) return
      this.removingMemberId = this.memberToRemove.user_id

      try {
        await removeSpaceMember(this.spaceId, this.memberToRemove.user_id)
        this.members = this.members.filter(member => member.user_id !== this.memberToRemove.user_id)
        this.showRemoveModal = false
        this.showCustomToast('成员已移除', 'success')
        this.memberToRemove = null
      } catch (error) {
        this.showCustomToast(error.message || '移除成员失败', 'error')
      } finally {
        this.removingMemberId = ''
      }
    }
  }
}
</script>

<style scoped>
.members-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(91, 140, 255, 0.2), transparent 40%),
    radial-gradient(circle at bottom right, rgba(132, 250, 176, 0.16), transparent 32%),
    linear-gradient(180deg, #0a0a12 0%, #11111b 48%, #0d0f17 100%);
  color: #ffffff;
}

.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.nav-left,
.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
}

.nav-left {
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

.state-container {
  min-height: 100vh;
  padding: calc(100vh * 5 / 26) calc(100vw / 12) calc(100vh * 2 / 26);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.loading-spinner {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(255, 255, 255, 0.15);
  border-top-color: #5b8cff;
  animation: spin 0.8s linear infinite;
}

.state-icon {
  width: 88rpx;
  height: 88rpx;
  margin-bottom: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.86;
}

.state-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

.state-sub {
  margin-top: 16rpx;
  font-size: 26rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.56);
}

.state-btn {
  margin-top: 32rpx;
  padding: 0 36rpx;
  height: 84rpx;
  border-radius: 42rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.8) 0%, rgba(132, 250, 176, 0.48) 100%);
  box-shadow: 0 10rpx 32rpx rgba(91, 140, 255, 0.22);
}

.state-btn-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.content-scroll {
  min-height: 100vh;
}

.content-body {
  padding:
    calc(100vh * 4.5 / 26)
    calc(100vw / 24)
    calc(env(safe-area-inset-bottom) + 40rpx);
}

.hero-card,
.members-card {
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.18);
}

.hero-card {
  padding: 32rpx;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 22rpx;
}

.hero-icon-wrap {
  width: 92rpx;
  height: 92rpx;
  border-radius: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(91, 140, 255, 0.14);
  border: 1rpx solid rgba(91, 140, 255, 0.18);
}

.hero-icon {
  width: 46rpx;
  height: 46rpx;
  filter: brightness(0) invert(1);
}

.hero-copy {
  flex: 1;
}

.hero-title {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  line-height: 1.3;
  color: #ffffff;
}

.hero-sub {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.56);
}

.hero-stats {
  margin-top: 28rpx;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14rpx;
}

.hero-stat {
  padding: 20rpx 18rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.05);
}

.hero-stat-value {
  display: block;
  font-size: 34rpx;
  font-weight: 700;
  color: #ffffff;
}

.hero-stat-label {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.46);
}

.members-card {
  margin-top: 24rpx;
  padding: 28rpx 24rpx 20rpx;
}

.section-header {
  margin-bottom: 18rpx;
}

.section-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.section-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.46);
}

.member-row {
  padding: 24rpx;
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.04);
}

.member-row + .member-row {
  margin-top: 16rpx;
}

.member-row-self {
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.16) 0%, rgba(132, 250, 176, 0.08) 100%);
  border: 1rpx solid rgba(91, 140, 255, 0.18);
}

.member-main {
  display: flex;
  gap: 18rpx;
}

.member-avatar {
  width: 84rpx;
  height: 84rpx;
  flex-shrink: 0;
  border-radius: 50%;
  border: 4rpx solid rgba(91, 140, 255, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
}

.member-avatar-text {
  font-size: 30rpx;
  font-weight: 700;
  color: #ffffff;
}

.member-info {
  flex: 1;
  min-width: 0;
}

.member-name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.member-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.member-badge {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
}

.member-badge-owner {
  color: #ffd56a;
  background: rgba(255, 213, 106, 0.12);
}

.member-badge-self {
  color: #9dd6ff;
  background: rgba(91, 140, 255, 0.14);
}

.member-meta {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.5);
}

.permission-chip {
  margin-top: 14rpx;
  padding: 12rpx 16rpx;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.permission-chip-active {
  background: rgba(91, 140, 255, 0.12);
  border-color: rgba(91, 140, 255, 0.18);
}

.permission-chip-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.72);
}

.member-actions {
  margin-top: 22rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.member-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-switch-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.82);
}

.member-remove-btn {
  margin-top: 16rpx;
  height: 78rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.14);
  border: 1rpx solid rgba(239, 68, 68, 0.24);
}

.member-remove-btn-disabled {
  opacity: 0.6;
}

.member-remove-btn-text {
  font-size: 26rpx;
  font-weight: 600;
  color: #ff8e8e;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.members-page.theme-light {
  background:
    radial-gradient(circle at top left, rgba(47, 110, 234, 0.14), transparent 40%),
    radial-gradient(circle at bottom right, rgba(199, 119, 22, 0.1), transparent 34%),
    linear-gradient(180deg, #F7F1E8 0%, #F3EDE3 50%, #EFE6DA 100%);
  color: #1F1A16;
}

.members-page.theme-light .nav-left {
  background-color: rgba(255, 255, 255, 0.82);
  border-color: rgba(63, 53, 42, 0.1);
  outline-color: rgba(255, 255, 255, 0.72);
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.68),
    0 10rpx 24rpx rgba(118, 101, 80, 0.12);
}

.members-page.theme-light .nav-icon,
.members-page.theme-light .state-icon,
.members-page.theme-light .hero-icon {
  filter: brightness(0) saturate(100%);
}

.members-page.theme-light .nav-title,
.members-page.theme-light .state-title,
.members-page.theme-light .hero-title,
.members-page.theme-light .hero-stat-value,
.members-page.theme-light .section-title,
.members-page.theme-light .member-name,
.members-page.theme-light .permission-chip-text {
  color: #1F1A16;
}

.members-page.theme-light .state-sub,
.members-page.theme-light .hero-sub,
.members-page.theme-light .hero-stat-label,
.members-page.theme-light .section-sub,
.members-page.theme-light .member-meta,
.members-page.theme-light .member-switch-label {
  color: rgba(31, 26, 22, 0.58);
}

.members-page.theme-light .loading-spinner {
  border-color: rgba(63, 53, 42, 0.12);
  border-top-color: #2F6EEA;
}

.members-page.theme-light .state-btn {
  background: linear-gradient(135deg, #2F6EEA 0%, #4C86F0 100%);
  box-shadow: 0 10rpx 32rpx rgba(47, 110, 234, 0.18);
}

.members-page.theme-light .hero-card,
.members-page.theme-light .members-card {
  background: rgba(255, 251, 245, 0.92);
  border-color: rgba(79, 66, 51, 0.12);
  box-shadow: 0 20rpx 56rpx rgba(118, 101, 80, 0.12);
}

.members-page.theme-light .hero-icon-wrap {
  background: rgba(47, 110, 234, 0.1);
  border-color: rgba(47, 110, 234, 0.16);
}

.members-page.theme-light .hero-stat,
.members-page.theme-light .permission-chip {
  background: rgba(255, 255, 255, 0.76);
  border-color: rgba(79, 66, 51, 0.08);
}

.members-page.theme-light .permission-chip-active {
  background: rgba(47, 110, 234, 0.12);
  border-color: rgba(47, 110, 234, 0.18);
}

.members-page.theme-light .member-row {
  background: rgba(255, 255, 255, 0.78);
}

.members-page.theme-light .member-row-self {
  background: linear-gradient(135deg, rgba(47, 110, 234, 0.12) 0%, rgba(47, 157, 112, 0.08) 100%);
  border: 1rpx solid rgba(47, 110, 234, 0.16);
}

.members-page.theme-light .member-avatar {
  background: rgba(255, 255, 255, 0.78);
}

.members-page.theme-light .member-avatar-text {
  color: #1F1A16;
}

.members-page.theme-light .member-badge-owner {
  color: #B78321;
  background: rgba(255, 213, 106, 0.16);
}

.members-page.theme-light .member-badge-self {
  color: #2F6EEA;
  background: rgba(47, 110, 234, 0.12);
}

.members-page.theme-light .member-actions {
  border-top-color: rgba(79, 66, 51, 0.08);
}

.members-page.theme-light .member-remove-btn {
  background: rgba(217, 72, 95, 0.1);
  border-color: rgba(217, 72, 95, 0.18);
}

.members-page.theme-light .member-remove-btn-text {
  color: #C2410C;
}
</style>
