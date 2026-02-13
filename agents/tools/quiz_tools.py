"""测试题生成工具定义和执行器"""

from dataclasses import dataclass
from typing import Any

from db.models import QuestionType


@dataclass
class CreatedQuestion:
    """已创建的题目数据"""

    question_type: QuestionType
    question_stem: str
    options: list[str] | None
    correct_answer: Any


# ============ 工具定义（OpenAI Function Calling 格式）============


QUIZ_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_single_choice_question",
            "description": "创建一道单选题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_stem": {
                        "type": "string",
                        "description": "题目题干",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "选项列表（4个选项）",
                        "minItems": 2,
                        "maxItems": 6,
                    },
                    "correct_answer_index": {
                        "type": "integer",
                        "description": "正确答案的索引（从0开始）",
                        "minimum": 0,
                    },
                },
                "required": ["question_stem", "options", "correct_answer_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_multiple_choice_question",
            "description": "创建一道多选题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_stem": {
                        "type": "string",
                        "description": "题目题干",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "选项列表（4-6个选项）",
                        "minItems": 2,
                        "maxItems": 6,
                    },
                    "correct_answer_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "所有正确答案的索引列表（从0开始）",
                        "minItems": 2,
                    },
                },
                "required": ["question_stem", "options", "correct_answer_indices"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_true_false_question",
            "description": "创建一道判断题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_stem": {
                        "type": "string",
                        "description": "题目题干（陈述句）",
                    },
                    "correct_answer": {
                        "type": "boolean",
                        "description": "正确答案（true=正确，false=错误）",
                    },
                },
                "required": ["question_stem", "correct_answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_short_answer_question",
            "description": "创建一道简答题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_stem": {
                        "type": "string",
                        "description": "题目题干",
                    },
                    "reference_answer": {
                        "type": "string",
                        "description": "参考答案",
                    },
                },
                "required": ["question_stem", "reference_answer"],
            },
        },
    },
]


class QuizToolExecutor:
    """测试题工具执行器"""

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> CreatedQuestion:
        """
        执行工具调用并返回创建的题目数据

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            CreatedQuestion 数据对象

        Raises:
            ValueError: 未知的工具名称
        """
        if tool_name == "create_single_choice_question":
            return self._create_single_choice(arguments)
        elif tool_name == "create_multiple_choice_question":
            return self._create_multiple_choice(arguments)
        elif tool_name == "create_true_false_question":
            return self._create_true_false(arguments)
        elif tool_name == "create_short_answer_question":
            return self._create_short_answer(arguments)
        else:
            raise ValueError(f"未知的工具名称: {tool_name}")

    def _create_single_choice(self, args: dict[str, Any]) -> CreatedQuestion:
        """创建单选题"""
        options = args.get("options", [])
        index = args.get("correct_answer_index", 0)

        # 验证参数
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError("选项列表必须至少有2个选项")
        if not isinstance(index, int) or index < 0 or index >= len(options):
            raise ValueError(f"答案索引 {index} 超出选项范围 [0, {len(options) - 1}]")

        return CreatedQuestion(
            question_type=QuestionType.SINGLE_CHOICE,
            question_stem=args.get("question_stem", ""),
            options=options,
            correct_answer={"index": index},
        )

    def _create_multiple_choice(self, args: dict[str, Any]) -> CreatedQuestion:
        """创建多选题"""
        options = args.get("options", [])
        indices = args.get("correct_answer_indices", [])

        # 验证参数
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError("选项列表必须至少有2个选项")
        if not isinstance(indices, list) or len(indices) < 2:
            raise ValueError("多选题答案必须至少有2个正确选项")
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(options):
                raise ValueError(f"答案索引 {idx} 超出选项范围 [0, {len(options) - 1}]")

        return CreatedQuestion(
            question_type=QuestionType.MULTIPLE_CHOICE,
            question_stem=args.get("question_stem", ""),
            options=options,
            correct_answer={"indices": sorted(indices)},
        )

    def _create_true_false(self, args: dict[str, Any]) -> CreatedQuestion:
        """创建判断题"""
        answer = args.get("correct_answer")

        # 验证参数
        if not isinstance(answer, bool):
            raise ValueError("判断题答案必须是布尔值")

        return CreatedQuestion(
            question_type=QuestionType.TRUE_FALSE,
            question_stem=args.get("question_stem", ""),
            options=None,
            correct_answer={"value": answer},
        )

    def _create_short_answer(self, args: dict[str, Any]) -> CreatedQuestion:
        """创建简答题"""
        reference = args.get("reference_answer", "")

        # 验证参数
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("简答题必须提供参考答案")

        return CreatedQuestion(
            question_type=QuestionType.SHORT_ANSWER,
            question_stem=args.get("question_stem", ""),
            options=None,
            correct_answer={"reference": reference},
        )
