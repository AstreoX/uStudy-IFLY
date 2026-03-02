"""测试题生成 Agent"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm.client import OpenRouterClient
from agents.llm.prompts import build_test_generation_prompt
from agents.tools.quiz_tools import QUIZ_TOOLS, CreatedQuestion, QuizToolExecutor
from config import get_settings
from db.models import Question, Quiz

logger = logging.getLogger(__name__)

# 最大 LLM 迭代次数，防止无限循环
# 基于每次迭代平均生成 2-3 道题目，10 次迭代足以生成 30 道题目
MAX_LLM_ITERATIONS = 40

# 单条 LLM 内容的最大长度（截断保护）
MAX_LLM_CONTENT_LENGTH = 5000


class TestGenerationAgent:
    """测试题生成 Agent"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        # 使用 Gemini 模型
        self.llm_client = OpenRouterClient(model_override=self.settings.gemini_model)
        self.tool_executor = QuizToolExecutor()
        # 调试日志收集
        self.debug_logs: list[dict[str, Any]] = []

    async def generate(
        self,
        quiz_id: UUID,
        topic: str,
        difficulty: str,
        test_struct: list[dict[str, Any]],
        on_progress: Any = None,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """
        生成测试题

        Args:
            quiz_id: Quiz 记录 ID
            topic: 测试主题
            difficulty: 难度级别
            test_struct: 题目结构配置
            on_progress: 进度回调函数，接收 debug_logs 列表

        Returns:
            (total_questions, successful_count, debug_logs) 元组

        Raises:
            Exception: 生成失败
        """
        logger.info(
            "开始生成测试题: quiz_id=%s, topic=%s, difficulty=%s",
            quiz_id,
            topic,
            difficulty,
        )

        # 清空调试日志
        self.debug_logs = []

        # 构建 prompt
        messages = build_test_generation_prompt(topic, difficulty, test_struct)

        # 计算期望的题目总数
        expected_total = sum(item.get("question_num", 0) for item in test_struct)

        # 调用 LLM 并处理工具调用
        created_questions: list[CreatedQuestion] = []

        for iteration in range(MAX_LLM_ITERATIONS):
            logger.debug("LLM 调用迭代 %d, 已创建题目数: %d", iteration, len(created_questions))

            # 在 LLM 调用前先记录"等待中"状态，让前端能立即看到进度
            waiting_log_index = len(self.debug_logs)
            self.debug_logs.append({
                "iteration": iteration + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "llm_content": "正在调用 LLM...",
                "tool_calls_count": 0,
                "progress": f"{len(created_questions)}/{expected_total}",
                "finish_reason": None,
                "status": "calling_llm",
            })

            # 立即调用回调，让前端知道正在调用 LLM
            if on_progress:
                try:
                    await on_progress(self.debug_logs)
                except Exception as cb_err:
                    logger.warning("进度回调失败（调用前）: %s", cb_err)

            try:
                result = await self.llm_client.complete_with_tools(
                    messages=messages,
                    tools=QUIZ_TOOLS,
                    temperature=0.7,
                    max_tokens=4096,
                )
            except Exception as llm_err:
                # LLM 调用失败，记录错误到调试日志
                error_msg = f"LLM 调用失败: {type(llm_err).__name__}: {str(llm_err)}"
                logger.error(error_msg)
                self.debug_logs[waiting_log_index] = {
                    "iteration": iteration + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "llm_content": error_msg,
                    "tool_calls_count": 0,
                    "progress": f"{len(created_questions)}/{expected_total}",
                    "finish_reason": "error",
                    "status": "error",
                }
                if on_progress:
                    try:
                        await on_progress(self.debug_logs)
                    except Exception:
                        pass
                raise  # 重新抛出异常，让上层处理

            # 记录调试日志（替换之前的"等待中"日志）
            llm_content = result.content
            if llm_content and len(llm_content) > MAX_LLM_CONTENT_LENGTH:
                llm_content = llm_content[:MAX_LLM_CONTENT_LENGTH] + "... [truncated]"

            self.debug_logs[waiting_log_index] = {
                "iteration": iteration + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "llm_content": llm_content,
                "tool_calls_count": len(result.tool_calls) if result.tool_calls else 0,
                "progress": f"{len(created_questions)}/{expected_total}",
                "finish_reason": result.finish_reason,
                "status": "completed",
            }

            # 调用进度回调（如果提供），用于实时更新数据库
            if on_progress:
                try:
                    await on_progress(self.debug_logs)
                except Exception as cb_err:
                    logger.warning("进度回调失败: %s", cb_err)

            # 处理工具调用
            if result.tool_calls:
                tool_results = []
                for tool_call in result.tool_calls:
                    try:
                        question = self.tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                        created_questions.append(question)

                        # 统计各题型数量，构建带进度的返回信息
                        type_counts = self._count_by_type(created_questions)
                        current_type = question.question_type.value
                        target_for_type = next(
                            (item["question_num"] for item in test_struct
                             if item["question_type"] == current_type), 0
                        )
                        current_for_type = type_counts.get(current_type, 0)

                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": f"成功创建 {current_type} 题目 ({current_for_type}/{target_for_type})。总进度: {len(created_questions)}/{expected_total}",
                        })
                        logger.debug(
                            "工具调用成功: %s, 题目: %s, 进度: %d/%d",
                            tool_call.name,
                            question.question_stem[:50],
                            len(created_questions),
                            expected_total,
                        )
                    except Exception as e:
                        logger.warning("工具调用失败: %s, error=%s", tool_call.name, e)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": f"创建失败: {str(e)}",
                        })

                # 添加 assistant 消息和工具结果到上下文
                messages.append({
                    "role": "assistant",
                    "content": result.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": str(tc.arguments),
                            },
                        }
                        for tc in result.tool_calls
                    ],
                })
                messages.extend(tool_results)

            # 检查是否完成
            if len(created_questions) >= expected_total:
                logger.info("已创建足够数量的题目: %d/%d", len(created_questions), expected_total)
                break

            # 如果没有工具调用且有内容，说明模型可能结束了
            if not result.tool_calls and result.finish_reason == "stop":
                logger.warning(
                    "LLM 停止但题目数量不足: %d/%d",
                    len(created_questions),
                    expected_total,
                )
                break

        # 持久化题目到数据库
        successful_count = await self._persist_questions(quiz_id, created_questions)

        # 更新 Quiz 的题目总数
        quiz = await self.db.get(Quiz, quiz_id)
        if quiz:
            quiz.total_questions = successful_count
            await self.db.commit()

        logger.info(
            "测试题生成完成: quiz_id=%s, 期望=%d, 成功=%d",
            quiz_id,
            expected_total,
            successful_count,
        )

        return expected_total, successful_count, self.debug_logs

    def _count_by_type(self, questions: list[CreatedQuestion]) -> dict[str, int]:
        """统计各题型已创建的数量"""
        counts: dict[str, int] = {}
        for q in questions:
            type_value = q.question_type.value
            counts[type_value] = counts.get(type_value, 0) + 1
        return counts

    async def _persist_questions(
        self,
        quiz_id: UUID,
        questions: list[CreatedQuestion],
    ) -> int:
        """
        将题目持久化到数据库

        Args:
            quiz_id: Quiz ID
            questions: 题目列表

        Returns:
            成功创建的题目数量
        """
        count = 0
        for idx, q in enumerate(questions):
            try:
                question = Question(
                    quiz_id=quiz_id,
                    question_type=q.question_type,
                    question_stem=q.question_stem,
                    options=q.options,
                    correct_answer=q.correct_answer,
                    order_index=idx,
                )
                self.db.add(question)
                count += 1
            except Exception as e:
                logger.error("题目持久化失败: idx=%d, error=%s", idx, e)

        await self.db.commit()
        return count
