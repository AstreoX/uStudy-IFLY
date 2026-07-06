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
  return text.replace(/(^|[\s(])((?:https?:\/\/)[^\s<>"']+)/gi, (match, prefix, candidate) => {
    const { url, suffix } = splitTrailingUrlSuffix(candidate)
    if (!url || !isSafeHttpUrl(url)) return match
    return `${prefix}<a href="${url}" style="${LINK_INLINE_STYLE}">${url}</a>${suffix}`
  })
}

const CODE_WRAPPER_STYLE = 'background:rgba(30,30,30,0.95); border-radius:12px; margin:16px 0; overflow:hidden;'
const CODE_HEADER_STYLE = 'display:flex; justify-content:space-between; align-items:center; padding:8px 16px; background:rgba(255,255,255,0.05); border-bottom:1px solid rgba(255,255,255,0.1);'
const CODE_LANG_STYLE = 'color:rgba(255,255,255,0.6); font-size:12px;'
const CODE_COPY_STYLE = 'color:#5c90f7; font-size:12px; text-decoration:none; cursor:pointer;'
const CODE_PRE_STYLE = 'overflow-x:auto; margin:0; padding:16px; white-space:pre; background:transparent;'
const CODE_STYLE = 'font-family:SF Mono,Monaco,Consolas,monospace; font-size:13px; color:#e0e0e0;'

// Table inline styles (dark theme)
const TABLE_WRAPPER_STYLE = 'overflow-x:auto; margin:12px 0;'
const TABLE_STYLE = 'border-collapse:collapse; width:100%;'
const TABLE_TH_STYLE = 'border:1px solid rgba(255,255,255,0.2); padding:8px 12px; background:rgba(255,255,255,0.08); font-weight:600; color:#ffffff; text-align:left;'
const TABLE_TD_STYLE = 'border:1px solid rgba(255,255,255,0.15); padding:8px 12px; color:#ffffff;'

function parseSimpleMarkdown(text) {
  if (!text) return { html: '', codeContents: [] }

  const codeBlocks = []
  const codeContents = []
  let content = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    const idx = codeBlocks.length
    const safeLang = escapeHtml((lang || '').trim())
    const rawCode = (code || '').replace(/^\n+|\n+$/g, '')
    const safeCode = escapeHtml(rawCode)
    const displayLang = safeLang || 'code'

    codeContents.push(rawCode)

    codeBlocks.push(
      `<div style="${CODE_WRAPPER_STYLE}">` +
        `<div style="${CODE_HEADER_STYLE}">` +
          `<span style="${CODE_LANG_STYLE}">${displayLang}</span>` +
          `<a href="copy:${idx}" style="${CODE_COPY_STYLE}">Copy</a>` +
        `</div>` +
        `<pre style="${CODE_PRE_STYLE}"><code style="${CODE_STYLE}">${safeCode}</code></pre>` +
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
  if (!text) return { text: '', placeholders: [] }

  const placeholders = []
  let processed = text
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

  // 块级公式 $$...$$
  processed = processed.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
    const rendered = renderLatex(formula.trim(), true)
    const key = `@@LATEX_BLOCK_${placeholders.length}@@`
    placeholders.push({ key, html: `<div class="katex-block" style="${katexBlockStyle}">${rendered}</div>` })
    return `\n${key}\n`
  })

  // 行内公式 $...$ （跳过货币格式如 $10, $10.00）
  processed = processed.replace(/(^|[^$])\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (match, prefix, formula) => {
    if (/^[\d,]+(\.\d+)?$/.test(formula.trim())) return match
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
  methods: {
    onRichTextItemClick(event) {
      const detail = event && event.detail
      const node = detail && detail.node
      const nodeName = node && node.name
      const attrs = node && node.attrs
      const href = attrs && attrs.href

      if (nodeName !== 'a' || !href) return

      if (href.startsWith('copy:')) {
        const index = parseInt(href.slice(5), 10)
        this.copyCode(index)
        return
      }

      if (isSafeHttpUrl(href)) {
        window.open(href, '_blank')
      }
    },
    copyCode(index) {
      const code = this.markdownResult.codeContents[index]
      if (code === undefined) return

      if (navigator.clipboard) {
        navigator.clipboard.writeText(code).then(() => {
          uni.showToast({ title: 'Copied', icon: 'success' })
        })
      } else {
        uni.setClipboardData({
          data: code,
          success: () => {
            uni.showToast({ title: 'Copied', icon: 'success' })
          }
        })
      }
    }
  },
  computed: {
    markdownResult() {
      if (!this.content) return { html: '', codeContents: [] }
      try {
        // 先处理 LaTeX 公式，再处理 Markdown
        const latexResult = processLatex(this.content)
        const markdownResult = parseSimpleMarkdown(latexResult.text)
        return {
          html: restorePlaceholders(markdownResult.html, latexResult.placeholders),
          codeContents: markdownResult.codeContents
        }
      } catch (e) {
        return { html: escapeHtml(this.content), codeContents: [] }
      }
    },
    parsedHtml() {
      return this.markdownResult.html
    }
  }
}
</script>

<style scoped>
.markdown-container {
  width: 100%;
  overflow: hidden;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
  user-select: text;
}

.markdown-content {
  font-size: 14px;
  line-height: 1.6;
  color: #ffffff;
  word-break: break-word;
}
</style>

<style>
.markdown-content p {
  margin: 0 0 8px 0;
}

.markdown-content strong {
  font-weight: 600;
  color: #ffffff;
}

.markdown-content em {
  font-style: italic;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  font-weight: 600;
  margin: 12px 0 8px 0;
  color: #ffffff;
}

.markdown-content h1 { font-size: 20px; }
.markdown-content h2 { font-size: 18px; }
.markdown-content h3 { font-size: 16px; }

.markdown-content ul,
.markdown-content ol {
  padding-left: 20px;
  margin: 8px 0;
}

.markdown-content li {
  margin: 4px 0;
}

.markdown-content pre {
  background: rgba(0, 0, 0, 0.4);
  border-radius: 6px;
  padding: 10px;
  margin: 8px 0;
  overflow-x: auto;
}

.markdown-content code {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 13px;
}

.markdown-content p code,
.markdown-content li code {
  background: rgba(255, 255, 255, 0.15);
  padding: 2px 5px;
  border-radius: 3px;
  font-size: 13px;
}

.markdown-content a {
  color: rgb(92, 144, 247);
  text-decoration: none;
}

.markdown-content blockquote {
  border-left: 2px solid rgba(255, 255, 255, 0.3);
  padding-left: 10px;
  margin: 8px 0;
  color: rgba(255, 255, 255, 0.8);
}

.markdown-content hr {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  margin: 12px 0;
}

/* 表格 */
.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}
.markdown-content th,
.markdown-content td {
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 8px 12px;
}
.markdown-content th {
  background: rgba(255, 255, 255, 0.08);
  font-weight: 600;
}

/* ===== KaTeX 数学公式样式 ===== */

/* 块级公式容器 */
.katex-block {
  display: block;
  text-align: center;
  margin: 16px 0;
  padding: 12px;
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
  padding: 2px 4px;
  border-radius: 4px;
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
