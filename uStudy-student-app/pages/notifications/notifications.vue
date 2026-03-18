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
		min-height: 100vh;
		background: #0A0A12;
		position: relative;
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
			radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.06) 0%, transparent 50%),
			radial-gradient(circle at 80% 70%, rgba(168, 85, 247, 0.05) 0%, transparent 50%);
	}

	.bg-glow {
		position: absolute;
		width: 300rpx;
		height: 300rpx;
		border-radius: 50%;
		filter: blur(100px);
		opacity: 0.15;
	}

	.bg-glow-blue {
		background: #6366f1;
		top: -100rpx;
		right: -50rpx;
	}

	.bg-glow-violet {
		background: #a855f7;
		bottom: 200rpx;
		left: -80rpx;
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
		background: rgba(10, 10, 18, 0.85);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
	}

	.nav-back {
		width: 64rpx;
		height: 64rpx;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.nav-icon {
		width: 40rpx;
		height: 40rpx;
		opacity: 0.7;
		filter: brightness(0) invert(1);
	}

	.nav-copy {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.nav-title {
		font-size: 32rpx;
		font-weight: 600;
		color: #ffffff;
	}

	.nav-spacer {
		width: 64rpx;
	}

	.nav-action {
		padding: 8rpx 20rpx;
		border-radius: 20rpx;
		background: rgba(99, 102, 241, 0.15);
	}

	.nav-action-text {
		font-size: 24rpx;
		color: #818cf8;
		font-weight: 500;
	}

	/* ── States ── */
	.state-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding-top: 400rpx;
	}

	.state-icon {
		width: 96rpx;
		height: 96rpx;
		opacity: 0.3;
		filter: brightness(0) invert(1);
		margin-bottom: 24rpx;
	}

	.state-text {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.state-text-error {
		color: rgba(255, 100, 100, 0.6);
	}

	.retry-btn {
		margin-top: 24rpx;
		padding: 12rpx 40rpx;
		border-radius: 20rpx;
		background: rgba(99, 102, 241, 0.15);
	}

	.retry-btn-text {
		font-size: 26rpx;
		color: #818cf8;
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
		padding: 16rpx 24rpx 60rpx;
	}

	/* ── Notification Item ── */
	.notif-item {
		display: flex;
		align-items: flex-start;
		padding: 24rpx;
		margin-bottom: 16rpx;
		border-radius: 20rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.06);
		position: relative;
		transition: background 0.2s;
	}

	.notif-unread {
		background: rgba(99, 102, 241, 0.06);
		border-color: rgba(99, 102, 241, 0.12);
	}

	.unread-dot {
		position: absolute;
		top: 28rpx;
		left: 12rpx;
		width: 12rpx;
		height: 12rpx;
		border-radius: 50%;
		background: #6366f1;
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
	}

	.icon-quiz {
		background: rgba(99, 102, 241, 0.12);
	}

	.icon-reminder {
		background: rgba(234, 179, 8, 0.12);
	}

	.icon-care {
		background: rgba(236, 72, 153, 0.12);
	}

	.icon-system {
		background: rgba(148, 163, 184, 0.12);
	}

	.notif-icon {
		width: 36rpx;
		height: 36rpx;
		opacity: 0.7;
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
		color: #ffffff;
		line-height: 1.4;
	}

	.notif-body {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.5);
		line-height: 1.5;
		margin-top: 6rpx;
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.notif-time {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.25);
		margin-top: 8rpx;
	}

	/* ── Action Button ── */
	.notif-action {
		flex-shrink: 0;
		margin-left: 16rpx;
		padding: 10rpx 20rpx;
		border-radius: 16rpx;
		background: rgba(99, 102, 241, 0.15);
		align-self: center;
	}

	.notif-action-text {
		font-size: 24rpx;
		color: #818cf8;
		font-weight: 500;
		white-space: nowrap;
	}

	/* ── Loading More ── */
	.loading-more {
		padding: 24rpx 0;
		display: flex;
		justify-content: center;
	}

	.loading-more-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.25);
	}
</style>
