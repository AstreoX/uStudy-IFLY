"""Review Quiz Planner Agent

根据复习事项智能规划测试题结构（题型、数量、难度、重点方向），
然后将规划结果传给 TestGenerationAgent 执行。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from agents.llm.client import OpenRouterClient
from config import get_settings

logger = logging.getLogger(__name__)

MAX_PLANNER_ITERATIONS = 10

# ── Planner Tool 定义 ──

PLANNER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "plan_review_quiz",
            "description": "输出复习测试题的生成规划，包括主题、难度、题目结构和重点方向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "测试题的综合主题描述，如 '综合复习: 线性代数基础 + 矩阵运算'",
                    },
                    "difficulty_level": {
                        "type": "string",
                        "enum": ["easy", "medium", "hard"],
                        "description": "测试题整体难度",
                    },
                    "test_struct": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_type": {
                                    "type": "string",
                                    "enum": [
                                        "single_choice",
                                        "multiple_choice",
                                        "true_false",
                                        "short_answer",
                                    ],
                                },
                                "question_num": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 10,
                                },
                            },
                            "required": ["question_type", "question_num"],
                        },
                        "description": "题目结构数组，每项指定题型和数量",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "重点考查方向列表",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "规划理由说明",
                    },
                },
                "required": [
                    "topic",
                    "difficulty_level",
                    "test_struct",
                    "focus_areas",
                    "reasoning",
                ],
            },
        },
    }
]

# ── System Prompt ──

REVIEW_PLANNER_SYSTEM_PROMPT = """你是 uStudy 复习测试规划专家。你的任务是根据用户当前到期的复习事项，智能规划一份复习测试题的结构。

## 输入信息

你将收到以下信息：
- 学习空间名称和偏好
- 到期复习事项列表（每项包含：标题、学习深度、逾期天数、第几次复习）

## 规划规则

### 题目总数
根据复习事项数量动态调整：
- 1-3 个事项：约 5 道题
- 4-6 个事项：约 8 道题
- 7 个以上：约 10 道题

### 题型比例
- 学习深度为"浅层浏览"的：多用单选题和判断题检验基础
- 学习深度为"中等理解"的：均衡分配各题型
- 学习深度为"深入掌握"的：适当加入简答题检验深度理解

### 难度等级
- 首次复习 (review_number=1)：偏简单 (easy)
- 2-4 次复习：中等 (medium)
- 5 次以上或逾期较久 (>7天)：偏难 (hard)

### 重点方向
- 基于复习事项标题提炼关键知识点
- 逾期较久的事项权重更高

## 输出要求

调用 plan_review_quiz 工具输出规划结果。只需要调用一次。
- topic: 综合概括所有复习事项的主题
- difficulty_level: 根据上述规则选择
- test_struct: 题型和数量数组
- focus_areas: 重点考查知识点列表
- reasoning: 简要说明规划理由

使用与复习事项标题相同的语言。"""


def _build_planner_prompt(
    space_name: str,
    learning_preferences: dict | None,
    review_items: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """构建 Planner 的 prompt。"""
    items_text = []
    for item in review_items:
        items_text.append(
            f"- {item['title']} | 学习深度: {item.get('study_depth', '未知')} | "
            f"逾期: {item.get('overdue_days', 0)}天 | 第{item.get('review_number', 1)}次复习"
        )

    prefs_text = ""
    if learning_preferences:
        preset = learning_preferences.get("preset_preferences", [])
        custom = learning_preferences.get("custom_preference", "")
        if preset:
            prefs_text = f"\n学习偏好: {', '.join(preset)}"
        if custom:
            prefs_text += f"\n自定义偏好: {custom}"

    user_content = (
        f"学习空间: {space_name}{prefs_text}\n\n"
        f"到期复习事项 ({len(review_items)} 项):\n"
        + "\n".join(items_text)
    )

    return [
        {"role": "system", "content": REVIEW_PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """校验并清洗 Planner 输出。"""
    valid_types = {"single_choice", "multiple_choice", "true_false", "short_answer"}
    valid_difficulties = {"easy", "medium", "hard"}

    topic = str(plan.get("topic", "复习测试"))[:500]

    difficulty = plan.get("difficulty_level", "medium")
    if difficulty not in valid_difficulties:
        difficulty = "medium"

    test_struct = plan.get("test_struct", [])
    cleaned_struct = []
    total_questions = 0
    for item in test_struct:
        q_type = item.get("question_type")
        q_num = item.get("question_num", 0)
        if q_type in valid_types and isinstance(q_num, int) and q_num >= 1:
            q_num = min(q_num, 10)
            cleaned_struct.append({"question_type": q_type, "question_num": q_num})
            total_questions += q_num

    # 总题数约束: 3-15
    if total_questions < 3 or not cleaned_struct:
        cleaned_struct = [
            {"question_type": "single_choice", "question_num": 3},
            {"question_type": "true_false", "question_num": 2},
        ]
    elif total_questions > 15:
        # 等比缩放
        ratio = 15 / total_questions
        cleaned_struct = [
            {
                "question_type": s["question_type"],
                "question_num": max(1, round(s["question_num"] * ratio)),
            }
            for s in cleaned_struct
        ]

    focus_areas = plan.get("focus_areas", [])
    if not isinstance(focus_areas, list):
        focus_areas = []
    focus_areas = [str(a)[:200] for a in focus_areas[:10]]

    reasoning = str(plan.get("reasoning", ""))[:500]

    return {
        "topic": topic,
        "difficulty_level": difficulty,
        "test_struct": cleaned_struct,
        "focus_areas": focus_areas,
        "reasoning": reasoning,
    }


class ReviewQuizPlannerAgent:
    """复习测试题规划 Agent：分析复习事项，输出测试题结构。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_client = OpenRouterClient(
            model_override=self.settings.gemini_model,
        )
        self.debug_logs: list[dict[str, Any]] = []

    async def plan(
        self,
        space_name: str,
        learning_preferences: dict | None,
        review_items: list[dict[str, Any]],
        on_progress: Callable[[list[dict]], Coroutine] | None = None,
    ) -> dict[str, Any]:
        """规划复习测试题结构。

        Args:
            space_name: 学习空间名称
            learning_preferences: 空间学习偏好
            review_items: 到期复习事项列表，每项包含 title, study_depth, overdue_days, review_number
            on_progress: 进度回调

        Returns:
            验证后的规划结果 dict:
            {topic, difficulty_level, test_struct, focus_areas, reasoning}
        """
        messages = _build_planner_prompt(space_name, learning_preferences, review_items)

        for iteration in range(MAX_PLANNER_ITERATIONS):
            self.debug_logs.append({
                "iteration": iteration + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "calling_llm",
            })

            if on_progress:
                await on_progress(self.debug_logs)

            try:
                result = await self.llm_client.complete_with_tools(
                    messages=messages,
                    tools=PLANNER_TOOLS,
                    temperature=0.7,
                    max_tokens=2048,
                )
            except Exception as e:
                self.debug_logs[-1]["status"] = "error"
                self.debug_logs[-1]["error"] = str(e)
                logger.error(f"ReviewQuizPlanner LLM call failed: {e}")
                # 降级为默认规划
                return _get_fallback_plan(review_items)

            # 提取 plan_review_quiz tool call
            for tool_call in result.tool_calls:
                if tool_call.name == "plan_review_quiz":
                    raw_plan = tool_call.arguments
                    validated = _validate_plan(raw_plan)

                    self.debug_logs[-1].update({
                        "status": "completed",
                        "raw_plan": raw_plan,
                        "validated_plan": validated,
                    })

                    if on_progress:
                        await on_progress(self.debug_logs)

                    logger.info(
                        f"ReviewQuizPlanner: topic={validated['topic']}, "
                        f"difficulty={validated['difficulty_level']}, "
                        f"struct={validated['test_struct']}"
                    )
                    return validated

            # LLM 没有调用 tool，追加消息请求重试
            if result.finish_reason == "stop":
                messages.append({"role": "assistant", "content": result.content or ""})
                messages.append({
                    "role": "user",
                    "content": "请使用 plan_review_quiz 工具输出你的规划结果。",
                })

            self.debug_logs[-1]["status"] = "retry"

        # 迭代用尽，降级
        logger.warning("ReviewQuizPlanner exhausted iterations, using fallback")
        return _get_fallback_plan(review_items)


def _get_fallback_plan(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    """降级：生成默认的测试题规划。"""
    count = len(review_items)
    if count <= 3:
        struct = [
            {"question_type": "single_choice", "question_num": 3},
            {"question_type": "true_false", "question_num": 2},
        ]
    elif count <= 6:
        struct = [
            {"question_type": "single_choice", "question_num": 4},
            {"question_type": "multiple_choice", "question_num": 2},
            {"question_type": "true_false", "question_num": 2},
        ]
    else:
        struct = [
            {"question_type": "single_choice", "question_num": 4},
            {"question_type": "multiple_choice", "question_num": 2},
            {"question_type": "true_false", "question_num": 2},
            {"question_type": "short_answer", "question_num": 1},
        ]

    titles = [item.get("title", "") for item in review_items[:5]]
    topic = "综合复习: " + ", ".join(titles)

    return {
        "topic": topic[:500],
        "difficulty_level": "medium",
        "test_struct": struct,
        "focus_areas": titles,
        "reasoning": "默认规划（Planner 降级）",
    }
