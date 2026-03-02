\pset border 2
\pset format aligned

-- =============================================
--       uStudy 数据统计面板 (完整版)
--       运行: docker exec -i ustudy-db psql -U postgres -d ustudy < stats.sql
-- =============================================

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 1. 用户总览
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 1. 用户总览 ===' AS "---";
SELECT
  COUNT(*)                                                         AS "总注册用户",
  COUNT(CASE WHEN subscription_tier::text = 'ALPHA' THEN 1 END)   AS "Alpha",
  COUNT(CASE WHEN subscription_tier::text = 'FREE' THEN 1 END)    AS "Free",
  COUNT(CASE WHEN subscription_tier::text = 'BASIC' THEN 1 END)   AS "Basic",
  COUNT(CASE WHEN subscription_tier::text = 'PREMIUM' THEN 1 END) AS "Premium",
  MIN(created_at)::date                                            AS "最早注册",
  MAX(created_at)::date                                            AS "最近注册"
FROM users;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 2. 每日新增用户 (近14天)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 2. 每日新增用户 (近14天) ===' AS "---";
SELECT
  created_at::date AS "日期",
  COUNT(*)         AS "新增用户"
FROM users
WHERE created_at >= NOW() - INTERVAL '14 days'
GROUP BY created_at::date
ORDER BY "日期" DESC;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 3. 学习空间统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 3. 学习空间统计 ===' AS "---";
SELECT
  COUNT(*)                     AS "总空间数",
  COUNT(DISTINCT user_id)      AS "创建过空间的用户",
  ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT user_id), 0), 1) AS "人均空间数",
  ROUND(100.0 * COUNT(DISTINCT user_id) / NULLIF((SELECT COUNT(*) FROM users), 0), 1) AS "空间创建率%"
FROM spaces;

-- 每用户空间数分布
SELECT '=== 3b. 每用户空间数分布 ===' AS "---";
SELECT
  space_count AS "空间数",
  COUNT(*)    AS "用户数"
FROM (
  SELECT user_id, COUNT(*) AS space_count
  FROM spaces GROUP BY user_id
) t
GROUP BY space_count
ORDER BY space_count;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 4. 对话统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 4. 对话统计 ===' AS "---";
SELECT
  COUNT(*)                                                  AS "总对话数",
  COUNT(CASE WHEN space_id IS NOT NULL THEN 1 END)          AS "空间对话",
  COUNT(CASE WHEN space_id IS NULL THEN 1 END)              AS "快速对话",
  COUNT(DISTINCT user_id)                                   AS "发起过对话的用户",
  ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT user_id), 0), 1) AS "人均对话数"
FROM conversations;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 5. 消息统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 5. 消息统计 ===' AS "---";
SELECT
  COUNT(*)                                                   AS "总消息数",
  COUNT(CASE WHEN role::text = 'USER' THEN 1 END)           AS "用户消息",
  COUNT(CASE WHEN role::text = 'ASSISTANT' THEN 1 END)      AS "AI回复",
  ROUND(COUNT(*)::numeric / NULLIF((SELECT COUNT(*) FROM conversations), 0), 1) AS "平均每对话消息数"
FROM messages;

-- 附件统计
SELECT '=== 5b. 附件统计 ===' AS "---";
SELECT
  COUNT(*)                                                   AS "总附件数",
  COUNT(CASE WHEN attachment_type::text = 'image' THEN 1 END) AS "图片",
  COUNT(CASE WHEN attachment_type::text = 'file' THEN 1 END)  AS "文件",
  COUNT(DISTINCT user_id)                                    AS "上传过附件的用户"
FROM message_attachments;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 6. 每日活跃 (近14天)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 6. 每日活跃 (近14天) ===' AS "---";
SELECT
  m.created_at::date          AS "日期",
  COUNT(DISTINCT c.user_id)   AS "DAU",
  COUNT(DISTINCT c.id)        AS "活跃对话数",
  COUNT(*)                    AS "消息数",
  COUNT(CASE WHEN m.role::text = 'USER' THEN 1 END) AS "用户消息"
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
WHERE m.created_at >= NOW() - INTERVAL '14 days'
GROUP BY m.created_at::date
ORDER BY "日期" DESC;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 7. 留存概览
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 7. 留存概览 ===' AS "---";
SELECT
  (SELECT COUNT(*) FROM users) AS "总用户",
  (SELECT COUNT(DISTINCT c.user_id)
   FROM conversations c
   JOIN messages m ON m.conversation_id = c.id
   WHERE m.created_at >= NOW() - INTERVAL '1 day') AS "今日活跃",
  (SELECT COUNT(DISTINCT c.user_id)
   FROM conversations c
   JOIN messages m ON m.conversation_id = c.id
   WHERE m.created_at >= NOW() - INTERVAL '3 days') AS "近3天活跃",
  (SELECT COUNT(DISTINCT c.user_id)
   FROM conversations c
   JOIN messages m ON m.conversation_id = c.id
   WHERE m.created_at >= NOW() - INTERVAL '7 days') AS "近7天活跃",
  (SELECT COUNT(*)
   FROM users u
   WHERE NOT EXISTS (
     SELECT 1 FROM conversations c WHERE c.user_id = u.id
   )) AS "注册未使用";

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 8. 用户活跃排行 TOP 15
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 8. 用户活跃排行 TOP15 ===' AS "---";
SELECT
  u.nickname                   AS "昵称",
  u.email                      AS "邮箱",
  COUNT(DISTINCT c.id)         AS "对话数",
  COUNT(m.id)                  AS "消息数",
  (SELECT COUNT(*) FROM spaces s WHERE s.user_id = u.id) AS "空间数",
  MAX(m.created_at)::timestamp(0) AS "最后活跃",
  u.created_at::date           AS "注册日期"
FROM users u
LEFT JOIN conversations c ON c.user_id = u.id
LEFT JOIN messages m ON m.conversation_id = c.id
GROUP BY u.id, u.nickname, u.email, u.created_at
ORDER BY COUNT(m.id) DESC
LIMIT 15;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 9. 用户学习空间明细
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 9. 用户学习空间明细 ===' AS "---";
SELECT
  u.nickname                    AS "用户",
  u.email                       AS "邮箱",
  s.name                        AS "学习空间",
  s.created_at::date            AS "创建日期",
  COUNT(c.id)                   AS "对话数",
  COALESCE(SUM(msg.cnt), 0)     AS "消息数"
FROM users u
LEFT JOIN spaces s ON s.user_id = u.id
LEFT JOIN conversations c ON c.space_id = s.id
LEFT JOIN (
  SELECT conversation_id, COUNT(*) AS cnt
  FROM messages GROUP BY conversation_id
) msg ON msg.conversation_id = c.id
GROUP BY u.id, u.nickname, u.email, s.id, s.name, s.created_at
ORDER BY u.nickname, s.created_at;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 10. 知识图谱统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 10. 知识图谱统计 ===' AS "---";
SELECT
  COUNT(DISTINCT n.space_id) AS "有图谱的空间",
  COUNT(n.id)                AS "总节点数",
  (SELECT COUNT(*) FROM edges) AS "总边数",
  ROUND(COUNT(n.id)::numeric / NULLIF(COUNT(DISTINCT n.space_id), 0), 1) AS "平均每空间节点数"
FROM nodes n;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 11. 测试题统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 11. 测试题统计 ===' AS "---";
SELECT
  (SELECT COUNT(*) FROM quizzes) AS "总测试数",
  (SELECT COUNT(*) FROM questions) AS "总题目数",
  COUNT(*) AS "总作答次数",
  COUNT(DISTINCT user_id) AS "参与过测试的用户",
  ROUND(AVG(score::numeric / NULLIF(total_score, 0) * 100), 1) AS "平均正确率%"
FROM quiz_attempts;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 12. 知识库 (RAG) 统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 12. 知识库统计 ===' AS "---";
SELECT
  COUNT(DISTINCT sd.id)                                              AS "总文档数",
  COUNT(DISTINCT sd.space_id)                                        AS "使用知识库的空间",
  SUM(CASE WHEN dpt.status::text = 'completed' THEN 1 ELSE 0 END)   AS "处理完成",
  SUM(CASE WHEN dpt.status::text = 'pending' THEN 1 ELSE 0 END)     AS "待处理",
  SUM(CASE WHEN dpt.status::text = 'failed' THEN 1 ELSE 0 END)      AS "处理失败",
  (SELECT COUNT(*) FROM document_chunks)                             AS "总切片数"
FROM space_documents sd
LEFT JOIN document_processing_tasks dpt ON dpt.document_id = sd.id;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 13. 记忆系统统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 13. 记忆系统统计 ===' AS "---";
SELECT
  (SELECT COUNT(*) FROM long_term_memories)                          AS "长期记忆(用户数)",
  (SELECT COUNT(*) FROM space_memories)                              AS "空间记忆数",
  (SELECT COUNT(*) FROM vector_memories)                             AS "向量记忆总数",
  (SELECT COUNT(DISTINCT user_id) FROM vector_memories)              AS "有向量记忆的用户",
  (SELECT COUNT(*) FROM vector_memories WHERE memory_type::text = 'long_term') AS "向量-长期",
  (SELECT COUNT(*) FROM vector_memories WHERE memory_type::text = 'space')     AS "向量-空间";

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 14. API 用量统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 14. API 用量总览 ===' AS "---";
SELECT
  COUNT(*)                      AS "总请求数",
  SUM(total_tokens)             AS "总Token数",
  SUM(prompt_tokens)            AS "Prompt Tokens",
  SUM(completion_tokens)        AS "Completion Tokens",
  ROUND(SUM(estimated_cost_cents) / 100.0, 2) AS "预估费用($)"
FROM api_usage_logs;

-- 按类型+模型分
SELECT '=== 14b. API 用量按类型 ===' AS "---";
SELECT
  usage_type::text              AS "类型",
  model                         AS "模型",
  COUNT(*)                      AS "请求数",
  SUM(total_tokens)             AS "Token数",
  ROUND(SUM(estimated_cost_cents) / 100.0, 2) AS "费用($)"
FROM api_usage_logs
GROUP BY usage_type, model
ORDER BY SUM(total_tokens) DESC;

-- 近7天每日用量
SELECT '=== 14c. 近7天每日API用量 ===' AS "---";
SELECT
  created_at::date              AS "日期",
  COUNT(*)                      AS "请求数",
  SUM(total_tokens)             AS "Token数",
  ROUND(SUM(estimated_cost_cents) / 100.0, 2) AS "费用($)"
FROM api_usage_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY created_at::date
ORDER BY "日期" DESC;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 15. 用户反馈统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 15. 用户反馈统计 ===' AS "---";
SELECT
  COUNT(*)                      AS "总反馈数",
  COUNT(DISTINCT user_id)       AS "反馈过的用户",
  COUNT(CASE WHEN chat_mode::text = 'space_chat' THEN 1 END) AS "空间对话反馈",
  COUNT(CASE WHEN chat_mode::text = 'quick_chat' THEN 1 END) AS "快速对话反馈",
  MIN(created_at)::date         AS "最早反馈",
  MAX(created_at)::date         AS "最近反馈"
FROM feedbacks;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 16. 激活码统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 16. 激活码统计 ===' AS "---";
SELECT
  COUNT(*)                                    AS "总激活码数",
  COUNT(CASE WHEN used_by IS NOT NULL THEN 1 END) AS "已使用",
  COUNT(CASE WHEN used_by IS NULL THEN 1 END)     AS "未使用",
  ROUND(100.0 * COUNT(CASE WHEN used_by IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS "使用率%"
FROM activation_codes;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 17. Agent 任务统计
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECT '=== 17. Agent 任务统计 ===' AS "---";
SELECT
  task_type::text                              AS "任务类型",
  COUNT(*)                                     AS "总数",
  COUNT(CASE WHEN status::text = 'done' THEN 1 END)    AS "完成",
  COUNT(CASE WHEN status::text = 'failed' THEN 1 END)  AS "失败",
  COUNT(CASE WHEN status::text = 'running' THEN 1 END) AS "运行中",
  COUNT(CASE WHEN status::text = 'pending' THEN 1 END) AS "待处理"
FROM agent_tasks
GROUP BY task_type;
