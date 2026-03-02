"""QuizToolExecutor 单元测试"""

import pytest

from agents.tools.quiz_tools import CreatedQuestion, QuizToolExecutor
from db.models import QuestionType


class TestCreateSingleChoiceQuestion:
    """单选题工具测试"""

    def setup_method(self):
        """每个测试方法前创建执行器实例"""
        self.executor = QuizToolExecutor()

    def test_valid_question(self):
        """有效参数应成功创建单选题"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "Python 中哪个关键字用于定义函数？",
                "options": ["def", "func", "function", "define"],
                "correct_answer_index": 0,
            },
        )

        assert isinstance(result, CreatedQuestion)
        assert result.question_type == QuestionType.SINGLE_CHOICE
        assert result.question_stem == "Python 中哪个关键字用于定义函数？"
        assert result.options == ["def", "func", "function", "define"]
        assert result.correct_answer == {"index": 0}

    def test_minimum_options(self):
        """最少 2 个选项应成功"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "1 + 1 = ?",
                "options": ["2", "3"],
                "correct_answer_index": 0,
            },
        )

        assert len(result.options) == 2
        assert result.correct_answer == {"index": 0}

    def test_maximum_options(self):
        """最多 6 个选项应成功"""
        options = ["A", "B", "C", "D", "E", "F"]
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "选择一个选项",
                "options": options,
                "correct_answer_index": 5,
            },
        )

        assert len(result.options) == 6
        assert result.correct_answer == {"index": 5}

    def test_valid_index_boundary_zero(self):
        """索引 0 边界应成功"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "测试题",
                "options": ["A", "B", "C"],
                "correct_answer_index": 0,
            },
        )

        assert result.correct_answer == {"index": 0}

    def test_valid_index_boundary_max(self):
        """索引 n-1 边界应成功"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "测试题",
                "options": ["A", "B", "C"],
                "correct_answer_index": 2,
            },
        )

        assert result.correct_answer == {"index": 2}

    def test_invalid_index_negative(self):
        """负数索引应失败"""
        with pytest.raises(ValueError, match="答案索引.*超出选项范围"):
            self.executor.execute(
                "create_single_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C"],
                    "correct_answer_index": -1,
                },
            )

    def test_invalid_index_out_of_range(self):
        """索引超出范围应失败"""
        with pytest.raises(ValueError, match="答案索引.*超出选项范围"):
            self.executor.execute(
                "create_single_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C"],
                    "correct_answer_index": 3,
                },
            )

    def test_options_too_few(self):
        """选项数 < 2 应失败"""
        with pytest.raises(ValueError, match="选项列表必须至少有2个选项"):
            self.executor.execute(
                "create_single_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A"],
                    "correct_answer_index": 0,
                },
            )

    def test_options_empty(self):
        """空选项列表应失败"""
        with pytest.raises(ValueError, match="选项列表必须至少有2个选项"):
            self.executor.execute(
                "create_single_choice_question",
                {
                    "question_stem": "测试题",
                    "options": [],
                    "correct_answer_index": 0,
                },
            )

    def test_correct_answer_format(self):
        """验证 {"index": N} 格式"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "测试题",
                "options": ["A", "B", "C", "D"],
                "correct_answer_index": 2,
            },
        )

        assert "index" in result.correct_answer
        assert isinstance(result.correct_answer["index"], int)
        assert result.correct_answer["index"] == 2


class TestCreateMultipleChoiceQuestion:
    """多选题工具测试"""

    def setup_method(self):
        self.executor = QuizToolExecutor()

    def test_valid_question(self):
        """有效参数 (2+ 答案) 应成功"""
        result = self.executor.execute(
            "create_multiple_choice_question",
            {
                "question_stem": "以下哪些是 Python 内置类型？",
                "options": ["int", "str", "array", "list"],
                "correct_answer_indices": [0, 1, 3],
            },
        )

        assert isinstance(result, CreatedQuestion)
        assert result.question_type == QuestionType.MULTIPLE_CHOICE
        assert result.correct_answer == {"indices": [0, 1, 3]}

    def test_minimum_correct_answers(self):
        """正好 2 个答案应成功"""
        result = self.executor.execute(
            "create_multiple_choice_question",
            {
                "question_stem": "选择正确的选项",
                "options": ["A", "B", "C", "D"],
                "correct_answer_indices": [0, 2],
            },
        )

        assert len(result.correct_answer["indices"]) == 2

    def test_single_answer_fails(self):
        """仅 1 个答案应失败"""
        with pytest.raises(ValueError, match="多选题答案必须至少有2个正确选项"):
            self.executor.execute(
                "create_multiple_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer_indices": [0],
                },
            )

    def test_empty_answer_fails(self):
        """空答案列表应失败"""
        with pytest.raises(ValueError, match="多选题答案必须至少有2个正确选项"):
            self.executor.execute(
                "create_multiple_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer_indices": [],
                },
            )

    def test_indices_are_sorted(self):
        """答案索引应被排序"""
        result = self.executor.execute(
            "create_multiple_choice_question",
            {
                "question_stem": "测试题",
                "options": ["A", "B", "C", "D"],
                "correct_answer_indices": [3, 1, 0],
            },
        )

        assert result.correct_answer["indices"] == [0, 1, 3]

    def test_out_of_range_index(self):
        """超出范围索引应失败"""
        with pytest.raises(ValueError, match="答案索引.*超出选项范围"):
            self.executor.execute(
                "create_multiple_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C"],
                    "correct_answer_indices": [0, 5],
                },
            )

    def test_negative_index(self):
        """负数索引应失败"""
        with pytest.raises(ValueError, match="答案索引.*超出选项范围"):
            self.executor.execute(
                "create_multiple_choice_question",
                {
                    "question_stem": "测试题",
                    "options": ["A", "B", "C"],
                    "correct_answer_indices": [0, -1],
                },
            )

    def test_correct_answer_format(self):
        """验证 {"indices": [...]} 格式"""
        result = self.executor.execute(
            "create_multiple_choice_question",
            {
                "question_stem": "测试题",
                "options": ["A", "B", "C", "D"],
                "correct_answer_indices": [1, 3],
            },
        )

        assert "indices" in result.correct_answer
        assert isinstance(result.correct_answer["indices"], list)


class TestCreateTrueFalseQuestion:
    """判断题工具测试"""

    def setup_method(self):
        self.executor = QuizToolExecutor()

    def test_valid_true(self):
        """答案 True 应成功"""
        result = self.executor.execute(
            "create_true_false_question",
            {
                "question_stem": "Python 是解释型语言。",
                "correct_answer": True,
            },
        )

        assert isinstance(result, CreatedQuestion)
        assert result.question_type == QuestionType.TRUE_FALSE
        assert result.options is None
        assert result.correct_answer == {"value": True}

    def test_valid_false(self):
        """答案 False 应成功"""
        result = self.executor.execute(
            "create_true_false_question",
            {
                "question_stem": "Python 是编译型语言。",
                "correct_answer": False,
            },
        )

        assert result.correct_answer == {"value": False}

    def test_non_boolean_string_fails(self):
        """字符串值应失败"""
        with pytest.raises(ValueError, match="判断题答案必须是布尔值"):
            self.executor.execute(
                "create_true_false_question",
                {
                    "question_stem": "测试题",
                    "correct_answer": "true",
                },
            )

    def test_non_boolean_int_fails(self):
        """整数值应失败"""
        with pytest.raises(ValueError, match="判断题答案必须是布尔值"):
            self.executor.execute(
                "create_true_false_question",
                {
                    "question_stem": "测试题",
                    "correct_answer": 1,
                },
            )

    def test_non_boolean_none_fails(self):
        """None 值应失败"""
        with pytest.raises(ValueError, match="判断题答案必须是布尔值"):
            self.executor.execute(
                "create_true_false_question",
                {
                    "question_stem": "测试题",
                    "correct_answer": None,
                },
            )

    def test_correct_answer_format(self):
        """验证 {"value": bool} 格式"""
        result = self.executor.execute(
            "create_true_false_question",
            {
                "question_stem": "测试题",
                "correct_answer": True,
            },
        )

        assert "value" in result.correct_answer
        assert isinstance(result.correct_answer["value"], bool)


class TestCreateShortAnswerQuestion:
    """简答题工具测试"""

    def setup_method(self):
        self.executor = QuizToolExecutor()

    def test_valid_question(self):
        """有效参数应成功"""
        result = self.executor.execute(
            "create_short_answer_question",
            {
                "question_stem": "请简述 Python 的优点。",
                "reference_answer": "简洁、易读、丰富的库支持",
            },
        )

        assert isinstance(result, CreatedQuestion)
        assert result.question_type == QuestionType.SHORT_ANSWER
        assert result.options is None
        assert result.correct_answer == {"reference": "简洁、易读、丰富的库支持"}

    def test_empty_answer_fails(self):
        """空字符串应失败"""
        with pytest.raises(ValueError, match="简答题必须提供参考答案"):
            self.executor.execute(
                "create_short_answer_question",
                {
                    "question_stem": "测试题",
                    "reference_answer": "",
                },
            )

    def test_whitespace_only_fails(self):
        """仅空格应失败"""
        with pytest.raises(ValueError, match="简答题必须提供参考答案"):
            self.executor.execute(
                "create_short_answer_question",
                {
                    "question_stem": "测试题",
                    "reference_answer": "   ",
                },
            )

    def test_whitespace_with_tabs_fails(self):
        """仅制表符和空格应失败"""
        with pytest.raises(ValueError, match="简答题必须提供参考答案"):
            self.executor.execute(
                "create_short_answer_question",
                {
                    "question_stem": "测试题",
                    "reference_answer": "\t  \n",
                },
            )

    def test_correct_answer_format(self):
        """验证 {"reference": str} 格式"""
        result = self.executor.execute(
            "create_short_answer_question",
            {
                "question_stem": "测试题",
                "reference_answer": "参考答案内容",
            },
        )

        assert "reference" in result.correct_answer
        assert isinstance(result.correct_answer["reference"], str)

    def test_long_reference_answer(self):
        """长参考答案应成功"""
        long_answer = "这是一个非常长的参考答案。" * 100
        result = self.executor.execute(
            "create_short_answer_question",
            {
                "question_stem": "测试题",
                "reference_answer": long_answer,
            },
        )

        assert result.correct_answer["reference"] == long_answer


class TestQuizToolExecutor:
    """工具执行器测试"""

    def setup_method(self):
        self.executor = QuizToolExecutor()

    def test_execute_single_choice(self):
        """执行单选题工具"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "测试",
                "options": ["A", "B"],
                "correct_answer_index": 0,
            },
        )

        assert result.question_type == QuestionType.SINGLE_CHOICE

    def test_execute_multiple_choice(self):
        """执行多选题工具"""
        result = self.executor.execute(
            "create_multiple_choice_question",
            {
                "question_stem": "测试",
                "options": ["A", "B", "C"],
                "correct_answer_indices": [0, 1],
            },
        )

        assert result.question_type == QuestionType.MULTIPLE_CHOICE

    def test_execute_true_false(self):
        """执行判断题工具"""
        result = self.executor.execute(
            "create_true_false_question",
            {
                "question_stem": "测试",
                "correct_answer": True,
            },
        )

        assert result.question_type == QuestionType.TRUE_FALSE

    def test_execute_short_answer(self):
        """执行简答题工具"""
        result = self.executor.execute(
            "create_short_answer_question",
            {
                "question_stem": "测试",
                "reference_answer": "答案",
            },
        )

        assert result.question_type == QuestionType.SHORT_ANSWER

    def test_unknown_tool_raises(self):
        """未知工具名抛出 ValueError"""
        with pytest.raises(ValueError, match="未知的工具名称"):
            self.executor.execute(
                "unknown_tool",
                {"some": "args"},
            )

    def test_invalid_tool_name_variations(self):
        """不同形式的无效工具名都应失败"""
        invalid_names = [
            "create_question",
            "single_choice",
            "CREATE_SINGLE_CHOICE_QUESTION",
            "",
            "create_single_choice_question_extra",
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="未知的工具名称"):
                self.executor.execute(name, {})

    def test_missing_required_arguments(self):
        """缺少必需参数时应有合理行为"""
        # 缺少 question_stem 应使用默认空字符串
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "options": ["A", "B"],
                "correct_answer_index": 0,
            },
        )
        assert result.question_stem == ""

    def test_extra_arguments_ignored(self):
        """额外参数应被忽略"""
        result = self.executor.execute(
            "create_single_choice_question",
            {
                "question_stem": "测试",
                "options": ["A", "B"],
                "correct_answer_index": 0,
                "extra_field": "ignored",
                "another_extra": 123,
            },
        )

        assert result.question_type == QuestionType.SINGLE_CHOICE


class TestCreatedQuestionDataclass:
    """CreatedQuestion 数据类测试"""

    def test_dataclass_fields(self):
        """验证数据类字段"""
        question = CreatedQuestion(
            question_type=QuestionType.SINGLE_CHOICE,
            question_stem="题目",
            options=["A", "B"],
            correct_answer={"index": 0},
        )

        assert question.question_type == QuestionType.SINGLE_CHOICE
        assert question.question_stem == "题目"
        assert question.options == ["A", "B"]
        assert question.correct_answer == {"index": 0}

    def test_none_options_for_non_choice_questions(self):
        """判断题和简答题的 options 应为 None"""
        true_false = CreatedQuestion(
            question_type=QuestionType.TRUE_FALSE,
            question_stem="题目",
            options=None,
            correct_answer={"value": True},
        )

        short_answer = CreatedQuestion(
            question_type=QuestionType.SHORT_ANSWER,
            question_stem="题目",
            options=None,
            correct_answer={"reference": "答案"},
        )

        assert true_false.options is None
        assert short_answer.options is None
