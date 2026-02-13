"""Quiz Generation Tools - Tool definition and executor for generating tests"""

import logging
from typing import Any
from uuid import UUID

from agents.schemas import (
    DifficultyLevelEnum,
    QuestionTypeEnum,
    QuizGenerateRequest,
    TestStructItem,
)
from agents.service import AgentService
from chat.tools.base import ToolResult
from db.database import get_scoped_session

logger = logging.getLogger(__name__)


# ============ Quiz Generation Tool (OpenAI Function Calling Format) ============


QUIZ_GENERATION_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "generate_test",
            "description": "根据指定的主题和要求生成测试题。这是一个异步任务，调用后会返回任务 ID，题目将在后台生成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "测试题的主题或领域",
                    },
                    "difficulty_level": {
                        "type": "string",
                        "enum": ["easy", "medium", "hard"],
                        "description": "难度级别：easy=简单, medium=中等, hard=困难",
                        "default": "medium",
                    },
                    "test_struct": {
                        "type": "array",
                        "description": "题目结构配置",
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
                                    "description": "题型：single_choice=单选题, multiple_choice=多选题, true_false=判断题, short_answer=简答题",
                                },
                                "question_num": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 20,
                                    "description": "该题型的题目数量",
                                },
                            },
                            "required": ["question_type", "question_num"],
                        },
                    },
                },
                "required": ["topic", "test_struct"],
            },
        },
    },
]


# ============ Quiz Generation Tool Executor ============


class QuizGenerationToolExecutor:
    """Executor for quiz generation tools"""

    def __init__(
        self,
        user_id: UUID,
        conversation_id: UUID,
        space_id: UUID,
    ) -> None:
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a quiz generation tool and return result.
        Creates a short-lived DB session per call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM

        Returns:
            ToolResult with success status, data, and message
        """
        if tool_name != "generate_test":
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        try:
            return await self._generate_test(arguments)
        except ValueError as e:
            logger.warning(f"Invalid value: {e}")
            return ToolResult(success=False, data=None, message=f"参数错误: {e}")
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return ToolResult(success=False, data=None, message=f"执行错误: {str(e)}")

    async def _generate_test(self, args: dict) -> ToolResult:
        """Generate test by calling AgentService"""
        topic = args.get("topic", "")
        if not topic:
            return ToolResult(
                success=False, data=None, message="测试主题不能为空"
            )

        difficulty_level_str = args.get("difficulty_level", "medium")
        try:
            difficulty_level = DifficultyLevelEnum(difficulty_level_str)
        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                message=f"无效的难度级别: {difficulty_level_str}，请使用 easy/medium/hard",
            )

        test_struct_raw = args.get("test_struct", [])
        if not test_struct_raw:
            return ToolResult(
                success=False, data=None, message="题目结构配置不能为空"
            )

        # Parse test_struct
        test_struct: list[TestStructItem] = []
        for item in test_struct_raw:
            question_type_str = item.get("question_type", "")
            question_num = item.get("question_num", 0)

            try:
                question_type = QuestionTypeEnum(question_type_str)
            except ValueError:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"无效的题型: {question_type_str}",
                )

            if question_num < 1 or question_num > 20:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"题目数量必须在 1-20 之间，当前值: {question_num}",
                )

            test_struct.append(
                TestStructItem(question_type=question_type, question_num=question_num)
            )

        # Build request
        request = QuizGenerateRequest(
            topic=topic,
            difficulty_level=difficulty_level,
            test_struct=test_struct,
        )

        # Call AgentService with a short-lived session
        async with get_scoped_session() as db:
            agent_service = AgentService(db)
            task_response = await agent_service.create_quiz_task(
                user_id=self.user_id,
                space_id=self.space_id,
                request=request,
                conversation_id=self.conversation_id,
            )

        # Calculate total questions
        total_questions = sum(item.question_num for item in test_struct)

        return ToolResult(
            success=True,
            data={
                "task_id": str(task_response.task_id),
                "status": task_response.status.value,
                "topic": topic,
                "difficulty": difficulty_level.value,
                "total_questions": total_questions,
            },
            message=f"测试生成任务已启动，任务 ID: {task_response.task_id}，共 {total_questions} 道题目正在后台生成中",
        )
