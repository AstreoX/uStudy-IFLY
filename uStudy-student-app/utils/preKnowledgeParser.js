/**
 * 前置知识标签解析器
 * 从流式文本中实时解析 <PreKnowledge> 和 <Highlight> 标签
 */

// 状态机状态
const ParserState = {
  TEXT: 'text',           // 普通文本
  TAG_OPEN: 'tag_open',   // 检测到 '<'，等待标签名
  IN_TAG: 'in_tag',       // 在标签内容中
  TAG_CLOSE: 'tag_close'  // 检测到 '</'，等待关闭标签
}

// 支持的标签名
const KNOWN_TAGS = ['PreKnowledge', 'Highlight']

/**
 * 流式标签解析器
 * 处理跨 chunk 分割的标签，返回干净文本和事件列表
 */
export class PreKnowledgeTagParser {
  constructor() {
    this.state = ParserState.TEXT
    this.buffer = ''
    this.currentTag = null
    this.tagContent = ''
  }

  /**
   * 解析一个 chunk
   * @param {string} chunk - 输入文本块
   * @returns {{ cleanText: string, events: Array<{type: string, payload: string}> }}
   */
  parse(chunk) {
    const events = []
    let cleanText = ''

    for (let i = 0; i < chunk.length; i++) {
      const char = chunk[i]

      switch (this.state) {
        case ParserState.TEXT:
          if (char === '<') {
            this.state = ParserState.TAG_OPEN
            this.buffer = '<'
          } else {
            cleanText += char
          }
          break

        case ParserState.TAG_OPEN:
          this.buffer += char
          if (char === '/') {
            // 可能是关闭标签
            this.state = ParserState.TAG_CLOSE
          } else if (char === '>') {
            // 标签结束，检查是否是已知标签
            const tagName = this.extractOpenTagName(this.buffer)
            if (this.isKnownTag(tagName)) {
              this.currentTag = tagName
              this.state = ParserState.IN_TAG
              this.tagContent = ''
            } else {
              // 不是已知标签，输出 buffer
              cleanText += this.buffer
              this.state = ParserState.TEXT
            }
            this.buffer = ''
          } else if (!/[a-zA-Z]/.test(char)) {
            // 不是有效的标签字符，输出 buffer
            cleanText += this.buffer
            this.buffer = ''
            this.state = ParserState.TEXT
          }
          break

        case ParserState.IN_TAG:
          if (char === '<') {
            this.buffer = '<'
            this.state = ParserState.TAG_CLOSE
          } else {
            this.tagContent += char
          }
          break

        case ParserState.TAG_CLOSE:
          this.buffer += char
          if (char === '>') {
            // 关闭标签结束，检查是否匹配当前标签
            const closingTag = this.extractCloseTagName(this.buffer)
            if (closingTag === this.currentTag) {
              // 标签完整，发射事件
              events.push({
                type: this.currentTag.toLowerCase(),
                payload: this.tagContent.trim()
              })
            } else if (this.currentTag) {
              // 关闭标签不匹配，把内容和 buffer 都输出
              cleanText += this.tagContent + this.buffer
            } else {
              // 没有当前标签，直接输出
              cleanText += this.buffer
            }
            this.currentTag = null
            this.tagContent = ''
            this.buffer = ''
            this.state = ParserState.TEXT
          } else if (char === '<') {
            // 新的 '<' 开始，之前的 buffer 不是有效关闭标签
            if (this.currentTag) {
              this.tagContent += this.buffer.slice(0, -1)
            } else {
              cleanText += this.buffer.slice(0, -1)
            }
            this.buffer = '<'
          } else if (!/[a-zA-Z\/]/.test(char)) {
            // 不是有效的关闭标签字符
            if (this.currentTag) {
              this.tagContent += this.buffer
              this.state = ParserState.IN_TAG
            } else {
              cleanText += this.buffer
              this.state = ParserState.TEXT
            }
            this.buffer = ''
          }
          break
      }
    }

    return { cleanText, events }
  }

  /**
   * 提取开标签名
   * @param {string} buffer - 例如 '<PreKnowledge>'
   * @returns {string|null}
   */
  extractOpenTagName(buffer) {
    const match = buffer.match(/^<([a-zA-Z]+)>$/)
    return match ? match[1] : null
  }

  /**
   * 提取关闭标签名
   * @param {string} buffer - 例如 '</PreKnowledge>'
   * @returns {string|null}
   */
  extractCloseTagName(buffer) {
    const match = buffer.match(/^<\/([a-zA-Z]+)>$/)
    return match ? match[1] : null
  }

  /**
   * 检查是否是已知标签
   * @param {string} tagName
   * @returns {boolean}
   */
  isKnownTag(tagName) {
    return KNOWN_TAGS.includes(tagName)
  }

  /**
   * 重置解析器状态
   */
  reset() {
    this.state = ParserState.TEXT
    this.buffer = ''
    this.currentTag = null
    this.tagContent = ''
  }

  /**
   * 获取未完成的缓冲内容（用于流结束时处理）
   * @returns {string}
   */
  flush() {
    let remaining = ''
    if (this.buffer) {
      remaining += this.buffer
    }
    if (this.currentTag && this.tagContent) {
      // 标签未关闭，输出原始内容
      remaining = `<${this.currentTag}>${this.tagContent}` + remaining
    }
    this.reset()
    return remaining
  }
}

export default PreKnowledgeTagParser
