<template>
	<view class="markdown-container">
		<rich-text
			:nodes="parsedHtml"
			class="markdown-content"
			selectable="true"
			@itemclick="onRichTextItemClick"
		></rich-text>
	</view>
</template>

<script>
import katex from 'katex'

function escapeHtml(text) {
	return String(text)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;')
}

function isSafeHttpUrl(url) {
	return /^https?:\/\//i.test(String(url || ''))
}

const LINK_INLINE_STYLE = 'color: rgb(92, 144, 247); text-decoration: underline;'

function countChar(str, target) {
	let count = 0
	for (let i = 0; i < str.length; i++) {
		if (str[i] === target) count++
	}
	return count
}

function splitTrailingUrlSuffix(url) {
	let trimmed = String(url || '')
	if (!trimmed) return { url: '', suffix: '' }

	while (/[.,!?;:]+$/.test(trimmed)) {
		trimmed = trimmed.slice(0, -1)
	}

	while (/[)\]}]$/.test(trimmed)) {
		const last = trimmed[trimmed.length - 1]
		const opening = last === ')' ? '(' : last === ']' ? '[' : '{'
		const openCount = countChar(trimmed, opening)
		const closeCount = countChar(trimmed, last)
		if (closeCount > openCount) {
			trimmed = trimmed.slice(0, -1)
			continue
		}
		break
	}

	return {
		url: trimmed,
		suffix: String(url || '').slice(trimmed.length)
	}
}

function linkifyRawUrls(text) {
	if (!text) return ''
	return text.replace(/(^|[\s(（\[【<>"'])((?:https?:\/\/)[^\s<>"']+)/gi, (match, prefix, candidate) => {
		const { url, suffix } = splitTrailingUrlSuffix(candidate)
		if (!url || !isSafeHttpUrl(url)) return match
		return `${prefix}<a href="${url}" style="${LINK_INLINE_STYLE}">${url}</a>${suffix}`
	})
}

// 代码块内联样式（rich-text 不支持外部 CSS）
const CODE_WRAPPER_STYLE = 'background:rgba(30,30,30,0.95); border-radius:12px; margin:16px 0; overflow:hidden;'
const CODE_HEADER_STYLE = 'display:flex; justify-content:space-between; align-items:center; padding:8px 16px; background:rgba(255,255,255,0.05); border-bottom:1px solid rgba(255,255,255,0.1);'
const CODE_LANG_STYLE = 'color:rgba(255,255,255,0.6); font-size:12px;'
const CODE_COPY_STYLE = 'color:#5c90f7; font-size:12px; text-decoration:none;'
const CODE_PRE_STYLE = 'overflow-x:auto; margin:0; padding:16px; white-space:pre; background:transparent;'
const CODE_STYLE = 'font-family:SF Mono,Monaco,Consolas,monospace; font-size:13px; color:#e0e0e0;'

function parseSimpleMarkdown(text) {
	if (!text) return { html: '', codeContents: [] }

	const codeBlocks = []
	const codeContents = []
	let content = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
		const idx = codeBlocks.length
		const safeLang = escapeHtml((lang || '').trim())
		const rawCode = (code || '').replace(/^\n+|\n+$/g, '') // 去掉首尾空行
		const safeCode = escapeHtml(rawCode)
		const displayLang = safeLang || 'code'

		// 保存原始代码供复制
		codeContents.push(rawCode)

		codeBlocks.push(
			`<div style="${CODE_WRAPPER_STYLE}">` +
				`<div style="${CODE_HEADER_STYLE}">` +
					`<span style="${CODE_LANG_STYLE}">${displayLang}</span>` +
					`<a href="copy:${idx}" style="${CODE_COPY_STYLE}">复制代码</a>` +
				`</div>` +
				`<pre style="${CODE_PRE_STYLE}"><code style="${CODE_STYLE}">${safeCode}</code></pre>` +
			`</div>`
		)
		return `@@CODE_BLOCK_${idx}@@`
	})

	content = escapeHtml(content)

	content = content
		.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>')
		.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>')
		.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>')

	content = content.replace(/(^|\n)(-{3,}|\*{3,})(?=\n|$)/g, '$1<hr/>')

	content = content.replace(/(?:^|\n)(?:[-*]\s+.+(?:\n[-*]\s+.+)*)/g, (block) => {
		const items = block
			.trim()
			.split('\n')
			.map((line) => `<li>${line.replace(/^[-*]\s+/, '')}</li>`)
			.join('')
		return `\n<ul>${items}</ul>`
	})

	content = content.replace(/(?:^|\n)(?:\d+\.\s+.+(?:\n\d+\.\s+.+)*)/g, (block) => {
		const items = block
			.trim()
			.split('\n')
			.map((line) => `<li>${line.replace(/^\d+\.\s+/, '')}</li>`)
			.join('')
		return `\n<ol>${items}</ol>`
	})

	content = content.replace(/(^|\n)>\s?(.*)(?=\n|$)/g, '$1<blockquote>$2</blockquote>')

	content = content.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, (match, label, url) => {
		if (!isSafeHttpUrl(url)) return label
		return `<a href="${url}" style="${LINK_INLINE_STYLE}">${label}</a>`
	})

	content = content
		.replace(/`([^`\n]+)`/g, '<code>$1</code>')
		.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
		.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')

	const protectedSegments = []
	content = content.replace(/<a href="[^"]+">[\s\S]*?<\/a>|<code>[\s\S]*?<\/code>/g, (segment) => {
		const key = `@@PROTECTED_SEGMENT_${protectedSegments.length}@@`
		protectedSegments.push({ key, html: segment })
		return key
	})

	content = linkifyRawUrls(content)

	for (const item of protectedSegments) {
		content = content.split(item.key).join(item.html)
	}

	content = content.replace(/\n/g, '<br/>')

	content = content
		.replace(/<br\/>(<\/?(?:h1|h2|h3|ul|ol|li|blockquote|pre|hr)[^>]*>)/g, '$1')
		.replace(/(<\/?(?:h1|h2|h3|ul|ol|li|blockquote|pre|hr)[^>]*>)<br\/>/g, '$1')

	for (let i = 0; i < codeBlocks.length; i++) {
		content = content.split(`@@CODE_BLOCK_${i}@@`).join(codeBlocks[i])
	}

	return { html: content, codeContents }
}

function renderLatex(formula, displayMode) {
	try {
		return katex.renderToString(formula, {
			throwOnError: false,
			displayMode: displayMode,
			output: 'html',
			strict: false
		})
	} catch (e) {
		return `<span class="katex-error">${formula}</span>`
	}
}

function processLatex(text) {
	if (!text) {
		return { text: '', placeholders: [] }
	}

	const placeholders = []
	let processed = text

	// KaTeX 块级公式内联样式
	const katexBlockStyle = 'display:block; text-align:center; margin:16px 0; padding:12px; overflow-x:auto; max-width:100%;'

	processed = processed.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
		const rendered = renderLatex(formula.trim(), true)
		const key = `@@LATEX_BLOCK_${placeholders.length}@@`
		placeholders.push({ key, html: `<div class="katex-block" style="${katexBlockStyle}">${rendered}</div>` })
		return `\n${key}\n`
	})

	// 避免 lookbehind，兼容旧 Android JS 引擎
	processed = processed.replace(/(^|[^$])\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (match, prefix, formula) => {
		// 只跳过纯数字/货币格式（如 $10, $10.00, $1,000），允许包含 LaTeX 命令的数字公式
		if (/^[\d,]+(\.\d+)?$/.test(formula.trim())) {
			return match
		}
		const rendered = renderLatex(formula.trim(), false)
		const key = `@@LATEX_INLINE_${placeholders.length}@@`
		placeholders.push({ key, html: `<span class="katex-inline">${rendered}</span>` })
		return `${prefix}${key}`
	})

	return { text: processed, placeholders }
}

function restorePlaceholders(text, placeholders) {
	let output = text
	for (const item of placeholders) {
		output = output.split(item.key).join(item.html)
	}
	return output
}

export default {
	name: 'MarkdownRender',
	props: {
		content: {
			type: String,
			default: ''
		}
	},
	data() {
		return {
			codeContents: []
		}
	},
	methods: {
		onRichTextItemClick(event) {
			const detail = event && event.detail
			const node = detail && detail.node
			const nodeName = node && node.name
			const attrs = node && node.attrs
			const href = attrs && attrs.href

			if (nodeName !== 'a' || !href) {
				return
			}

			// 处理复制代码操作
			if (href.startsWith('copy:')) {
				const index = parseInt(href.slice(5), 10)
				this.copyCode(index)
				return
			}

			// 处理外部链接
			if (isSafeHttpUrl(href)) {
				this.openExternalLink(href)
			}
		},
		copyCode(index) {
			const code = this.codeContents[index]
			if (code === undefined) return

			uni.setClipboardData({
				data: code,
				success: () => {
					uni.showToast({ title: '已复制', icon: 'success' })
				}
			})
		},
		openExternalLink(url) {
			// #ifdef APP-PLUS
			plus.runtime.openURL(url)
			return
			// #endif

			// #ifdef H5
			window.open(url, '_blank')
			return
			// #endif

			uni.setClipboardData({
				data: url,
				success: () => {
					uni.showToast({ title: '链接已复制', icon: 'none' })
				}
			})
		}
	},
	computed: {
		parsedHtml() {
			if (!this.content) return ''
			try {
				const latexResult = processLatex(this.content)
				const markdownResult = parseSimpleMarkdown(latexResult.text)

				// 保存代码内容供复制使用
				this.codeContents = markdownResult.codeContents

				return restorePlaceholders(markdownResult.html, latexResult.placeholders)
			} catch (e) {
				console.error('Markdown parse error:', e)
				return escapeHtml(this.content)
			}
		}
	}
}
</script>

<style scoped>
.markdown-container {
	width: 100%;
	overflow: hidden;
	/* 启用 APP 端长按选择复制 */
	-webkit-user-select: text;
	-moz-user-select: text;
	-ms-user-select: text;
	user-select: text;
}

/* 基础文本 */
.markdown-content {
	font-size: 30rpx;
	line-height: 1.6;
	color: #ffffff;
	word-break: break-word;
}
</style>

<style>
/* 全局样式 - rich-text内部元素 */
.markdown-content p {
	margin: 0 0 16rpx 0;
}

.markdown-content strong {
	font-weight: 600;
	color: #ffffff;
}

.markdown-content em {
	font-style: italic;
}

/* 标题 */
.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
	font-weight: 600;
	margin: 24rpx 0 16rpx 0;
	color: #ffffff;
}

.markdown-content h1 { font-size: 40rpx; }
.markdown-content h2 { font-size: 36rpx; }
.markdown-content h3 { font-size: 32rpx; }

/* 列表 */
.markdown-content ul,
.markdown-content ol {
	padding-left: 40rpx;
	margin: 16rpx 0;
}

.markdown-content li {
	margin: 8rpx 0;
}

/* 代码块 */
.markdown-content pre,
.markdown-content .hljs-code-block {
	background: rgba(0, 0, 0, 0.4);
	border-radius: 12rpx;
	padding: 20rpx;
	margin: 16rpx 0;
	overflow-x: auto;
}

.markdown-content code {
	font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
	font-size: 26rpx;
}

/* 行内代码 */
.markdown-content p code,
.markdown-content li code {
	background: rgba(255, 255, 255, 0.15);
	padding: 4rpx 10rpx;
	border-radius: 6rpx;
	font-size: 28rpx;
}

/* 链接 */
.markdown-content a {
	color: rgb(92, 144, 247);
	text-decoration: none;
}

/* 引用 */
.markdown-content blockquote {
	border-left: 4rpx solid rgba(255, 255, 255, 0.3);
	padding-left: 20rpx;
	margin: 16rpx 0;
	color: rgba(255, 255, 255, 0.8);
}

/* 分隔线 */
.markdown-content hr {
	border: none;
	border-top: 1px solid rgba(255, 255, 255, 0.2);
	margin: 24rpx 0;
}

/* ===== Highlight.js 代码高亮主题（深色） ===== */
.hljs-keyword { color: #c792ea; }
.hljs-string { color: #c3e88d; }
.hljs-number { color: #f78c6c; }
.hljs-function { color: #82aaff; }
.hljs-title { color: #82aaff; }
.hljs-params { color: #89ddff; }
.hljs-comment { color: #676e95; font-style: italic; }
.hljs-built_in { color: #ffcb6b; }
.hljs-attr { color: #ffcb6b; }
.hljs-literal { color: #f78c6c; }
.hljs-type { color: #ffcb6b; }
.hljs-variable { color: #f07178; }
.hljs-selector-class { color: #ffcb6b; }
.hljs-selector-id { color: #82aaff; }
.hljs-selector-tag { color: #f07178; }
.hljs-property { color: #89ddff; }

/* ===== KaTeX 数学公式样式 ===== */

/* 块级公式容器 */
.katex-block {
	display: block;
	text-align: center;
	margin: 20rpx 0;
	padding: 16rpx;
	overflow-x: auto;
	overflow-y: hidden;
}

/* 行内公式容器 */
.katex-inline {
	display: inline;
}

/* KaTeX 渲染错误提示 */
.katex-error {
	color: #ef4444;
	background: rgba(239, 68, 68, 0.1);
	padding: 4rpx 8rpx;
	border-radius: 4rpx;
	font-family: monospace;
}

/* KaTeX 核心样式 - 深色主题适配 */
.katex {
	font-size: 1.1em;
	line-height: 1.2;
	color: #ffffff;
}

.katex .katex-html {
	color: #ffffff;
}

/* 分数线颜色 */
.katex .frac-line {
	background: #ffffff;
}

/* 根号线颜色 */
.katex .sqrt-line {
	background: #ffffff;
}

/* 矩阵括号颜色 */
.katex .delimsizing,
.katex .delimsizinginner {
	color: #ffffff;
}

/* 上下标 */
.katex .msupsub {
	text-align: left;
}

/* 操作符 */
.katex .mop {
	color: #82aaff;
}

/* 变量 */
.katex .mord.mathnormal {
	color: #ffffff;
}

/* 数字 */
.katex .mord.text {
	color: #f78c6c;
}
</style>
