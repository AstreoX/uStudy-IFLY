<template>
	<view
		class="sse-renderjs-container"
		:trigger="trigger"
		:change:trigger="sseRender.onTriggerChange"
		:abort-trigger="abortTrigger"
		:change:abort-trigger="sseRender.onAbortTriggerChange"
	></view>
</template>

<script>
/**
 * SSE Renderjs 组件
 *
 * 利用 renderjs 在 Android WebView 渲染层直接使用浏览器原生 fetch + ReadableStream,
 * 绕过 uni-app 逻辑层的网络请求限制，实现真正的 SSE 流式响应。
 *
 * 通信方式:
 *   逻辑层 → renderjs: 通过 data 属性 + :change: 绑定触发
 *   renderjs → 逻辑层: 通过 $ownerInstance.callMethod() 回调
 *
 * 事件:
 *   @sse-events   ({ requestId, events: [{ eventType, data }] })
 *   @sse-complete ({ requestId, finalEvents: [{ eventType, data }], doneEventData })
 *   @sse-error    ({ requestId, error })
 */
export default {
	name: 'SseRenderjs',
	data() {
		return {
			requestId: 0,
			trigger: '',
			abortTrigger: ''
		}
	},
	methods: {
		// renderjs → 逻辑层 回调方法
		onSseEvents(data) {
			this.$emit('sse-events', data)
		},
		onSseComplete(data) {
			this.$emit('sse-complete', data)
		},
		onSseError(data) {
			this.$emit('sse-error', data)
		},

		// 外部调用：启动 SSE 连接
		startSSE(options) {
			this.requestId++
			const payload = {
				...options,
				requestId: this.requestId
			}
			// 修改 trigger 触发 renderjs 层的 onTriggerChange
			this.trigger = JSON.stringify(payload)
			return this.requestId
		},

		// 外部调用：取消 SSE 连接
		abortSSE(requestId) {
			this.abortTrigger = String(requestId) + '_' + Date.now()
		}
	}
}
</script>

<script module="sseRender" lang="renderjs">
export default {
	data() {
		return {
			abortControllers: {},
			retryTimers: {}
		}
	},
	beforeDestroy() {
		Object.keys(this.retryTimers).forEach(id => {
			clearTimeout(this.retryTimers[id])
		})
		this.retryTimers = {}
		Object.keys(this.abortControllers).forEach(id => {
			try { this.abortControllers[id].abort() } catch(e) {}
		})
		this.abortControllers = {}
	},
	methods: {
		// 解析 SSE 数据缓冲区
		parseSSEBuffer(buffer, onEvent) {
			const lines = buffer.split('\n')
			const remaining = lines.pop()
			let currentEvent = 'message'

			for (const line of lines) {
				if (line.startsWith('event: ')) {
					currentEvent = line.slice(7).trim()
				} else if (line.startsWith('data: ')) {
					try {
						const parsed = JSON.parse(line.slice(6))
						onEvent(currentEvent, parsed)
					} catch (e) {
						console.warn('[SSE-Renderjs] Parse error:', e)
					}
					currentEvent = 'message'
				}
			}
			return remaining
		},

		// 监听 trigger 变化，启动 fetch
		onTriggerChange(newVal) {
			if (!newVal) return
			try {
				const options = JSON.parse(newVal)
				this.startFetch(options)
			} catch (e) {
				console.error('[SSE-Renderjs] Failed to parse trigger:', e)
			}
		},

		// 监听 abortTrigger 变化，取消请求
		onAbortTriggerChange(newVal) {
			if (!newVal) return
			// 格式: "requestId_timestamp"
			const requestId = parseInt(newVal.split('_')[0], 10)
			if (requestId) {
				this.abortFetch(requestId)
			}
		},

		// 使用浏览器原生 fetch 发起流式请求
		async startFetch(options) {
			const { url, method, headers, data, requestId } = options
			const abortController = new AbortController()
			this.abortControllers[requestId] = abortController

			console.log('[SSE-Renderjs] Starting fetch, requestId:', requestId)

			try {
				const response = await fetch(url, {
					method: method || 'POST',
					headers: headers,
					body: JSON.stringify(data),
					signal: abortController.signal
				})

				if (!response.ok) {
					const text = await response.text()
					throw new Error('HTTP ' + response.status + ': ' + text)
				}

				const reader = response.body.getReader()
				const decoder = new TextDecoder()
				let buffer = ''
				let doneEventData = null

				while (true) {
					const { done, value } = await reader.read()

					if (done) {
						const finalEvents = []
						if (buffer) {
							this.parseSSEBuffer(buffer + '\n', (eventType, eventData) => {
								finalEvents.push({ eventType, data: eventData })
								if (eventType === 'done') {
									doneEventData = eventData
								}
							})
						}
						console.log('[SSE-Renderjs] Stream ended, requestId:', requestId,
							'finalEvents:', finalEvents.length, 'hasDone:', !!doneEventData)
						const payload = { requestId, finalEvents, doneEventData }
						this.$ownerInstance.callMethod('onSseComplete', payload)
						// 200ms 后重试（handler 幂等，重复调用安全）
						this.retryTimers[requestId] = setTimeout(() => {
							delete this.retryTimers[requestId]
							try {
								this.$ownerInstance.callMethod('onSseComplete', payload)
							} catch (e) {
								console.warn('[SSE-Renderjs] Retry callMethod failed (component likely destroyed):', e)
							}
						}, 200)
						break
					}

					const chunk = decoder.decode(value, { stream: true })
					console.log('[SSE-Renderjs] Chunk:', chunk.length, 'bytes')
					buffer += chunk

					const events = []
					buffer = this.parseSSEBuffer(buffer, (eventType, eventData) => {
						events.push({ eventType, data: eventData })
						if (eventType === 'done') {
							doneEventData = eventData
						}
					})
					if (events.length > 0) {
						this.$ownerInstance.callMethod('onSseEvents', { requestId, events })
					}
				}
			} catch (err) {
				if (err.name !== 'AbortError') {
					console.error('[SSE-Renderjs] Error:', err)
					this.$ownerInstance.callMethod('onSseError', {
						requestId,
						error: err.message
					})
				}
			} finally {
				delete this.abortControllers[requestId]
			}
		},

		// 取消请求
		abortFetch(requestId) {
			if (this.retryTimers[requestId]) {
				clearTimeout(this.retryTimers[requestId])
				delete this.retryTimers[requestId]
			}
			const controller = this.abortControllers[requestId]
			if (controller) {
				console.log('[SSE-Renderjs] Aborting requestId:', requestId)
				controller.abort()
				delete this.abortControllers[requestId]
			}
		}
	}
}
</script>

<style scoped>
.sse-renderjs-container {
	width: 0;
	height: 0;
	overflow: hidden;
	position: fixed;
	left: -9999px;
}
</style>
