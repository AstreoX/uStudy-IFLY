<template>
  <view class="sidebar" :class="{ collapsed }">
    <!-- Logo -->
    <view class="sidebar-logo">
      <text class="logo-u" :class="{ 'logo-u-clickable': collapsed }" @tap="collapsed && $emit('toggle')">u</text>
      <text class="logo-study">Study</text>
      <view class="collapse-btn" @tap="$emit('toggle')">
        <svg viewBox="0 0 256 256" class="collapse-svg"><polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
      </view>
    </view>

    <!-- Navigation -->
    <view class="sidebar-nav">
      <template v-for="item in menuItems" :key="item.id">
        <view
          class="nav-item"
          :class="{ active: item.id === activeId }"
          @tap="handleNavTap(item)"
        >
          <view class="nav-icon">
            <!-- house -->
            <svg v-if="item.id === 'home'" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M104,216V152h48v64h64V120a8,8,0,0,0-2.34-5.66l-80-80a8,8,0,0,0-11.32,0l-80,80A8,8,0,0,0,40,120v96Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            <!-- graduation-cap -->
            <svg v-else-if="item.id === 'study'" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><polygon points="8 96 128 32 248 96 128 160 8 96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="128 96 184 125.87 184 240" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M216,113.07v53.22a8,8,0,0,1-2,5.31c-11.3,12.59-38.9,36.4-86,36.4s-74.68-23.81-86-36.4a8,8,0,0,1-2-5.31V113.07" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            <!-- chat -->
            <svg v-else-if="item.id === 'direct'" viewBox="0 0 256 256"><path d="M216,48H40A16,16,0,0,0,24,64V224a15.84,15.84,0,0,0,9.25,14.5A16.05,16.05,0,0,0,40,240a15.89,15.89,0,0,0,10.25-3.78l.09-.07L83,208H216a16,16,0,0,0,16-16V64A16,16,0,0,0,216,48ZM216,192H80a8,8,0,0,0-5.23,1.95L40,224V64H216Z" fill="currentColor"/></svg>
          </view>
          <text v-if="!collapsed" class="nav-label">{{ item.label }}</text>
          <!-- caret-right for expandable -->
          <svg
            v-if="!collapsed && item.expandable"
            viewBox="0 0 256 256"
            class="nav-arrow"
            :class="{ 'nav-arrow-expanded': item.id === 'study' && studyExpanded }"
          >
            <rect width="256" height="256" fill="none"/>
            <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          </svg>
        </view>

        <!-- Study Submenu -->
        <view
          v-if="item.id === 'study' && !collapsed"
          class="submenu-container"
          :style="{ maxHeight: studyExpanded ? '400px' : '0px', opacity: studyExpanded ? 1 : 0 }"
        >
          <view class="submenu-list">
            <!-- Loading -->
            <view v-if="spacesLoading" class="submenu-empty">
              <text class="submenu-empty-text">Loading...</text>
            </view>
            <!-- Empty state -->
            <view v-else-if="spaces.length === 0" class="submenu-empty">
              <text class="submenu-empty-text">No spaces yet</text>
            </view>
            <!-- Space entries -->
            <view
              v-else
              v-for="space in spaces"
              :key="space.id"
              class="submenu-item"
              :class="{ 'submenu-item-selected': space.id === selectedSpaceId }"
              @tap="handleSpaceTap(space)"
            >
              <view class="space-dot" :style="{ background: space.color || '#3B82F6' }"></view>
              <text class="space-name">{{ space.name }}</text>
              <text class="space-progress">{{ spaceProgress[space.id] || 0 }}%</text>
            </view>
            <!-- Create space button -->
            <view class="submenu-divider"></view>
            <view class="submenu-create" @tap="handleCreateSpace">
              <text class="submenu-create-plus">+</text>
              <text class="submenu-create-text">New Space</text>
            </view>
          </view>
        </view>
      </template>
    </view>

    <!-- Bottom Account Section -->
    <view class="sidebar-bottom">
      <view class="sidebar-bottom-divider"></view>

      <!-- Account row (clickable) -->
      <view v-if="user" class="account-section" ref="accountSection">
        <view class="account-row" @tap="toggleAccountMenu">
          <view class="account-avatar" :style="avatarStyle">
            <image
              v-if="user.avatar_url"
              class="account-avatar-image"
              :src="fullAvatarUrl"
              mode="aspectFill"
            />
            <text v-else class="account-avatar-text">{{ userInitial }}</text>
          </view>
          <view class="account-info">
            <text class="account-name">{{ userDisplayName }}</text>
            <view class="account-badge" :class="subscriptionClass">
              <text class="account-badge-text">{{ subscriptionLabel }}</text>
            </view>
          </view>
        </view>

        <!-- Account menu (teleported to body to escape sidebar overflow:hidden + backdrop-filter clipping) -->
        <Teleport to="body">
          <view v-if="accountMenuOpen" class="account-menu-backdrop" @tap="closeAccountMenu"></view>
          <transition name="menu-fade">
            <view v-if="accountMenuOpen" class="account-menu" :style="menuStyle">
              <!-- User info header -->
              <view class="account-menu-header">
                <view class="account-menu-avatar" :style="avatarStyle">
                  <image
                    v-if="user.avatar_url"
                    class="account-avatar-image"
                    :src="fullAvatarUrl"
                    mode="aspectFill"
                  />
                  <text v-else class="account-avatar-text">{{ userInitial }}</text>
                </view>
                <view class="account-menu-user">
                  <text class="account-menu-name">{{ userDisplayName }}</text>
                  <text class="account-menu-email">{{ maskedEmail }}</text>
                </view>
              </view>
              <view class="account-menu-divider"></view>
              <!-- Menu items -->
              <view class="account-menu-item" @tap="handleSubscription">
                <svg viewBox="0 0 256 256" class="account-menu-icon" fill="currentColor"><path d="M216,72H180.92c.39-.33.79-.65,1.17-1A29.53,29.53,0,0,0,192,49.57,32.62,32.62,0,0,0,158.44,16,29.53,29.53,0,0,0,137,25.91a54.94,54.94,0,0,0-9,14.48,54.94,54.94,0,0,0-9-14.48A29.53,29.53,0,0,0,97.56,16,32.62,32.62,0,0,0,64,49.57,29.53,29.53,0,0,0,73.91,71c.38.33.78.65,1.17,1H40A16,16,0,0,0,24,88v32a16,16,0,0,0,16,16v64a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V136a16,16,0,0,0,16-16V88A16,16,0,0,0,216,72ZM149,36.51a13.69,13.69,0,0,1,10-4.5h.49A16.62,16.62,0,0,1,176,49.08a13.69,13.69,0,0,1-4.5,10c-9.49,8.4-25.24,11.36-35,12.4C137.7,60.89,141,45.5,149,36.51Zm-64.09.36A16.63,16.63,0,0,1,96.59,32h.49a13.69,13.69,0,0,1,10,4.5c8.39,9.48,11.35,25.2,12.39,34.92-9.72-1-25.44-4-34.92-12.39a13.69,13.69,0,0,1-4.5-10A16.6,16.6,0,0,1,84.87,36.87ZM40,88h80v32H40Zm16,48h64v64H56Zm144,64H136V136h64Zm16-80H136V88h80v32Z"/></svg>
                <text class="account-menu-item-text">升级订阅</text>
              </view>
              <view class="account-menu-item" @tap="handleSettings">
                <svg viewBox="0 0 256 256" class="account-menu-icon"><rect width="256" height="256" fill="none"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M41.43,178.09A99.14,99.14,0,0,1,31.36,153.8l16.78-21a81.59,81.59,0,0,1,0-9.64l-16.77-21a99.43,99.43,0,0,1,10.05-24.3l26.71-3a81,81,0,0,1,6.81-6.81l3-26.7A99.14,99.14,0,0,1,102.2,31.36l21,16.78a81.59,81.59,0,0,1,9.64,0l21-16.77a99.43,99.43,0,0,1,24.3,10.05l3,26.71a81,81,0,0,1,6.81,6.81l26.7,3a99.14,99.14,0,0,1,10.07,24.29l-16.78,21a81.59,81.59,0,0,1,0,9.64l16.77,21a99.43,99.43,0,0,1-10,24.3l-26.71,3a81,81,0,0,1-6.81,6.81l-3,26.7a99.14,99.14,0,0,1-24.29,10.07l-21-16.78a81.59,81.59,0,0,1-9.64,0l-21,16.77a99.43,99.43,0,0,1-24.3-10l-3-26.71a81,81,0,0,1-6.81-6.81Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                <text class="account-menu-item-text">偏好设置</text>
              </view>
              <view class="account-menu-divider"></view>
              <view class="account-menu-item account-menu-item-danger" @tap="handleLogout">
                <svg viewBox="0 0 256 256" class="account-menu-icon"><rect width="256" height="256" fill="none"/><polyline points="174 86 216 128 174 170" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="104" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M104,216H48a8,8,0,0,1-8-8V48a8,8,0,0,1,8-8h56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                <text class="account-menu-item-text">退出登录</text>
              </view>
            </view>
          </transition>
        </Teleport>
      </view>
      <!-- Not logged in fallback -->
      <view v-else class="account-login-row" @tap="navigateToLogin">
        <svg viewBox="0 0 256 256" class="account-login-icon"><rect width="256" height="256" fill="none"/><circle cx="128" cy="96" r="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M32,216c19.37-33.47,54.55-56,96-56s76.63,22.53,96,56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
        <text v-if="!collapsed" class="account-login-text">Sign in</text>
      </view>

    </view>

    <Teleport to="body">
      <u-modal
        :visible="showLogoutModal"
        title="退出登录"
        content="确定要退出当前账号吗？"
        confirm-text="退出"
        confirm-type="danger"
        @confirm="confirmLogout"
        @close="showLogoutModal = false"
      />
    </Teleport>
  </view>
</template>

<script>
import { useUserStore } from '@/store/user'
import { useSpacesStore } from '@/store/spaces'
import config from '@/config'
import UModal from '@/components/u-modal/u-modal.vue'

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #0F6FFF 0%, #B1DD8B 100%)',
  'linear-gradient(135deg, #A18CD1 0%, #FBC2EB 100%)',
  'linear-gradient(135deg, #FA709A 0%, #FEE140 100%)',
  'linear-gradient(135deg, #84FAB0 0%, #38F9D7 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
]

export default {
  components: {
    UModal
  },
  props: {
    collapsed: {
      type: Boolean,
      default: false
    }
  },
  emits: ['toggle', 'navigate', 'select-space', 'create-space'],
  created() {
    this.userStore = useUserStore()
    this.spacesStore = useSpacesStore()
  },
  data() {
    return {
      activeId: 'home',
      studyExpanded: false,
      pendingStudyExpand: false,
      selectedSpaceId: null,
      accountMenuOpen: false,
      menuStyle: {},
      showLogoutModal: false,
      menuItems: [
        { id: 'home',    label: '首页',      expandable: false, route: '/pages/index/index' },
        { id: 'study',   label: '学习空间',  expandable: true },
        { id: 'direct',  label: '快速对话',  expandable: false, route: '/pages/quickChat/quickChat' }
      ]
    }
  },
  computed: {
    user() {
      return this.userStore.user
    },
    spaces() {
      return this.spacesStore.spaces
    },
    spaceProgress() {
      return this.spacesStore.spaceProgress
    },
    spacesLoading() {
      return this.spacesStore.loading
    },
    userInitial() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      return nickname.charAt(0).toUpperCase()
    },
    avatarGradient() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      const index = nickname.charCodeAt(0) % AVATAR_GRADIENTS.length
      return AVATAR_GRADIENTS[index]
    },
    fullAvatarUrl() {
      if (!this.user?.avatar_url) return ''
      if (this.user.avatar_url.startsWith('http')) {
        return this.user.avatar_url
      }
      return `${config.API_BASE_URL}${this.user.avatar_url}`
    },
    avatarStyle() {
      if (this.user?.avatar_url) {
        return {}
      }
      return { background: this.avatarGradient }
    },
    subscriptionClass() {
      const tier = (this.user?.subscription_tier || 'FREE').toUpperCase()
      const alias = {
        BASIC: 'PLUS',
        PREMIUM: 'ULTRA'
      }
      const normalized = alias[tier] || tier
      return `badge-${normalized.toLowerCase()}`
    },
    subscriptionLabel() {
      const tier = (this.user?.subscription_tier || 'FREE').toUpperCase()
      const labels = {
        FREE: 'Free',
        PLUS: 'Plus',
        ULTRA: 'Ultra',
        ALPHA: 'Alpha'
      }
      const alias = {
        BASIC: 'PLUS',
        PREMIUM: 'ULTRA'
      }
      const normalized = alias[tier] || tier
      return labels[normalized] || normalized
    },
    userDisplayName() {
      return this.user?.nickname || 'User'
    },
    maskedEmail() {
      const email = this.user?.email || ''
      if (!email) return ''
      const atIndex = email.indexOf('@')
      if (atIndex <= 0) return email
      const local = email.substring(0, atIndex)
      const domain = email.substring(atIndex)
      return `${local.charAt(0)}***${domain}`
    }
  },
  watch: {
    collapsed(newVal) {
      if (newVal) {
        this.studyExpanded = false
        this.accountMenuOpen = false
      } else if (this.pendingStudyExpand) {
        this.pendingStudyExpand = false
        this.$nextTick(() => {
          this.studyExpanded = true
        })
      }
    }
  },
  mounted() {
    this.spacesStore.loadSpaces()
    this.syncActiveFromRoute()
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.handleEscKey)
  },
  methods: {
    normalizeRoutePath(rawPath) {
      let path = String(rawPath || '').trim()
      if (!path) return ''

      const hashIndex = path.indexOf('#')
      if (hashIndex >= 0) {
        path = path.slice(hashIndex + 1)
      }

      const queryIndex = path.indexOf('?')
      if (queryIndex >= 0) {
        path = path.slice(0, queryIndex)
      }

      if (!path.startsWith('/')) {
        path = `/${path}`
      }

      return path
    },
    syncActiveFromRoute() {
      if (typeof getCurrentPages !== 'function') return
      const pages = getCurrentPages() || []
      const currentPage = pages[pages.length - 1]
      const rawRoute = currentPage?.route || currentPage?.$page?.fullPath || currentPage?.$page?.path || ''
      const currentRoute = this.normalizeRoutePath(rawRoute)
      if (!currentRoute) return

      const matchedItem = this.menuItems.find(item => item.route && this.normalizeRoutePath(item.route) === currentRoute)
      if (matchedItem) {
        this.activeId = matchedItem.id
        if (matchedItem.id !== 'study') {
          this.studyExpanded = false
        }
        return
      }

      // Treat all learning-space related pages as "study".
      if (currentRoute.startsWith('/pages/study/') || currentRoute.startsWith('/pages/createSpace/')) {
        this.activeId = 'study'
      }
    },
    handleNavTap(item) {
      this.accountMenuOpen = false
      if (item.id === 'study') {
        if (this.collapsed) {
          this.pendingStudyExpand = true
          this.$emit('toggle')
        } else {
          this.studyExpanded = !this.studyExpanded
        }
        this.activeId = item.id
        return
      }
      this.studyExpanded = false
      this.activeId = item.id
      this.$emit('navigate', item.id)
      if (item.route) {
        uni.reLaunch({ url: item.route })
      }
    },
    handleSpaceTap(space) {
      this.selectedSpaceId = space.id
      this.$emit('select-space', space.id)
    },
    handleCreateSpace() {
      this.$emit('create-space')
    },
    toggleAccountMenu() {
      if (this.collapsed) return
      this.accountMenuOpen = !this.accountMenuOpen
      if (this.accountMenuOpen) {
        this.updateMenuPosition()
        document.addEventListener('keydown', this.handleEscKey)
      } else {
        document.removeEventListener('keydown', this.handleEscKey)
      }
    },
    updateMenuPosition() {
      const el = this.$refs.accountSection?.$el || this.$refs.accountSection
      if (!el) return
      const rect = el.getBoundingClientRect()
      this.menuStyle = {
        left: rect.left + 'px',
        bottom: (window.innerHeight - rect.top + 6) + 'px',
        width: Math.max(rect.width, 220) + 'px'
      }
    },
    closeAccountMenu() {
      this.accountMenuOpen = false
      document.removeEventListener('keydown', this.handleEscKey)
    },
    handleEscKey(e) {
      if (e.key === 'Escape') {
        this.closeAccountMenu()
      }
    },
    handleSubscription() {
      this.accountMenuOpen = false
      uni.navigateTo({
        url: '/pages/activation/activation'
      })
    },
    handleSettings() {
      this.accountMenuOpen = false
      uni.navigateTo({
        url: '/pages/searchSettings/searchSettings'
      })
    },
    handleLogout() {
      this.accountMenuOpen = false
      this.showLogoutModal = true
    },
    confirmLogout() {
      this.showLogoutModal = false
      this.userStore.clear()
      uni.reLaunch({ url: '/pages/login/login' })
    },
    navigateToLogin() {
      uni.reLaunch({ url: '/pages/login/login' })
    },
    refreshSpaces() {
      this.spacesStore.loadSpaces(true)
    }
  }
}
</script>

<style scoped>
.sidebar {
  width: 200px;
  min-width: 200px;
  height: 100vh;
  background: rgba(255, 255, 255, 0.03);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease, min-width 0.25s ease;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 64px;
  min-width: 64px;
}

.sidebar-logo {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 24px 12px 32px 20px;
  white-space: nowrap;
  transition: padding 0.25s ease;
}

.sidebar.collapsed .sidebar-logo {
  padding: 24px 12px 32px 12px;
  justify-content: center;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
}

.sidebar.collapsed .account-row {
  justify-content: center;
}

.sidebar.collapsed .account-login-row {
  justify-content: center;
}

.logo-u {
  font-size: 28px;
  font-weight: 600;
  color: var(--color-accent-blue);
  border-radius: 8px;
  transition: background 0.15s ease;
}

.logo-u-clickable {
  cursor: pointer;
  padding: 2px 6px;
  margin: -2px -6px;
}

.logo-u-clickable:hover {
  background: rgba(255, 255, 255, 0.06);
}

.logo-study {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  max-width: 120px;
  overflow: hidden;
  transition: max-width 0.25s ease, opacity 0.25s ease;
}

.sidebar.collapsed .logo-study {
  max-width: 0;
  opacity: 0;
}

.sidebar-logo .collapse-btn {
  max-width: 28px;
  overflow: hidden;
  transition: max-width 0.25s ease, opacity 0.25s ease;
}

.sidebar.collapsed .sidebar-logo .collapse-btn {
  max-width: 0;
  opacity: 0;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 12px;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.sidebar-nav::-webkit-scrollbar {
  display: none;
}

.nav-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
  white-space: nowrap;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.15);
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.7);
}

.nav-icon svg {
  width: 20px;
  height: 20px;
}

.nav-item.active .nav-icon {
  color: var(--color-accent-blue);
}

.nav-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-left: 12px;
}

.nav-item.active .nav-label {
  color: #FFFFFF;
  font-weight: 500;
}

.nav-arrow {
  width: 14px;
  height: 14px;
  margin-left: auto;
  color: rgba(255, 255, 255, 0.3);
  transition: transform 0.25s ease;
}

.nav-arrow-expanded {
  transform: rotate(90deg);
}

/* Submenu */
.submenu-container {
  overflow: hidden;
  transition: max-height 0.25s ease, opacity 0.2s ease;
}

.submenu-list {
  padding: 4px 0 4px 0;
}

.submenu-empty {
  padding: 8px 12px 8px 44px;
}

.submenu-empty-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.35);
}

.submenu-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 8px 12px 8px 44px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
  gap: 8px;
}

.submenu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.submenu-item-selected {
  background: rgba(59, 130, 246, 0.12);
}

.submenu-item-selected:hover {
  background: rgba(59, 130, 246, 0.18);
}

.space-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.space-name {
  flex: 1;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.submenu-item-selected .space-name {
  color: rgba(255, 255, 255, 0.9);
}

.space-progress {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.submenu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 4px 12px 4px 44px;
}

.submenu-create {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 8px 12px 8px 44px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
  gap: 6px;
}

.submenu-create:hover {
  background: rgba(255, 255, 255, 0.06);
}

.submenu-create-plus {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-accent-blue);
  line-height: 1;
}

.submenu-create-text {
  font-size: 13px;
  color: var(--color-accent-blue);
}

.submenu-create:hover .submenu-create-plus,
.submenu-create:hover .submenu-create-text {
  color: #60A5FA;
}

/* Bottom section */
.sidebar-bottom {
  flex-shrink: 0;
  position: relative;
  padding: 0 12px 12px;
}

.sidebar-bottom-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 0 0 8px;
}

/* Account section */
.account-section {
  position: relative;
}

.account-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
  gap: 10px;
  white-space: nowrap;
}

.account-row:hover {
  background: rgba(255, 255, 255, 0.06);
}

.account-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.account-avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.account-avatar-text {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
  max-width: 120px;
  opacity: 1;
  transition: max-width 0.25s ease, opacity 0.2s ease;
}

.sidebar.collapsed .account-info {
  max-width: 0;
  opacity: 0;
}

.account-name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.account-badge {
  display: inline-flex;
  align-self: flex-start;
  padding: 1px 8px;
  border-radius: 8px;
}

.account-badge-text {
  font-size: 10px;
  font-weight: 500;
}

/* Badge colors */
.badge-free {
  background: rgba(255, 255, 255, 0.1);
}
.badge-free .account-badge-text {
  color: rgba(255, 255, 255, 0.6);
}

.badge-basic {
  background: rgba(0, 122, 255, 0.2);
}
.badge-basic .account-badge-text {
  color: #007AFF;
}

.badge-plus {
  background: rgba(59, 130, 246, 0.2);
}
.badge-plus .account-badge-text {
  color: #60A5FA;
}

.badge-premium {
  background: rgba(255, 215, 0, 0.2);
}
.badge-premium .account-badge-text {
  color: #FFD700;
}

.badge-ultra {
  background: rgba(139, 92, 246, 0.22);
}
.badge-ultra .account-badge-text {
  color: #C4B5FD;
}

.badge-alpha {
  background: rgba(255, 255, 255, 0.1);
}
.badge-alpha .account-badge-text {
  color: rgba(255, 255, 255, 0.6);
}

/* Not logged in fallback */
.account-login-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
  gap: 10px;
}

.account-login-row:hover {
  background: rgba(255, 255, 255, 0.06);
}

.account-login-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.5);
}

.account-login-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
  margin-left: auto;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.collapse-svg {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.4);
}

</style>

<!-- Unscoped styles for Teleported account menu (escapes sidebar clipping context) -->
<style>
.account-menu-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99;
}

.account-menu {
  position: fixed;
  min-width: 220px;
  background: rgba(30, 30, 30, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  z-index: 100;
  padding: 6px;
}

.account-menu-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
}

.account-menu-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.account-menu-avatar .account-avatar-text {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
}

.account-menu-avatar .account-avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.account-menu-user {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.account-menu-name {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.account-menu-email {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.account-menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 4px;
}

.account-menu-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.account-menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.account-menu-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.6);
}

.account-menu-item-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
}

.account-menu-item-danger .account-menu-icon {
  color: #EF4444;
}

.account-menu-item-danger .account-menu-item-text {
  color: #EF4444;
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
