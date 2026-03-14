<template>
	<view class="markdown-container">
		<!-- #ifdef APP-PLUS -->
		<view
			class="markdown-content app-rich-content"
			:prop="parsedHtml"
			:change:prop="mdRender.onContentChange"
		></view>
		<!-- #endif -->

		<!-- #ifndef APP-PLUS -->
		<rich-text
			:nodes="parsedHtml"
			class="markdown-content"
			selectable="true"
			@itemclick="onRichTextItemClick"
		></rich-text>
		<!-- #endif -->
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

const MARKDOWN_TEXT_COLOR = '#E5E5E5'
const MARKDOWN_MUTED_COLOR = '#A3A3A3'
const MARKDOWN_BORDER_COLOR = '#333333'
const MARKDOWN_SURFACE_COLOR = '#111111'
const MARKDOWN_SURFACE_ELEVATED_COLOR = '#1A1A1A'

const ONE_DARK_BG = '#282C34'
const ONE_DARK_BG_ELEVATED = '#21252B'
const ONE_DARK_BORDER = '#3E4451'
const ONE_DARK_TEXT = '#ABB2BF'
const ONE_DARK_MUTED = '#7F848E'
const ONE_DARK_BLUE = '#61AFEF'
const ONE_DARK_CYAN = '#56B6C2'
const ONE_DARK_GREEN = '#98C379'
const ONE_DARK_ORANGE = '#D19A66'
const ONE_DARK_PURPLE = '#C678DD'
const ONE_DARK_RED = '#E06C75'
const ONE_DARK_YELLOW = '#E5C07B'

// 代码块内联样式（rich-text 不支持外部 CSS）
const CODE_WRAPPER_STYLE = `background:${ONE_DARK_BG}; border:1px solid ${ONE_DARK_BORDER}; border-radius:12px; margin:16px 0; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,0.22);`
const CODE_HEADER_STYLE = `display:flex; justify-content:space-between; align-items:center; padding:8px 16px; background:${ONE_DARK_BG_ELEVATED}; border-bottom:1px solid ${ONE_DARK_BORDER};`
const CODE_LANG_STYLE = `color:${ONE_DARK_MUTED}; font-size:12px; letter-spacing:0.04em; text-transform:lowercase;`
const CODE_COPY_STYLE = `color:${ONE_DARK_BLUE}; font-size:12px; text-decoration:none;`
const CODE_PRE_STYLE = 'overflow-x:auto; margin:0; padding:16px; white-space:pre; background:transparent;'
const CODE_STYLE = `font-family:SF Mono,Monaco,Consolas,monospace; font-size:13px; color:${ONE_DARK_TEXT}; -webkit-text-fill-color:${ONE_DARK_TEXT};`

// App 端 renderjs 动态插入的高亮节点，不能稳定依赖外部 class 样式，直接内联 token 颜色。
const HLJS_TOKEN_STYLE_MAP = {
	'hljs-comment': `color:${ONE_DARK_MUTED};-webkit-text-fill-color:${ONE_DARK_MUTED};font-style:italic;`,
	'hljs-quote': `color:${ONE_DARK_MUTED};-webkit-text-fill-color:${ONE_DARK_MUTED};font-style:italic;`,
	'hljs-keyword': `color:${ONE_DARK_PURPLE};-webkit-text-fill-color:${ONE_DARK_PURPLE};`,
	'hljs-selector-tag': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`,
	'hljs-tag': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`,
	'hljs-name': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`,
	'hljs-literal': `color:${ONE_DARK_ORANGE};-webkit-text-fill-color:${ONE_DARK_ORANGE};`,
	'hljs-link': `color:${ONE_DARK_BLUE};-webkit-text-fill-color:${ONE_DARK_BLUE};text-decoration:underline;`,
	'hljs-string': `color:${ONE_DARK_GREEN};-webkit-text-fill-color:${ONE_DARK_GREEN};`,
	'hljs-regexp': `color:${ONE_DARK_CYAN};-webkit-text-fill-color:${ONE_DARK_CYAN};`,
	'hljs-addition': `color:${ONE_DARK_GREEN};-webkit-text-fill-color:${ONE_DARK_GREEN};`,
	'hljs-number': `color:${ONE_DARK_ORANGE};-webkit-text-fill-color:${ONE_DARK_ORANGE};`,
	'hljs-symbol': `color:${ONE_DARK_ORANGE};-webkit-text-fill-color:${ONE_DARK_ORANGE};`,
	'hljs-bullet': `color:${ONE_DARK_ORANGE};-webkit-text-fill-color:${ONE_DARK_ORANGE};`,
	'hljs-built_in': `color:${ONE_DARK_CYAN};-webkit-text-fill-color:${ONE_DARK_CYAN};`,
	'hljs-type': `color:${ONE_DARK_YELLOW};-webkit-text-fill-color:${ONE_DARK_YELLOW};`,
	'hljs-class': `color:${ONE_DARK_YELLOW};-webkit-text-fill-color:${ONE_DARK_YELLOW};`,
	'hljs-title': `color:${ONE_DARK_BLUE};-webkit-text-fill-color:${ONE_DARK_BLUE};`,
	'hljs-function': `color:${ONE_DARK_BLUE};-webkit-text-fill-color:${ONE_DARK_BLUE};`,
	'hljs-params': `color:${ONE_DARK_TEXT};-webkit-text-fill-color:${ONE_DARK_TEXT};`,
	'hljs-variable': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`,
	'hljs-property': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`,
	'hljs-attr': `color:${ONE_DARK_YELLOW};-webkit-text-fill-color:${ONE_DARK_YELLOW};`,
	'hljs-operator': `color:${ONE_DARK_TEXT};-webkit-text-fill-color:${ONE_DARK_TEXT};`,
	'hljs-punctuation': `color:${ONE_DARK_TEXT};-webkit-text-fill-color:${ONE_DARK_TEXT};`,
	'hljs-meta': `color:${ONE_DARK_PURPLE};-webkit-text-fill-color:${ONE_DARK_PURPLE};`,
	'hljs-doctag': `color:${ONE_DARK_PURPLE};-webkit-text-fill-color:${ONE_DARK_PURPLE};`,
	'hljs-section': `color:${ONE_DARK_BLUE};-webkit-text-fill-color:${ONE_DARK_BLUE};`,
	'hljs-emphasis': 'font-style:italic;',
	'hljs-strong': 'font-weight:700;',
	'hljs-deletion': `color:${ONE_DARK_RED};-webkit-text-fill-color:${ONE_DARK_RED};`
}

function getHljsInlineStyle(className) {
	const classNames = String(className || '').split(/\s+/).filter(Boolean)
	const styles = []

	classNames.forEach((name) => {
		const style = HLJS_TOKEN_STYLE_MAP[name]
		if (style && !styles.includes(style)) {
			styles.push(style)
		}
	})

	return styles.join('')
}

function buildStyledTokenEscaped(escapedContent, className) {
	const inlineStyle = getHljsInlineStyle(className)
	if (!inlineStyle) return escapedContent
	return `<span class="${className}" style="${inlineStyle}">${escapedContent}</span>`
}

function buildStyledToken(rawContent, className) {
	return buildStyledTokenEscaped(escapeHtml(rawContent), className)
}

// Table inline styles (dark theme, rpx units for app)
const TABLE_WRAPPER_STYLE = 'overflow-x:auto; margin:24rpx 0;'
const TABLE_STYLE = 'border-collapse:collapse; width:100%;'
const TABLE_TH_STYLE = `border:1px solid ${MARKDOWN_BORDER_COLOR}; padding:16rpx 24rpx; background:${MARKDOWN_SURFACE_ELEVATED_COLOR}; font-weight:600; color:${MARKDOWN_TEXT_COLOR}; text-align:left;`
const TABLE_TD_STYLE = `border:1px solid ${MARKDOWN_BORDER_COLOR}; padding:16rpx 24rpx; color:${MARKDOWN_TEXT_COLOR};`

const LANGUAGE_SPECS = {
	python: {
		lineComments: ['#'],
		blockComments: [],
		stringQuotes: ["'''", '"""', "'", '"'],
		caseInsensitive: false,
		keywords: ['and', 'as', 'assert', 'async', 'await', 'break', 'case', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'match', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield'],
		literals: ['True', 'False', 'None'],
		builtins: ['abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float', 'input', 'int', 'len', 'list', 'map', 'max', 'min', 'open', 'print', 'range', 'set', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip']
	},
	javascript: {
		lineComments: ['//'],
		blockComments: [['/*', '*/']],
		stringQuotes: ['`', "'", '"'],
		caseInsensitive: false,
		keywords: ['async', 'await', 'break', 'case', 'catch', 'class', 'const', 'continue', 'default', 'delete', 'do', 'else', 'export', 'extends', 'finally', 'for', 'function', 'if', 'import', 'in', 'instanceof', 'let', 'new', 'of', 'return', 'super', 'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void', 'while', 'yield'],
		literals: ['true', 'false', 'null', 'undefined', 'NaN', 'Infinity'],
		builtins: ['Array', 'Boolean', 'console', 'Date', 'JSON', 'Map', 'Math', 'Number', 'Object', 'Promise', 'RegExp', 'Set', 'String', 'Symbol']
	},
	typescript: {
		lineComments: ['//'],
		blockComments: [['/*', '*/']],
		stringQuotes: ['`', "'", '"'],
		caseInsensitive: false,
		keywords: ['abstract', 'any', 'as', 'async', 'await', 'break', 'case', 'catch', 'class', 'const', 'continue', 'declare', 'default', 'delete', 'do', 'else', 'enum', 'export', 'extends', 'finally', 'for', 'function', 'if', 'implements', 'import', 'in', 'infer', 'instanceof', 'interface', 'keyof', 'let', 'module', 'namespace', 'new', 'private', 'protected', 'public', 'readonly', 'return', 'satisfies', 'static', 'super', 'switch', 'this', 'throw', 'try', 'type', 'typeof', 'var', 'void', 'while'],
		literals: ['true', 'false', 'null', 'undefined', 'never', 'unknown'],
		builtins: ['Array', 'Boolean', 'console', 'Date', 'JSON', 'Map', 'Math', 'Number', 'Object', 'Promise', 'Record', 'Set', 'String']
	},
	json: {
		lineComments: [],
		blockComments: [],
		stringQuotes: ['"'],
		caseInsensitive: false,
		keywords: [],
		literals: ['true', 'false', 'null'],
		builtins: []
	},
	bash: {
		lineComments: ['#'],
		blockComments: [],
		stringQuotes: ['`', "'", '"'],
		caseInsensitive: false,
		keywords: ['case', 'do', 'done', 'elif', 'else', 'esac', 'fi', 'for', 'function', 'if', 'in', 'select', 'then', 'until', 'while'],
		literals: ['true', 'false'],
		builtins: ['awk', 'cat', 'cd', 'curl', 'echo', 'export', 'find', 'grep', 'printf', 'pwd', 'sed', 'ssh', 'test', 'tr', 'uniq', 'xargs']
	},
	sql: {
		lineComments: ['--', '#'],
		blockComments: [['/*', '*/']],
		stringQuotes: ["'", '"', '`'],
		caseInsensitive: true,
		keywords: ['add', 'alter', 'and', 'as', 'asc', 'between', 'by', 'case', 'create', 'delete', 'desc', 'distinct', 'drop', 'else', 'end', 'exists', 'from', 'group', 'having', 'in', 'inner', 'insert', 'into', 'join', 'left', 'like', 'limit', 'not', 'null', 'offset', 'on', 'or', 'order', 'outer', 'right', 'select', 'set', 'table', 'then', 'union', 'update', 'values', 'when', 'where'],
		literals: ['true', 'false', 'null'],
		builtins: ['avg', 'count', 'coalesce', 'max', 'min', 'now', 'round', 'sum']
	},
	css: {
		lineComments: [],
		blockComments: [['/*', '*/']],
		stringQuotes: ["'", '"'],
		caseInsensitive: false,
		keywords: ['important'],
		literals: [],
		builtins: []
	}
}

const SUPPORTED_CODE_LANGUAGES = Object.keys(LANGUAGE_SPECS).concat(['xml'])

function escapeRegExp(text) {
	return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildKeywordRegex(words, caseInsensitive) {
	if (!words || !words.length) return null
	const sortedWords = words.slice().sort((a, b) => b.length - a.length)
	return new RegExp(`\\b(${sortedWords.map(escapeRegExp).join('|')})\\b`, caseInsensitive ? 'gi' : 'g')
}

function findLineEnd(text, startIndex) {
	const lineBreakIndex = text.indexOf('\n', startIndex)
	return lineBreakIndex === -1 ? text.length : lineBreakIndex
}

function findStringEnd(text, startIndex, quote) {
	let index = startIndex + quote.length

	while (index < text.length) {
		if (quote.length === 1 && text[index] === '\\') {
			index += 2
			continue
		}
		if (text.slice(index, index + quote.length) === quote) {
			return index + quote.length
		}
		index += 1
	}

	return text.length
}

function scanCodeSegments(text, spec) {
	const segments = []
	let plainStart = 0
	let index = 0

	function pushPlain(endIndex) {
		if (endIndex > plainStart) {
			segments.push({ type: 'plain', content: text.slice(plainStart, endIndex) })
		}
	}

	while (index < text.length) {
		let matched = false

		for (let i = 0; i < spec.blockComments.length; i++) {
			const startToken = spec.blockComments[i][0]
			const endToken = spec.blockComments[i][1]
			if (text.slice(index, index + startToken.length) === startToken) {
				pushPlain(index)
				const endIndex = text.indexOf(endToken, index + startToken.length)
				const segmentEnd = endIndex === -1 ? text.length : endIndex + endToken.length
				segments.push({ type: 'comment', content: text.slice(index, segmentEnd) })
				index = segmentEnd
				plainStart = index
				matched = true
				break
			}
		}
		if (matched) continue

		for (let i = 0; i < spec.lineComments.length; i++) {
			const marker = spec.lineComments[i]
			if (text.slice(index, index + marker.length) === marker) {
				pushPlain(index)
				const segmentEnd = findLineEnd(text, index)
				segments.push({ type: 'comment', content: text.slice(index, segmentEnd) })
				index = segmentEnd
				plainStart = index
				matched = true
				break
			}
		}
		if (matched) continue

		for (let i = 0; i < spec.stringQuotes.length; i++) {
			const quote = spec.stringQuotes[i]
			if (text.slice(index, index + quote.length) === quote) {
				pushPlain(index)
				const segmentEnd = findStringEnd(text, index, quote)
				segments.push({ type: 'string', content: text.slice(index, segmentEnd) })
				index = segmentEnd
				plainStart = index
				matched = true
				break
			}
		}
		if (matched) continue

		index += 1
	}

	pushPlain(text.length)
	return segments
}

function highlightMarkupAttributes(rawAttrs) {
	const attrRegex = /([:@A-Za-z_][-A-Za-z0-9_:.]*)(\s*=\s*)(".*?"|'.*?'|[^\s"'=<>`]+)/g
	let output = ''
	let lastIndex = 0
	let match = attrRegex.exec(rawAttrs)

	while (match) {
		output += escapeHtml(rawAttrs.slice(lastIndex, match.index))
		output += buildStyledToken(match[1], 'hljs-attr')
		output += escapeHtml(match[2])
		output += buildStyledToken(match[3], 'hljs-string')
		lastIndex = match.index + match[0].length
		match = attrRegex.exec(rawAttrs)
	}

	output += escapeHtml(rawAttrs.slice(lastIndex))
	return output
}

function highlightMarkupCode(rawCode) {
	const tagRegex = /<!--[\s\S]*?-->|<\/?[^>\n]+>/g
	let output = ''
	let lastIndex = 0
	let match = tagRegex.exec(rawCode)

	while (match) {
		output += escapeHtml(rawCode.slice(lastIndex, match.index))
		const token = match[0]

		if (token.slice(0, 4) === '<!--') {
			output += buildStyledToken(token, 'hljs-comment')
		} else {
			const parsed = token.match(/^<(\/?)([A-Za-z][A-Za-z0-9:_-]*)([\s\S]*?)(\/?)>$/)
			if (!parsed) {
				output += escapeHtml(token)
			} else {
				output += '&lt;'
				if (parsed[1]) output += '/'
				output += buildStyledToken(parsed[2], 'hljs-selector-tag')
				output += highlightMarkupAttributes(parsed[3] || '')
				if (parsed[4]) output += '/'
				output += '&gt;'
			}
		}

		lastIndex = match.index + token.length
		match = tagRegex.exec(rawCode)
	}

	output += escapeHtml(rawCode.slice(lastIndex))
	return output
}

function highlightPlainSegment(rawText, lang, spec) {
	let escapedText = escapeHtml(rawText)
	const caseInsensitive = !!spec.caseInsensitive
	const reserved = []

	function reservePattern(regex, renderer) {
		if (!regex) return
		escapedText = escapedText.replace(regex, (...args) => {
			const key = `@@CODE_SLOT_${reserved.length}_@@`
			reserved.push({ key, html: renderer(...args) })
			return key
		})
	}

	if (lang === 'python') {
		reservePattern(/(^|[\t ]+)(@[A-Za-z_][A-Za-z0-9_.]*)/gm, (match, prefix, decorator) => prefix + buildStyledTokenEscaped(decorator, 'hljs-meta'))
		reservePattern(/\b(def)(\s+)([A-Za-z_][A-Za-z0-9_]*)/g, (match, keyword, whitespace, name) => buildStyledTokenEscaped(keyword, 'hljs-keyword') + whitespace + buildStyledTokenEscaped(name, 'hljs-title'))
		reservePattern(/\b(class)(\s+)([A-Za-z_][A-Za-z0-9_]*)/g, (match, keyword, whitespace, name) => buildStyledTokenEscaped(keyword, 'hljs-keyword') + whitespace + buildStyledTokenEscaped(name, 'hljs-title'))
	}

	if (lang === 'javascript' || lang === 'typescript') {
		reservePattern(/\b(function)(\s+)([A-Za-z_$][A-Za-z0-9_$]*)/g, (match, keyword, whitespace, name) => buildStyledTokenEscaped(keyword, 'hljs-keyword') + whitespace + buildStyledTokenEscaped(name, 'hljs-title'))
		reservePattern(/\b(class)(\s+)([A-Za-z_$][A-Za-z0-9_$]*)/g, (match, keyword, whitespace, name) => buildStyledTokenEscaped(keyword, 'hljs-keyword') + whitespace + buildStyledTokenEscaped(name, 'hljs-title'))
	}

	if (lang === 'bash') {
		reservePattern(/(^|[^\\$])(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)/g, (match, prefix, variable) => prefix + buildStyledTokenEscaped(variable, 'hljs-variable'))
	}

	if (lang === 'json') {
		reservePattern(/(&quot;(?:\\.|[^&])*?&quot;)(\s*:)/g, (match, key, colon) => buildStyledTokenEscaped(key, 'hljs-attr') + colon)
	}

	if (lang === 'css') {
		reservePattern(/([A-Za-z-]+)(\s*:)/g, (match, property, colon) => buildStyledTokenEscaped(property, 'hljs-attr') + colon)
	}

	reservePattern(/\b(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/g, (match) => buildStyledTokenEscaped(match, 'hljs-number'))

	const keywordRegex = buildKeywordRegex(spec.keywords, caseInsensitive)
	if (keywordRegex) {
		reservePattern(keywordRegex, (match) => buildStyledTokenEscaped(match, 'hljs-keyword'))
	}

	const literalRegex = buildKeywordRegex(spec.literals, caseInsensitive)
	if (literalRegex) {
		reservePattern(literalRegex, (match) => buildStyledTokenEscaped(match, 'hljs-literal'))
	}

	const builtInRegex = buildKeywordRegex(spec.builtins, caseInsensitive)
	if (builtInRegex) {
		reservePattern(builtInRegex, (match) => buildStyledTokenEscaped(match, 'hljs-built_in'))
	}

	for (let i = 0; i < reserved.length; i++) {
		escapedText = escapedText.split(reserved[i].key).join(reserved[i].html)
	}

	return escapedText
}

function highlightGenericCode(rawCode, lang, spec) {
	const segments = scanCodeSegments(rawCode, spec)
	let html = ''

	for (let i = 0; i < segments.length; i++) {
		const segment = segments[i]
		if (segment.type === 'comment') {
			html += buildStyledToken(segment.content, 'hljs-comment')
		} else if (segment.type === 'string') {
			html += buildStyledToken(segment.content, 'hljs-string')
		} else {
			html += highlightPlainSegment(segment.content, lang, spec)
		}
	}

	return html
}

function detectCodeLanguage(rawCode) {
	const code = String(rawCode || '')
	if (!code.trim()) return ''

	if (/^\s*[\[{]/.test(code) && /"\s*:/.test(code)) return 'json'
	if (/(^|\n)\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(/.test(code) || /\bimport\s+[A-Za-z_][A-Za-z0-9_]*\b/.test(code) || /\bself\b/.test(code)) return 'python'
	if (/<[A-Za-z][^>\n]*>/.test(code) || /<\/[A-Za-z][^>\n]*>/.test(code) || /<!--[\s\S]*?-->/.test(code)) return 'xml'
	if (/\b(function|const|let|var|=>|console\.|import\s+.+from)\b/.test(code)) return 'javascript'
	if (/\b(select|insert|update|delete)\b[\s\S]*\b(from|into|set)\b/i.test(code)) return 'sql'
	if (/^\s*#!/.test(code) || /(^|\n)\s*(echo|export|fi|then|elif)\b/.test(code)) return 'bash'
	if (/(^|\n)\s*[.#]?[A-Za-z_-][A-Za-z0-9_-]*\s*\{/.test(code) || /(^|\n)\s*[A-Za-z-]+\s*:\s*[^;]+;/.test(code)) return 'css'
	return ''
}

function normalizeCodeLanguage(lang) {
	const normalized = String(lang || '').trim().toLowerCase()
	if (!normalized) return ''

	const aliasMap = {
		js: 'javascript',
		jsx: 'javascript',
		py: 'python',
		ts: 'typescript',
		tsx: 'typescript',
		sh: 'bash',
		shell: 'bash',
		zsh: 'bash',
		yml: 'yaml',
		md: 'markdown',
		plaintext: 'plaintext',
		text: 'plaintext',
		vue: 'xml',
		html: 'xml'
	}

	return aliasMap[normalized] || normalized
}

function sanitizeCodeLanguageClass(lang) {
	return String(lang || '').toLowerCase().replace(/[^a-z0-9_-]/g, '')
}

function highlightCode(rawCode, lang) {
	const normalizedLang = normalizeCodeLanguage(lang)
	const resolvedLang = SUPPORTED_CODE_LANGUAGES.indexOf(normalizedLang) !== -1 ? normalizedLang : detectCodeLanguage(rawCode)

	if (resolvedLang === 'xml') {
		return {
			html: highlightMarkupCode(rawCode),
			language: resolvedLang
		}
	}

	const spec = LANGUAGE_SPECS[resolvedLang]
	if (!spec) {
		return {
			html: escapeHtml(rawCode),
			language: normalizedLang || ''
		}
	}

	return {
		html: highlightGenericCode(rawCode, resolvedLang, spec),
		language: resolvedLang
	}
}

function parseSimpleMarkdown(text) {
	if (!text) return { html: '', codeContents: [] }

	const codeBlocks = []
	const codeContents = []
	let content = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
		const idx = codeBlocks.length
		const normalizedLang = normalizeCodeLanguage(lang)
		const rawCode = (code || '').replace(/^\n+|\n+$/g, '') // 去掉首尾空行
		const highlighted = highlightCode(rawCode, normalizedLang)
		const resolvedLang = String(lang || '').trim() || highlighted.language || 'code'
		const displayLang = escapeHtml(resolvedLang)
		const languageClass = sanitizeCodeLanguageClass(highlighted.language || normalizedLang)
		const codeClassAttr = `hljs hljs-code-block${languageClass ? ` language-${languageClass}` : ''}`

		// 保存原始代码供复制
		codeContents.push(rawCode)

		codeBlocks.push(
			`<div style="${CODE_WRAPPER_STYLE}">` +
				`<div style="${CODE_HEADER_STYLE}">` +
					`<span style="${CODE_LANG_STYLE}">${displayLang}</span>` +
					`<a href="copy:${idx}" style="${CODE_COPY_STYLE}">复制代码</a>` +
				`</div>` +
				`<pre style="${CODE_PRE_STYLE}"><code class="${codeClassAttr}" style="${CODE_STYLE}">${highlighted.html}</code></pre>` +
			`</div>`
		)
		return `@@CODE_BLOCK_${idx}@@`
	})

	// Extract markdown images before escapeHtml
	const imageBlocks = []
	content = content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
		const idx = imageBlocks.length
		const safeAlt = escapeHtml(alt || '图片')
		imageBlocks.push('')
		return `@@IMAGE_BLOCK_${idx}@@`
	})

	// Extract blockquotes (including GitHub-style alerts) before escapeHtml
	const blockquoteBlocks = []
	const ALERT_CONFIGS = {
		NOTE:      { color: '#3b82f6', bg: 'rgba(59,130,246,0.10)',  icon: 'ℹ' },
		TIP:       { color: '#22c55e', bg: 'rgba(34,197,94,0.10)',   icon: '💡' },
		WARNING:   { color: '#f97316', bg: 'rgba(249,115,22,0.10)',  icon: '⚠' },
		CAUTION:   { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',   icon: '🔴' },
		IMPORTANT: { color: '#a855f7', bg: 'rgba(168,85,247,0.10)', icon: '❗' },
	}
	content = content.replace(/((?:^[ \t]*>[^\n]*\n?)+)/gm, (match) => {
		const lines = match.split('\n').filter(l => l.trim() !== '')
		const stripped = lines.map(l => l.replace(/^[ \t]*>\s?/, ''))
		const firstLine = stripped[0] || ''
		const alertMatch = firstLine.match(/^\[!(NOTE|TIP|WARNING|CAUTION|IMPORTANT)\][ \t]*(.*)/i)
		let html
		if (alertMatch) {
			const type = alertMatch[1].toUpperCase()
			const titleExtra = alertMatch[2].trim()
			const cfg = ALERT_CONFIGS[type]
			const title = titleExtra ? `${cfg.icon} ${titleExtra}` : `${cfg.icon} ${type}`
			const bodyLines = stripped.slice(1)
			const body = bodyLines.map(l => escapeHtml(l)
				.replace(/`([^`\n]+)`/g, '<code>$1</code>')
				.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
				.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
			).join('<br/>')
			html = `<div style="border-left:3px solid ${cfg.color};background:${cfg.bg};padding:10px 14px;margin:10px 0;border-radius:0 6px 6px 0;">` +
				`<div style="color:${cfg.color};font-weight:600;margin-bottom:4px;font-size:13px;">${title}</div>` +
				`<div style="color:${MARKDOWN_TEXT_COLOR};font-size:14px;line-height:1.6;">${body}</div>` +
				`</div>`
		} else {
			const body = stripped.map(l => escapeHtml(l)
				.replace(/`([^`\n]+)`/g, '<code>$1</code>')
				.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
				.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
			).join('<br/>')
			html = `<blockquote style="border-left:3px solid ${MARKDOWN_BORDER_COLOR};padding-left:12px;margin:8px 0;color:${MARKDOWN_MUTED_COLOR};">${body}</blockquote>`
		}
		const idx = blockquoteBlocks.length
		blockquoteBlocks.push(html)
		return `\n@@BLOCKQUOTE_BLOCK_${idx}@@\n`
	})

	// Extract tables before escapeHtml (same placeholder pattern as code blocks)
	const tableBlocks = []
	content = content.replace(
		/(?:^|\n)((?:\|[^\n]+\|[ \t]*\n)+\|[\s:|-]+\|[ \t]*\n((?:\|[^\n]+\|[ \t]*\n?)*))/gm,
		(match, fullTable) => {
			const lines = fullTable.trim().split('\n').filter(l => l.trim())
			// Need at least header + separator + 1 data row
			if (lines.length < 3) return match

			// Parse header row
			const headerCells = lines[0].split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1).map(c => c.trim())
			// Parse separator row for alignment
			const sepCells = lines[1].split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1).map(c => c.trim())
			// Validate separator row
			if (!sepCells.every(s => /^:?-+:?$/.test(s))) return match

			const alignments = sepCells.map(sep => {
				if (/^:-+:$/.test(sep)) return 'center'
				if (/^-+:$/.test(sep)) return 'right'
				return 'left'
			})

			// Parse body rows
			const bodyRows = lines.slice(2).map(line =>
				line.split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1).map(c => c.trim())
			)

			// Build HTML with inline styles
			let html = `<div style="${TABLE_WRAPPER_STYLE}"><table style="${TABLE_STYLE}">`
			html += '<thead><tr>'
			headerCells.forEach((cell, i) => {
				const align = alignments[i] || 'left'
				html += `<th style="${TABLE_TH_STYLE}text-align:${align};">${escapeHtml(cell)}</th>`
			})
			html += '</tr></thead><tbody>'
			bodyRows.forEach(row => {
				html += '<tr>'
				headerCells.forEach((_, i) => {
					const cell = (row[i] || '').trim()
					const align = alignments[i] || 'left'
					html += `<td style="${TABLE_TD_STYLE}text-align:${align};">${escapeHtml(cell)}</td>`
				})
				html += '</tr>'
			})
			html += '</tbody></table></div>'

			const idx = tableBlocks.length
			tableBlocks.push(html)
			return `\n@@TABLE_BLOCK_${idx}@@\n`
		}
	)

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

	// blockquotes already extracted as blockquoteBlocks above

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

	// 引用标记 [1], [2] → 上标徽章样式
	// 在链接处理和 protected segments 恢复之后执行；[text](url) 已在前面被替换为 protected segment，无需 lookbehind
	content = content.replace(
		/\[(\d{1,2})\](?!\()/g,
		'<span style="display:inline-block;background:#3b82f6;color:#fff;font-size:10px;' +
		'line-height:14px;padding:0 4px;border-radius:7px;vertical-align:super;' +
		'margin:0 1px;font-weight:600;">$1</span>'
	)

	content = content.replace(/\n/g, '<br/>')

	content = content
		.replace(/<br\/>(<\/?(?:h1|h2|h3|ul|ol|li|blockquote|pre|hr|div|table|thead|tbody|tr|th|td)[^>]*>)/g, '$1')
		.replace(/(<\/?(?:h1|h2|h3|ul|ol|li|blockquote|pre|hr|div|table|thead|tbody|tr|th|td)[^>]*>)<br\/>/g, '$1')

	for (let i = 0; i < codeBlocks.length; i++) {
		content = content.split(`@@CODE_BLOCK_${i}@@`).join(codeBlocks[i])
	}

	for (let i = 0; i < tableBlocks.length; i++) {
		content = content.split(`@@TABLE_BLOCK_${i}@@`).join(tableBlocks[i])
	}

	for (let i = 0; i < imageBlocks.length; i++) {
		content = content.split(`@@IMAGE_BLOCK_${i}@@`).join(imageBlocks[i])
	}

	for (let i = 0; i < blockquoteBlocks.length; i++) {
		content = content.split(`@@BLOCKQUOTE_BLOCK_${i}@@`).join(blockquoteBlocks[i])
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

	// 块级公式 \[...\]（标准 LaTeX display math）
	processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, (match, formula) => {
		const rendered = renderLatex(formula.trim(), true)
		const key = `@@LATEX_BLOCK_${placeholders.length}@@`
		placeholders.push({ key, html: `<div class="katex-block" style="${katexBlockStyle}">${rendered}</div>` })
		return `\n${key}\n`
	})

	// 行内公式 \(...\)（标准 LaTeX inline math）
	processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, (match, formula) => {
		const rendered = renderLatex(formula.trim(), false)
		const key = `@@LATEX_INLINE_${placeholders.length}@@`
		placeholders.push({ key, html: `<span class="katex-inline">${rendered}</span>` })
		return key
	})

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
			codeContents: [],
			cachedHtml: '',
			_lastContent: ''
		}
	},
	methods: {
		onLinkClick(data) {
			const href = data && data.href
			if (!href) return
			if (isSafeHttpUrl(href)) {
				this.openExternalLink(href)
			}
		},
		onCodeCopy(data) {
			const index = data && data.index
			if (typeof index === 'number') {
				this.copyCode(index)
			}
		},
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
		_doParse(text) {
			try {
				const latexResult = processLatex(text)
				const markdownResult = parseSimpleMarkdown(latexResult.text)
				this.codeContents = markdownResult.codeContents
				this.cachedHtml = restorePlaceholders(markdownResult.html, latexResult.placeholders)
			} catch (e) {
				this.cachedHtml = escapeHtml(text)
			}
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
	watch: {
		content: {
			handler(val) {
				if (!val) {
					this.cachedHtml = ''
					this._lastContent = ''
					return
				}
				if (val.startsWith(this._lastContent) && this._lastContent.length > 0) {
					// Streaming append — debounce re-parse
					if (this._parseTimer) clearTimeout(this._parseTimer)
					this._parseTimer = setTimeout(() => {
						this._parseTimer = null
						this._doParse(this.content)
					}, 100)
				} else {
					// Full content change — parse immediately
					this._doParse(val)
				}
				this._lastContent = val
			},
			immediate: true
		}
	},
	computed: {
		parsedHtml() {
			return this.cachedHtml
		}
	},
	beforeDestroy() {
		if (this._parseTimer) {
			clearTimeout(this._parseTimer)
			this._parseTimer = null
		}
	}
}
</script>

<!-- #ifdef APP-PLUS -->
<script module="mdRender" lang="renderjs">
export default {
	methods: {
		onContentChange(newVal, oldVal, ownerInstance) {
			if (!ownerInstance) return
			const el = ownerInstance.$el
			if (!el) return

			const container = el.querySelector('.app-rich-content') || el
			if (!container) return

			container.innerHTML = newVal || ''

			const links = container.querySelectorAll('a[href]')
			links.forEach(function(link) {
				link.addEventListener('click', function(e) {
					e.preventDefault()
					e.stopPropagation()
					const href = link.getAttribute('href')
					if (href && href.indexOf('copy:') === 0) {
						ownerInstance.callMethod('onCodeCopy', {
							index: parseInt(href.slice(5), 10)
						})
					} else if (href) {
						ownerInstance.callMethod('onLinkClick', { href: href })
					}
				})
			})
		}
	}
}
</script>
<!-- #endif -->

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
	color: #E5E5E5;
	word-break: break-word;
}
</style>

<style>
/* APP-PLUS renderjs content inherits markdown styles */
.app-rich-content {
	-webkit-user-select: text;
	user-select: text;
}

/* 全局样式 - rich-text内部元素 */
.markdown-content p {
	margin: 0 0 16rpx 0;
}

.markdown-content strong {
	font-weight: 600;
	color: #E5E5E5;
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
	color: #E5E5E5;
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
	background: #282C34;
	border: 1px solid #3E4451;
	border-radius: 12rpx;
	padding: 20rpx;
	margin: 16rpx 0;
	overflow-x: auto;
}

.markdown-content code {
	font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
	font-size: 26rpx;
}

.markdown-content pre code,
.markdown-content .hljs-code-block,
.app-rich-content pre code,
.app-rich-content .hljs-code-block {
	display: block;
	background: transparent !important;
	padding: 0;
	margin: 0;
	line-height: 1.7;
	color: #ABB2BF;
	-webkit-text-fill-color: #ABB2BF;
}

/* 行内代码 */
.markdown-content p code,
.markdown-content li code {
	background: rgba(97, 175, 239, 0.12);
	padding: 4rpx 10rpx;
	border-radius: 6rpx;
	font-size: 28rpx;
	color: #E5C07B;
	-webkit-text-fill-color: #E5C07B;
}

/* 链接 */
.markdown-content a {
	color: rgb(92, 144, 247);
	text-decoration: none;
}

/* 引用 */
.markdown-content blockquote {
	border-left: 4rpx solid #333333;
	padding-left: 20rpx;
	margin: 16rpx 0;
	color: #A3A3A3;
}

/* 分隔线 */
.markdown-content hr {
	border: none;
	border-top: 1px solid #333333;
	margin: 24rpx 0;
}

/* 表格 */
.markdown-content table {
	border-collapse: collapse;
	width: 100%;
	margin: 24rpx 0;
}
.markdown-content th,
.markdown-content td {
	border: 1px solid #333333;
	padding: 16rpx 24rpx;
}
.markdown-content th {
	background: #1A1A1A;
	font-weight: 600;
}

/* ===== Highlight.js 代码高亮主题（深色） ===== */
.hljs-keyword { color: #C678DD; }
.hljs-string { color: #98C379; }
.hljs-number { color: #D19A66; }
.hljs-function { color: #61AFEF; }
.hljs-title { color: #61AFEF; }
.hljs-params { color: #ABB2BF; }
.hljs-comment { color: #7F848E; font-style: italic; }
.hljs-built_in { color: #56B6C2; }
.hljs-attr { color: #E5C07B; }
.hljs-literal { color: #D19A66; }
.hljs-type { color: #E5C07B; }
.hljs-variable { color: #E06C75; }
.hljs-selector-class { color: #E5C07B; }
.hljs-selector-id { color: #E06C75; }
.hljs-selector-tag { color: #E06C75; }
.hljs-property { color: #E06C75; }

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
	color: #E5E5E5;
}

.katex .katex-html {
	color: #E5E5E5;
}

/* 分数线颜色 */
.katex .frac-line {
	background: #E5E5E5;
}

/* 根号线颜色 */
.katex .sqrt-line {
	background: #E5E5E5;
}

/* 矩阵括号颜色 */
.katex .delimsizing,
.katex .delimsizinginner {
	color: #E5E5E5;
}

/* 上下标 */
.katex .msupsub {
	text-align: left;
}

/* 操作符 */
.katex .mop {
	color: #D4D4D4;
}

/* 变量 */
.katex .mord.mathnormal {
	color: #E5E5E5;
}

/* 数字 */
.katex .mord.text {
	color: #BFBFBF;
}
</style>
