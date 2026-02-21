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
        return parseSimpleMarkdown(this.content)
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
</style>
