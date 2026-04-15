"""整卷评估服务"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from agents.llm import OpenRouterClient
from agents.llm.full_quiz_evaluation_prompts import build_full_quiz_evaluation_prompt
from config import get_settings
from quiz.evaluator import evaluate_short_answer

logger = logging.getLogger(__name__)

# AI 评估参数常量
AI_EVALUATION_TEMPERATURE = 0.4  # 较低温度保证评估一致性
AI_EVALUATION_MAX_TOKENS = 2048  # 足够生成详细分析

# 分数配置常量
SINGLE_CHOICE_MAX_SCORE = 2
MULTIPLE_CHOICE_MAX_SCORE = 4
MULTIPLE_CHOICE_PARTIAL_SCORE = 2
TRUE_FALSE_MAX_SCORE = 2
SHORT_ANSWER_MAX_SCORE = 10


# ============ 调试信息数据类 ============


@dataclass
class DebugStep:
    """评估步骤调试信息"""

    step_number: int
    step_name: str  # "逐题评分" | "简答题AI评估" | "整卷综合评估" | "掌握分更新"
    status: Literal["success", "failed", "skipped"]
    duration_ms: int
    details: list[str] = field(default_factory=list)
    metadata: dict[str, Any] | None = None


@dataclass
class EvaluationDebugInfo:
    """评估调试信息"""

    steps: list[DebugStep] = field(default_factory=list)
    model_name: str = ""
    total_duration_ms: int = 0


@dataclass
class ObjectiveQuestionResult:
    """客观题评分结果"""

    score: int
    max_score: int
    status: str  # "correct" | "wrong" | "partial"


def evaluate_single_choice(
    user_answer: dict | None, correct_answer: dict
) -> ObjectiveQuestionResult:
    """
    单选题评分：对2分，错0分

    答案格式: {"index": int}
    """
    max_score = SINGLE_CHOICE_MAX_SCORE
    if not user_answer:
        return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")

    if user_answer.get("index") == correct_answer.get("index"):
        return ObjectiveQuestionResult(
            score=SINGLE_CHOICE_MAX_SCORE, max_score=max_score, status="correct"
        )
    return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")


def evaluate_multiple_choice(
    user_answer: dict | None, correct_answer: dict
) -> ObjectiveQuestionResult:
    """
    多选题评分：全对4分，选不全2分，选错0分

    答案格式: {"indices": [int, ...]}
    """
    max_score = MULTIPLE_CHOICE_MAX_SCORE
    if not user_answer:
        return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")

    correct_set = set(correct_answer.get("indices", []))
    user_set = set(user_answer.get("indices", []))

    if not user_set:
        return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")

    if user_set == correct_set:
        return ObjectiveQuestionResult(
            score=MULTIPLE_CHOICE_MAX_SCORE, max_score=max_score, status="correct"
        )

    # 选不全：用户选的是正确答案的子集
    if user_set.issubset(correct_set):
        return ObjectiveQuestionResult(
            score=MULTIPLE_CHOICE_PARTIAL_SCORE, max_score=max_score, status="partial"
        )

    # 选错：包含错误选项
    return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")


def evaluate_true_false(
    user_answer: dict | None, correct_answer: dict
) -> ObjectiveQuestionResult:
    """
    判断题评分：对2分，错0分

    答案格式: {"value": bool}
    """
    max_score = TRUE_FALSE_MAX_SCORE
    if user_answer is None:
        return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")

    if user_answer.get("value") == correct_answer.get("value"):
        return ObjectiveQuestionResult(
            score=TRUE_FALSE_MAX_SCORE, max_score=max_score, status="correct"
        )
    return ObjectiveQuestionResult(score=0, max_score=max_score, status="wrong")


@dataclass
class QuestionEvaluationResult:
    """单题评估结果"""

    question_id: UUID
    order: int
    question_type: str
    question_stem: str
    options: list[str] | None
    correct_answer: dict
    user_answer: dict | None
    score: int
    max_score: int
    status: str  # "correct" | "wrong" | "partial"
    ai_evaluation: str | None  # 简答题 AI 评语


@dataclass
class FullQuizEvaluationResult:
    """整卷评估结果"""

    quiz_id: UUID
    score: int
    total_score: int
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    question_results: list[QuestionEvaluationResult]
    debug_info: EvaluationDebugInfo | None = None


def _extract_json_from_response(response: str) -> dict:
    """
    从 AI 响应中提取 JSON

    尝试多种方式解析 JSON：
    1. 直接解析整个响应
    2. 提取 ```json ... ``` 代码块
    3. 提取 { ... } 部分
    """
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    json_block_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取 { ... } 部分
    brace_match = re.search(r"\{.*\}", response, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # 解析失败，返回默认值
    logger.warning("Failed to parse AI response as JSON: %s", response[:200])
    return {
        "strengths": ["综合评估解析失败"],
        "weaknesses": ["综合评估解析失败"],
        "suggestions": ["请重新提交测试"],
    }


class QuizEvaluationService:
    """整卷评估服务"""

    def __init__(
        self,
        space_id: UUID | None = None,
    ) -> None:
        """
        初始化评估服务

        Args:
            space_id: 学习空间 ID（可选，用于掌握分更新）
        """
        self.space_id = space_id

    async def evaluate_quiz(
        self,
        quiz_id: UUID,
        quiz_topic: str,
        difficulty_level: str,
        questions: list[dict],
        user_answers: dict[str, Any],
    ) -> FullQuizEvaluationResult:
        """
        评估整卷，返回完整结果

        Args:
            quiz_id: 测试 ID
            quiz_topic: 测试主题
            difficulty_level: 难度级别
            questions: 题目列表，每项包含:
                - id: UUID
                - question_type: str
                - question_stem: str
                - options: list[str] | None
                - correct_answer: dict
                - order_index: int
            user_answers: 用户答案映射 {question_id: answer}

        Returns:
            FullQuizEvaluationResult
        """
        # 初始化调试信息
        debug_info = EvaluationDebugInfo()
        overall_start_time = time.time()

        # 获取模型名称
        try:
            client = OpenRouterClient(model_override=get_settings().quiz_evaluation_model or None)
            debug_info.model_name = client.model
        except Exception:
            debug_info.model_name = "unknown"

        question_results: list[QuestionEvaluationResult] = []
        total_score = 0
        actual_score = 0

        # 1. 逐题评分
        step1_start = time.time()
        step1_details: list[str] = []
        short_answer_ai_details: list[str] = []
        short_answer_duration_ms = 0

        for q in questions:
            question_id = q["id"]
            question_type = q["question_type"]
            user_answer = user_answers.get(str(question_id))
            order = q["order_index"] + 1

            q_start = time.time()
            result = await self._evaluate_single_question(
                question_id=question_id,
                question_type=question_type,
                question_stem=q["question_stem"],
                options=q.get("options"),
                correct_answer=q["correct_answer"],
                user_answer=user_answer,
                order=order,
            )
            q_duration = int((time.time() - q_start) * 1000)

            question_results.append(result)
            total_score += result.max_score
            actual_score += result.score

            # 记录逐题评分详情
            type_names = {
                "single_choice": "单选题",
                "multiple_choice": "多选题",
                "true_false": "判断题",
                "short_answer": "简答题",
            }
            type_name = type_names.get(question_type, question_type)
            status_names = {"correct": "正确", "wrong": "错误", "partial": "部分正确"}
            status_name = status_names.get(result.status, result.status)

            if question_type == "short_answer":
                short_answer_duration_ms += q_duration
                short_answer_ai_details.append(
                    f"→ Q{order} {type_name}: {status_name} (+{result.score}分) [AI评估 {q_duration}ms]"
                )
            else:
                step1_details.append(
                    f"→ Q{order} {type_name}: {status_name} (+{result.score}分)"
                )

        step1_duration = int((time.time() - step1_start) * 1000) - short_answer_duration_ms

        # 添加逐题评分步骤
        debug_info.steps.append(
            DebugStep(
                step_number=1,
                step_name="逐题评分",
                status="success",
                duration_ms=step1_duration,
                details=step1_details,
            )
        )

        # 添加简答题AI评估步骤（如有）
        if short_answer_ai_details:
            debug_info.steps.append(
                DebugStep(
                    step_number=2,
                    step_name="简答题AI评估",
                    status="success",
                    duration_ms=short_answer_duration_ms,
                    details=short_answer_ai_details,
                    metadata={"model": debug_info.model_name},
                )
            )

        # 2. 并行执行：整卷综合评估 + 掌握分更新
        evaluation_data, parallel_debug = await self._run_parallel_evaluation(
            quiz_topic=quiz_topic,
            difficulty_level=difficulty_level,
            total_score=total_score,
            actual_score=actual_score,
            question_results=question_results,
            model_name=debug_info.model_name,
        )

        # 合并并行评估的调试信息
        debug_info.steps.extend(parallel_debug)

        # 计算总耗时
        debug_info.total_duration_ms = int((time.time() - overall_start_time) * 1000)

        return FullQuizEvaluationResult(
            quiz_id=quiz_id,
            score=actual_score,
            total_score=total_score,
            strengths=evaluation_data.get("strengths", []),
            weaknesses=evaluation_data.get("weaknesses", []),
            suggestions=evaluation_data.get("suggestions", []),
            question_results=question_results,
            debug_info=debug_info,
        )

    async def _evaluate_single_question(
        self,
        question_id: UUID,
        question_type: str,
        question_stem: str,
        options: list[str] | None,
        correct_answer: dict,
        user_answer: dict | None,
        order: int,
    ) -> QuestionEvaluationResult:
        """评估单道题目"""
        ai_evaluation = None

        if question_type == "single_choice":
            obj_result = evaluate_single_choice(user_answer, correct_answer)
            score = obj_result.score
            max_score = obj_result.max_score
            status = obj_result.status

        elif question_type == "multiple_choice":
            obj_result = evaluate_multiple_choice(user_answer, correct_answer)
            score = obj_result.score
            max_score = obj_result.max_score
            status = obj_result.status

        elif question_type == "true_false":
            obj_result = evaluate_true_false(user_answer, correct_answer)
            score = obj_result.score
            max_score = obj_result.max_score
            status = obj_result.status

        elif question_type == "short_answer":
            # 简答题使用 AI 评估
            max_score = SHORT_ANSWER_MAX_SCORE
            reference_answer = correct_answer.get("reference", "") or correct_answer.get("text", "")
            user_text = user_answer.get("text", "") if user_answer else ""

            eval_result = await evaluate_short_answer(
                question_stem=question_stem,
                reference_answer=reference_answer,
                user_answer=user_text,
                max_score=max_score,
            )

            score = eval_result.score
            ai_evaluation = eval_result.ai_evaluation
            # 简答题状态：满分correct，0分wrong，其他partial
            if score == max_score:
                status = "correct"
            elif score == 0:
                status = "wrong"
            else:
                status = "partial"

        else:
            # 未知题型，默认 0 分
            score = 0
            max_score = 0
            status = "wrong"

        return QuestionEvaluationResult(
            question_id=question_id,
            order=order,
            question_type=question_type,
            question_stem=question_stem,
            options=options,
            correct_answer=correct_answer,
            user_answer=user_answer,
            score=score,
            max_score=max_score,
            status=status,
            ai_evaluation=ai_evaluation,
        )

    async def _run_parallel_evaluation(
        self,
        quiz_topic: str,
        difficulty_level: str,
        total_score: int,
        actual_score: int,
        question_results: list[QuestionEvaluationResult],
        model_name: str = "",
    ) -> tuple[dict, list[DebugStep]]:
        """
        并行执行整卷评估和掌握分更新

        Args:
            quiz_topic: 测试主题
            difficulty_level: 难度级别
            total_score: 总分
            actual_score: 实际得分
            question_results: 逐题评估结果
            model_name: 模型名称（用于调试信息）

        Returns:
            (整卷评估结果 dict, 调试步骤列表)
        """
        debug_steps: list[DebugStep] = []

        # 构建题目结果数据（供两个任务使用）
        results_for_prompt = [
            {
                "order": r.order,
                "question_type": r.question_type,
                "question_stem": r.question_stem,
                "options": r.options,
                "correct_answer": r.correct_answer,
                "user_answer": r.user_answer,
                "score": r.score,
                "max_score": r.max_score,
                "status": r.status,
                "ai_evaluation": r.ai_evaluation,
            }
            for r in question_results
        ]

        # 创建任务列表和计时信息
        tasks = []
        task_names = []

        # 任务 1: 整卷综合评估（必须执行）
        tasks.append(
            self._get_full_quiz_evaluation_with_timing(
                quiz_topic=quiz_topic,
                difficulty_level=difficulty_level,
                total_score=total_score,
                actual_score=actual_score,
                results_for_prompt=results_for_prompt,
            )
        )
        task_names.append("full_evaluation")

        # 任务 2: 掌握分更新（可选，需要 space_id）
        if self.space_id is not None:
            tasks.append(
                self._update_mastery_with_timing(
                    quiz_topic=quiz_topic,
                    results_for_prompt=results_for_prompt,
                )
            )
            task_names.append("mastery_update")

        # 并行执行所有任务，return_exceptions=True 确保一个失败不影响另一个
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理整卷评估结果（第一个任务）
        eval_result_tuple = results[0]
        if isinstance(eval_result_tuple, Exception):
            logger.error("Full quiz evaluation failed: %s", eval_result_tuple)
            evaluation_result = {
                "strengths": ["AI 综合评估服务暂时不可用"],
                "weaknesses": ["无法生成详细分析"],
                "suggestions": ["请查看上方逐题评估结果，或稍后重试"],
            }
            debug_steps.append(
                DebugStep(
                    step_number=3,
                    step_name="整卷综合评估",
                    status="failed",
                    duration_ms=0,
                    details=[f"→ 错误: {str(eval_result_tuple)}"],
                    metadata={"model": model_name},
                )
            )
        else:
            evaluation_result, eval_duration = eval_result_tuple
            strengths_count = len(evaluation_result.get("strengths", []))
            weaknesses_count = len(evaluation_result.get("weaknesses", []))
            suggestions_count = len(evaluation_result.get("suggestions", []))
            debug_steps.append(
                DebugStep(
                    step_number=3,
                    step_name="整卷综合评估",
                    status="success",
                    duration_ms=eval_duration,
                    details=[
                        f"→ 模型: {model_name}",
                        f"→ 耗时: {eval_duration / 1000:.1f}s",
                        f"→ 生成: 优点{strengths_count}条、缺点{weaknesses_count}条、建议{suggestions_count}条",
                    ],
                    metadata={"model": model_name},
                )
            )

        # 处理掌握分更新结果（第二个任务，如果存在）
        if len(results) > 1:
            mastery_result_tuple = results[1]
            if isinstance(mastery_result_tuple, Exception):
                logger.error("Mastery update failed: %s", mastery_result_tuple)
                debug_steps.append(
                    DebugStep(
                        step_number=4,
                        step_name="掌握分更新",
                        status="failed",
                        duration_ms=0,
                        details=[f"→ 错误: {str(mastery_result_tuple)}"],
                    )
                )
            else:
                mastery_result, mastery_duration = mastery_result_tuple
                logger.info(
                    "Mastery update completed: %d success, %d failed",
                    mastery_result.success_count,
                    mastery_result.failure_count,
                )
                total_nodes = mastery_result.success_count + mastery_result.failure_count
                debug_steps.append(
                    DebugStep(
                        step_number=4,
                        step_name="掌握分更新",
                        status="success" if mastery_result.failure_count == 0 else "partial",
                        duration_ms=mastery_duration,
                        details=[
                            f"→ 更新节点: {total_nodes}个",
                            f"→ 成功: {mastery_result.success_count}, 失败: {mastery_result.failure_count}",
                        ],
                    )
                )
        else:
            # 没有 space_id，跳过掌握分更新
            debug_steps.append(
                DebugStep(
                    step_number=4,
                    step_name="掌握分更新",
                    status="skipped",
                    duration_ms=0,
                    details=["→ 跳过: 未关联学习空间"],
                )
            )

        return evaluation_result, debug_steps

    async def _get_full_quiz_evaluation_with_timing(
        self,
        quiz_topic: str,
        difficulty_level: str,
        total_score: int,
        actual_score: int,
        results_for_prompt: list[dict],
    ) -> tuple[dict, int]:
        """带计时的整卷综合评估"""
        start_time = time.time()
        result = await self._get_full_quiz_evaluation(
            quiz_topic=quiz_topic,
            difficulty_level=difficulty_level,
            total_score=total_score,
            actual_score=actual_score,
            results_for_prompt=results_for_prompt,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        return result, duration_ms

    async def _update_mastery_with_timing(
        self,
        quiz_topic: str,
        results_for_prompt: list[dict],
    ):
        """带计时的掌握分更新"""
        start_time = time.time()
        result = await self._update_mastery(
            quiz_topic=quiz_topic,
            results_for_prompt=results_for_prompt,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        return result, duration_ms

    async def _update_mastery(
        self,
        quiz_topic: str,
        results_for_prompt: list[dict],
    ):
        """
        调用掌握分更新 Agent

        Agent 使用独立的数据库会话，可以安全地与其他任务并行执行。

        Args:
            quiz_topic: 测试主题
            results_for_prompt: 答题结果数据

        Returns:
            MasteryUpdateResult
        """
        from agents.mastery_update_agent import MasteryUpdateAgent

        agent = MasteryUpdateAgent(space_id=self.space_id)
        return await agent.update_mastery(
            quiz_topic=quiz_topic,
            question_results=results_for_prompt,
        )

    async def _get_full_quiz_evaluation(
        self,
        quiz_topic: str,
        difficulty_level: str,
        total_score: int,
        actual_score: int,
        results_for_prompt: list[dict],
    ) -> dict:
        """调用 AI 进行整卷综合评估"""
        messages = build_full_quiz_evaluation_prompt(
            quiz_topic=quiz_topic,
            difficulty_level=difficulty_level,
            total_score=total_score,
            actual_score=actual_score,
            question_results=results_for_prompt,
        )

        try:
            client = OpenRouterClient(model_override=get_settings().quiz_evaluation_model or None)
            response = await client.complete(
                messages=messages,
                temperature=AI_EVALUATION_TEMPERATURE,
                max_tokens=AI_EVALUATION_MAX_TOKENS,
            )
            return _extract_json_from_response(response)
        except Exception as e:
            logger.error("AI evaluation service failed: %s", e)
            # AI 服务失败时返回默认评估结果，确保用户仍能看到分数
            return {
                "strengths": ["AI 综合评估服务暂时不可用"],
                "weaknesses": ["无法生成详细分析"],
                "suggestions": ["请查看上方逐题评估结果，或稍后重试"],
            }
