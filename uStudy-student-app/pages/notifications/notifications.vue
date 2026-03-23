<template>
	<view class="notifications-page">
		<view class="page-bg">
			<view class="bg-mesh"></view>
			<view class="bg-glow bg-glow-blue"></view>
			<view class="bg-glow bg-glow-violet"></view>
		</view>

		<!-- Navigation Bar -->
		<view class="nav-bar">
			<view class="nav-back" @click="goBack">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
			</view>
			<view class="nav-copy">
				<text class="nav-title">通知</text>
			</view>
			<view class="nav-action" @click="handleMarkAllRead" v-if="notifications.length > 0 && unreadCount > 0">
				<text class="nav-action-text">全部已读</text>
			</view>
			<view class="nav-spacer" v-else></view>
		</view>

		<!-- Loading State -->
		<view v-if="loading && notifications.length === 0" class="state-container">
			<text class="state-text">正在加载通知...</text>
		</view>

		<!-- Error State -->
		<view v-else-if="loadError" class="state-container">
			<text class="state-text state-text-error">{{ loadError }}</text>
			<view class="retry-btn" @click="loadNotifications(true)">
				<text class="retry-btn-text">重试</text>
			</view>
		</view>

		<!-- Empty State -->
		<view v-else-if="notifications.length === 0 && !loading" class="state-container">
			<image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/bell.svg" mode="aspectFit"></image>
			<text class="state-text">暂无通知</text>
		</view>

		<!-- Notification List -->
		<scroll-view
			v-else
			class="content-scroll"
			scroll-y
			@scrolltolower="loadMore"
		>
			<view class="content-body">
				<view
					v-for="item in notifications"
					:key="item.id"
					class="notif-item"
					:class="{ 'notif-unread': !item.is_read }"
					@click="handleNotifClick(item)"
				>
					<!-- Unread dot -->
					<view v-if="!item.is_read" class="unread-dot"></view>

					<!-- Icon -->
					<view class="notif-icon-wrap" :class="iconClass(item)">
						<image class="notif-icon" :src="iconSrc(item)" mode="aspectFit"></image>
					</view>

					<!-- Content -->
					<view class="notif-content">
						<text class="notif-title">{{ item.title }}</text>
						<text class="notif-body">{{ item.body }}</text>
						<text class="notif-time">{{ formatTime(item.created_at) }}</text>
					</view>

					<!-- Action button -->
					<view
						v-if="getAction(item)"
						class="notif-action"
						:class="iconClass(item)"
						@click.stop="handleAction(item)"
					>
						<text class="notif-action-text">{{ getAction(item).label }}</text>
					</view>
				</view>

				<!-- Loading more indicator -->
				<view v-if="loadingMore" class="loading-more">
					<text class="loading-more-text">加载中...</text>
				</view>

				<!-- No more -->
				<view v-else-if="noMore && notifications.length > 0" class="loading-more">
					<text class="loading-more-text">没有更多了</text>
				</view>
			</view>
		</scroll-view>
	</view>
</template>

<script>
	import {
		getNotifications,
		markNotificationRead,
		markAllNotificationsRead,
	} from '@/api/notificationCenter'
	import { useNotificationStore } from '@/store/notification'

	const PAGE_SIZE = 20

	export default {
		data() {
			return {
				notifications: [],
				loading: false,
				loadingMore: false,
				loadError: '',
				total: 0,
				unreadCount: 0,
				noMore: false,
			}
		},

		onShow() {
			this.loadNotifications(true)
		},

		computed: {
			notificationStore() {
				return useNotificationStore()
			},
		},

		methods: {
			goBack() {
				uni.navigateBack()
			},

			async loadNotifications(reset = false) {
				if (reset) {
					this.notifications = []
					this.noMore = false
					this.loading = true
					this.loadError = ''
				}

				try {
					const res = await getNotifications({
						offset: reset ? 0 : this.notifications.length,
						limit: PAGE_SIZE,
					})
					const items = res.items || []
					if (reset) {
						this.notifications = items
					} else {
						this.notifications = [...this.notifications, ...items]
					}
					this.total = res.total || 0
					this.unreadCount = res.unread_count || 0
					this.notificationStore.setUnreadCount(this.unreadCount)
					if (items.length < PAGE_SIZE) {
						this.noMore = true
					}
				} catch (err) {
					this.loadError = '加载失败，请重试'
				} finally {
					this.loading = false
					this.loadingMore = false
				}
			},

			async loadMore() {
				if (this.loadingMore || this.noMore) return
				this.loadingMore = true
				await this.loadNotifications(false)
			},

			async handleNotifClick(item) {
				if (!item.is_read) {
					await this.markRead(item)
				}
				this.navigateByAction(item)
			},

			async markRead(item) {
				try {
					await markNotificationRead(item.id)
					item.is_read = true
					this.unreadCount = Math.max(0, this.unreadCount - 1)
					this.notificationStore.decrement()
				} catch (_) {}
			},

			handleAction(item) {
				if (!item.is_read) {
					this.markRead(item)
				}
				this.navigateByAction(item)
			},

			navigateByAction(item) {
				const data = item.data || {}
				const action = data.action

				if (action === 'start_quiz' && data.quiz_id) {
					uni.navigateTo({ url: `/pages/test/test?quizId=${data.quiz_id}` })
				} else if (action === 'open_space' && data.space_id) {
					uni.navigateTo({ url: `/pages/learningSpace/learningSpace?spaceId=${data.space_id}` })
				} else if (action === 'go_review') {
					uni.navigateBack()
				} else if (item.type === 'system_announcement') {
					uni.navigateTo({ url: '/pages/announcementHistory/announcementHistory' })
				}
			},

			async handleMarkAllRead() {
				try {
					await markAllNotificationsRead()
					this.notifications.forEach(n => { n.is_read = true })
					this.unreadCount = 0
					this.notificationStore.clearUnread()
				} catch (_) {}
			},

			getAction(item) {
				const data = item.data || {}
				const action = data.action

				if (action === 'start_quiz' && data.quiz_id) {
					return { label: '开始测试' }
				}
				if (action === 'open_space' && data.space_id) {
					return { label: '查看空间' }
				}
				if (action === 'go_review') {
					return { label: '去复习' }
				}
				if (item.type === 'system_announcement') {
					return { label: '查看详情' }
				}
				return null
			},

			iconSrc(item) {
				if (item.type === 'review_quiz_ready') {
					return '/static/icons/phosphor-icons/SVGs/regular/clipboard-text.svg'
				}
				if (item.type === 'review_reminder') {
					return '/static/icons/phosphor-icons/SVGs/regular/calendar-check.svg'
				}
				if (item.type === 'inactivity_care') {
					return '/static/icons/phosphor-icons/SVGs/regular/heart.svg'
				}
				return '/static/icons/phosphor-icons/SVGs/regular/bell.svg'
			},

			iconClass(item) {
				if (item.type === 'review_quiz_ready') return 'icon-quiz'
				if (item.type === 'review_reminder') return 'icon-reminder'
				if (item.type === 'inactivity_care') return 'icon-care'
				return 'icon-system'
			},

			formatTime(dateStr) {
				if (!dateStr) return ''
				const date = new Date(dateStr)
				const now = new Date()
				const diff = now - date
				const minutes = Math.floor(diff / 60000)
				const hours = Math.floor(diff / 3600000)
				const days = Math.floor(diff / 86400000)

				if (minutes < 1) return '刚刚'
				if (minutes < 60) return `${minutes}分钟前`
				if (hours < 24) return `${hours}小时前`
				if (days < 7) return `${days}天前`

				const m = date.getMonth() + 1
				const d = date.getDate()
				return `${m}月${d}日`
			},
		},
	}
</script>

<style scoped>
	.notifications-page {
		--notif-bg-base: rgb(29, 30, 32);
		--notif-surface: rgba(255, 255, 255, 0.055);
		--notif-surface-strong: rgba(255, 255, 255, 0.08);
		--notif-border: rgba(255, 255, 255, 0.1);
		--notif-border-strong: rgba(255, 255, 255, 0.16);
		--notif-text-primary: #f5f5f5;
		--notif-text-secondary: #dddddf;
		--notif-text-muted: #b0b2b8;
		--notif-text-faint: rgba(255, 255, 255, 0.42);
		--notif-text-error: #fca5a5;
		--notif-dot: #ff8a3d;
		--notif-accent-quiz: #9ab0ff;
		--notif-accent-quiz-bg: rgba(122, 147, 255, 0.15);
		--notif-accent-quiz-border: rgba(122, 147, 255, 0.24);
		--notif-accent-reminder: #ff9a4d;
		--notif-accent-reminder-bg: rgba(255, 138, 61, 0.16);
		--notif-accent-reminder-border: rgba(255, 138, 61, 0.28);
		--notif-accent-care: #ff6f61;
		--notif-accent-care-bg: rgba(255, 111, 97, 0.15);
		--notif-accent-care-border: rgba(255, 111, 97, 0.27);
		--notif-accent-system: #7dc2b1;
		--notif-accent-system-bg: rgba(125, 194, 177, 0.13);
		--notif-accent-system-border: rgba(125, 194, 177, 0.22);
		min-height: 100vh;
		background: var(--notif-bg-base);
		position: relative;
		overflow: hidden;
	}

	/* ── Background ── */
	.page-bg {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 0;
		overflow: hidden;
	}

	.bg-mesh {
		position: absolute;
		inset: 0;
		background:
			radial-gradient(circle at 18% 20%, rgba(255, 255, 255, 0.08) 0%, transparent 40%),
			radial-gradient(circle at 82% 72%, rgba(255, 255, 255, 0.045) 0%, transparent 36%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.024) 0%, rgba(255, 255, 255, 0) 34%);
	}

	.bg-glow {
		position: absolute;
		width: 360rpx;
		height: 360rpx;
		border-radius: 50%;
		filter: blur(120px);
		opacity: 0.16;
	}

	.bg-glow-blue {
		background: #455064;
		top: -120rpx;
		right: -90rpx;
	}

	.bg-glow-violet {
		background: #60392e;
		bottom: 160rpx;
		left: -100rpx;
	}

	/* ── Nav Bar ── */
	.nav-bar {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 100;
		display: flex;
		align-items: center;
		padding: calc(var(--status-bar-height, 44px) + 8rpx) 24rpx 16rpx;
		background: rgba(29, 30, 32, 0.84);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
		box-shadow: 0 14rpx 34rpx rgba(0, 0, 0, 0.24);
	}

	.nav-back {
		width: 72rpx;
		height: 72rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		outline: 1rpx solid rgba(255, 255, 255, 0.04);
		outline-offset: 1rpx;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
			0 2rpx 12rpx rgba(0, 0, 0, 0.25);
		backdrop-filter: blur(40px) saturate(180%);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
	}

	.nav-icon {
		width: 44rpx;
		height: 44rpx;
		opacity: 0.9;
		filter: brightness(0) invert(1);
	}

	.nav-copy {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.nav-title {
		font-size: 34rpx;
		font-weight: 600;
		color: var(--notif-text-primary);
	}

	.nav-spacer {
		width: 64rpx;
	}

	.nav-action {
		padding: 12rpx 22rpx;
		border-radius: 999rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.05),
			0 2rpx 8rpx rgba(0, 0, 0, 0.12);
		transition: background 0.15s ease, border-color 0.15s ease;
	}

	.nav-action:active {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.14);
	}

	.nav-action-text {
		font-size: 24rpx;
		color: var(--notif-text-secondary);
		font-weight: 500;
	}

	/* ── States ── */
	.state-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding-top: 400rpx;
		padding-left: 48rpx;
		padding-right: 48rpx;
	}

	.state-icon {
		width: 96rpx;
		height: 96rpx;
		opacity: 0.42;
		filter: brightness(0) invert(1);
		margin-bottom: 24rpx;
	}

	.state-text {
		font-size: 28rpx;
		color: var(--notif-text-muted);
		text-align: center;
		line-height: 1.6;
	}

	.state-text-error {
		color: var(--notif-text-error);
	}

	.retry-btn {
		margin-top: 24rpx;
		padding: 14rpx 40rpx;
		border-radius: 999rpx;
		background: rgba(255, 111, 97, 0.14);
		border: 1rpx solid rgba(255, 111, 97, 0.28);
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
			0 4rpx 14rpx rgba(0, 0, 0, 0.16);
	}

	.retry-btn-text {
		font-size: 26rpx;
		color: #ffb1a8;
	}

	/* ── Content ── */
	.content-scroll {
		position: fixed;
		top: calc(var(--status-bar-height, 44px) + 88rpx);
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1;
	}

	.content-body {
		padding: 20rpx 24rpx 72rpx;
	}

	/* ── Notification Item ── */
	.notif-item {
		display: flex;
		align-items: flex-start;
		padding: 26rpx 24rpx 26rpx 30rpx;
		margin-bottom: 18rpx;
		border-radius: 24rpx;
		background: var(--notif-surface);
		border: 1rpx solid var(--notif-border);
		position: relative;
		box-shadow: 0 12rpx 30rpx rgba(0, 0, 0, 0.16);
		backdrop-filter: blur(24px) saturate(120%);
		-webkit-backdrop-filter: blur(24px) saturate(120%);
		transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
	}

	.notif-item:active {
		background: var(--notif-surface-strong);
		transform: scale(0.995);
	}

	.notif-unread {
		background: var(--notif-surface-strong);
		border-color: var(--notif-border-strong);
	}

	.unread-dot {
		position: absolute;
		top: 34rpx;
		left: 12rpx;
		width: 10rpx;
		height: 10rpx;
		border-radius: 50%;
		background: var(--notif-dot);
		box-shadow: 0 0 12rpx rgba(255, 138, 61, 0.34);
	}

	/* ── Icon ── */
	.notif-icon-wrap {
		width: 72rpx;
		height: 72rpx;
		border-radius: 18rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		margin-right: 20rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.04);
	}

	.icon-quiz {
		background: var(--notif-accent-quiz-bg);
		border-color: var(--notif-accent-quiz-border);
	}

	.icon-reminder {
		background: var(--notif-accent-reminder-bg);
		border-color: var(--notif-accent-reminder-border);
	}

	.icon-care {
		background: var(--notif-accent-care-bg);
		border-color: var(--notif-accent-care-border);
	}

	.icon-system {
		background: var(--notif-accent-system-bg);
		border-color: var(--notif-accent-system-border);
	}

	.notif-icon {
		width: 36rpx;
		height: 36rpx;
		opacity: 0.88;
		filter: brightness(0) invert(1);
	}

	/* ── Content ── */
	.notif-content {
		flex: 1;
		min-width: 0;
	}

	.notif-title {
		font-size: 28rpx;
		font-weight: 600;
		color: var(--notif-text-primary);
		line-height: 1.4;
	}

	.notif-body {
		font-size: 24rpx;
		color: var(--notif-text-secondary);
		line-height: 1.5;
		margin-top: 8rpx;
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.notif-time {
		font-size: 22rpx;
		color: var(--notif-text-muted);
		margin-top: 10rpx;
	}

	/* ── Action Button ── */
	.notif-action {
		flex-shrink: 0;
		margin-left: 16rpx;
		padding: 12rpx 20rpx;
		border-radius: 16rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
			0 4rpx 12rpx rgba(0, 0, 0, 0.12);
		align-self: center;
		transition: background 0.15s ease, border-color 0.15s ease;
	}

	.notif-action:active {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.12);
	}

	.notif-action-text {
		font-size: 24rpx;
		color: var(--notif-text-primary);
		font-weight: 500;
		white-space: nowrap;
	}

	.notif-action.icon-quiz {
		background: var(--notif-accent-quiz-bg);
		border-color: var(--notif-accent-quiz-border);
	}

	.notif-action.icon-reminder {
		background: var(--notif-accent-reminder-bg);
		border-color: var(--notif-accent-reminder-border);
	}

	.notif-action.icon-care {
		background: var(--notif-accent-care-bg);
		border-color: var(--notif-accent-care-border);
	}

	.notif-action.icon-system {
		background: var(--notif-accent-system-bg);
		border-color: var(--notif-accent-system-border);
	}

	.notif-action.icon-quiz .notif-action-text {
		color: var(--notif-accent-quiz);
	}

	.notif-action.icon-reminder .notif-action-text {
		color: var(--notif-accent-reminder);
	}

	.notif-action.icon-care .notif-action-text {
		color: var(--notif-accent-care);
	}

	.notif-action.icon-system .notif-action-text {
		color: var(--notif-accent-system);
	}

	/* ── Loading More ── */
	.loading-more {
		padding: 24rpx 0;
		display: flex;
		justify-content: center;
	}

	.loading-more-text {
		font-size: 24rpx;
		color: var(--notif-text-faint);
	}
</style>
