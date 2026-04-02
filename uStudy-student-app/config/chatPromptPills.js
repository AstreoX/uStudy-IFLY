export const CHAT_PROMPT_PAGE_KEYS = {
  SPACE_CHAT: 'spaceChat',
  QUICK_CHAT: 'quickChat'
}

export const CHAT_PROMPT_PILL_ACTIONS = {
  SEND: 'send',
  FILL: 'fill'
}

export const CHAT_PROMPT_PILLS = [
  {
    id: 'save-note',
    label: '保存为笔记',
    icon: '/static/icons/lucide/notebook-pen.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.SEND,
    promptText: '为我保存为一份笔记，挂载到合适的知识结点下',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT]
  },
  {
    id: 'create-artifact',
    label: '创建交互式演示',
    icon: '/static/icons/lucide/messages-square.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.SEND,
    promptText: '为我创建一份直观的交互式演示',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT]
  },
  {
    id: 'create-image',
    label: '创建图片',
    icon: '/static/icons/lucide/image.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.FILL,
    promptText: '为我创建一幅图片，关于',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT]
  },
  {
    id: 'agent-sandbox',
    label: 'Agent沙盒',
    icon: '/static/icons/lucide/square-terminal.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.SEND,
    promptText: '为我使用代码沙盒来讲解',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT, CHAT_PROMPT_PAGE_KEYS.QUICK_CHAT]
  },
  {
    id: 'create-test',
    label: '创建测试',
    icon: '/static/icons/lucide/list-checks.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.SEND,
    promptText: '为我创建一份测试',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT]
  },
  {
    id: 'calendar-schedule',
    label: '日历日程',
    icon: '/static/icons/lucide/calendar-plus.svg',
    actionType: CHAT_PROMPT_PILL_ACTIONS.SEND,
    promptText: '为我安排相关日程到系统日历中',
    supportedPages: [CHAT_PROMPT_PAGE_KEYS.SPACE_CHAT, CHAT_PROMPT_PAGE_KEYS.QUICK_CHAT]
  }
]

export function getChatPromptPills(pageKey) {
  return CHAT_PROMPT_PILLS.filter((pill) => pill.supportedPages.includes(pageKey))
}
