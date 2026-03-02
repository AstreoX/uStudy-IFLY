<template>
  <view class="header-bar">
    <!-- Left: slot for title -->
    <view class="header-left">
      <slot name="left"></slot>
    </view>

    <!-- Center: quote -->
    <view class="quote-section">
      <text class="quote-icon">&#10078;</text>
      <text class="quote-text">{{ quote }}</text>
      <text v-if="author" class="quote-author">&mdash; {{ author }}</text>
    </view>

    <!-- Right: slot for actions -->
    <view class="header-right">
      <slot name="right"></slot>
    </view>
  </view>
</template>

<script>
const LOCAL_QUOTES = [
  { text: 'The only way to do great work is to love what you do.', author: 'Steve Jobs' },
  { text: '学而不思则罔，思而不学则殆。', author: '孔子' },
  { text: 'Stay hungry, stay foolish.', author: 'Steve Jobs' },
  { text: '千里之行，始于足下。', author: '老子' },
  { text: 'Education is not the filling of a pail, but the lighting of a fire.', author: 'W.B. Yeats' },
  { text: '博学之，审问之，慎思之，明辨之，笃行之。', author: '《中庸》' },
  { text: 'The mind is not a vessel to be filled, but a fire to be kindled.', author: 'Plutarch' },
  { text: '知之者不如好之者，好之者不如乐之者。', author: '孔子' },
  { text: 'Live as if you were to die tomorrow. Learn as if you were to live forever.', author: 'Mahatma Gandhi' },
  { text: '读书破万卷，下笔如有神。', author: '杜甫' },
  { text: 'An investment in knowledge pays the best interest.', author: 'Benjamin Franklin' },
  { text: '路漫漫其修远兮，吾将上下而求索。', author: '屈原' },
  { text: 'The beautiful thing about learning is that nobody can take it away from you.', author: 'B.B. King' },
  { text: '业精于勤，荒于嬉；行成于思，毁于随。', author: '韩愈' },
  { text: 'Tell me and I forget. Teach me and I remember. Involve me and I learn.', author: 'Benjamin Franklin' }
]

export default {
  data() {
    return {
      quote: '',
      author: ''
    }
  },
  mounted() {
    this.fetchQuote()
  },
  methods: {
    fetchQuote() {
      uni.request({
        url: 'https://v1.hitokoto.cn/?c=k&encode=json',
        timeout: 2000,
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.hitokoto) {
            this.quote = res.data.hitokoto
            this.author = res.data.from || ''
          } else {
            this.useLocalQuote()
          }
        },
        fail: () => {
          this.useLocalQuote()
        }
      })
    },
    useLocalQuote() {
      const now = new Date()
      const start = new Date(now.getFullYear(), 0, 0)
      const dayOfYear = Math.floor((now - start) / 86400000)
      const entry = LOCAL_QUOTES[dayOfYear % LOCAL_QUOTES.length]
      this.quote = entry.text
      this.author = entry.author
    }
  }
}
</script>

<style scoped>
.header-bar {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
  margin: 0 28px;
  padding: 14px 20px;
  background: var(--color-widget-bg);
  border: 1px solid var(--color-widget-border);
  border-radius: 14px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  flex-shrink: 0;
}

.header-left {
  flex-shrink: 0;
}

.quote-section {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  min-width: 0;
  border-left: 2px solid var(--color-accent-blue);
  padding-left: 14px;
}

.quote-icon {
  font-size: 18px;
  color: rgba(59, 130, 246, 0.4);
  flex-shrink: 0;
  line-height: 1;
}

.quote-text {
  font-size: 15px;
  font-style: italic;
  color: rgba(255, 255, 255, 0.65);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.quote-author {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
  white-space: nowrap;
}

.header-right {
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
}
</style>
