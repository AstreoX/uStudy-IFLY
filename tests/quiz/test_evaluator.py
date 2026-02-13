"""简答题评估器测试"""

import asyncio
import pytest

from quiz.evaluator import (
    ShortAnswerEvaluationResult,
    evaluate_short_answer,
    extract_score_from_evaluation,
)


class TestExtractScore:
    """分数提取函数测试"""

    def test_extract_score_normal(self):
        """正常情况：提取最后一个 {分数}"""
        response = """
### 关键知识点分析
1. 知识点A
2. 知识点B

### 用户答案评估
- 正确提到了A
- 遗漏了B

### 评分理由
部分正确

### 最终得分
{6}
"""
        assert extract_score_from_evaluation(response) == 6

    def test_extract_score_multiple_braces(self):
        """多个大括号时取最后一个"""
        response = "前面提到了 {3} 个知识点... 最终得分 {8}"
        assert extract_score_from_evaluation(response) == 8

    def test_extract_score_out_of_range(self):
        """分数超出范围时截断"""
        response = "最终得分 {15}"
        assert extract_score_from_evaluation(response, max_score=10) == 10

        response = "最终得分 {-5}"
        # 负数不会匹配 \d+，返回 0
        assert extract_score_from_evaluation(response) == 0

    def test_extract_score_no_match(self):
        """没有匹配时返回 0"""
        response = "这是一个没有分数的响应"
        assert extract_score_from_evaluation(response) == 0

    def test_extract_score_zero(self):
        """分数为 0 的情况"""
        response = "完全错误，最终得分 {0}"
        assert extract_score_from_evaluation(response) == 0


@pytest.mark.integration
class TestEvaluateShortAnswer:
    """简答题评估集成测试（需要 LLM API）"""

    @pytest.mark.asyncio
    async def test_evaluate_short_answer_basic(self):
        """基本评估测试"""
        result = await evaluate_short_answer(
            question_stem="什么是面向对象编程的三大特性？",
            reference_answer="面向对象编程的三大特性是：1. 封装：将数据和操作数据的方法绑定在一起，隐藏内部实现细节。2. 继承：子类可以继承父类的属性和方法，实现代码复用。3. 多态：同一操作作用于不同对象可以有不同的表现形式。",
            user_answer="面向对象有封装、继承、多态三个特性。封装就是把数据藏起来，继承是子类继承父类，多态是一个方法有多种实现。",
        )

        assert isinstance(result, ShortAnswerEvaluationResult)
        assert 0 <= result.score <= 10
        assert result.max_score == 10
        assert len(result.ai_evaluation) > 0
        print(f"\n评估结果：{result.score}/{result.max_score}")
        print(f"AI 评语：\n{result.ai_evaluation}")

    @pytest.mark.asyncio
    async def test_evaluate_short_answer_empty(self):
        """空答案测试"""
        result = await evaluate_short_answer(
            question_stem="什么是递归？",
            reference_answer="递归是指函数直接或间接调用自身的编程技术。",
            user_answer="",
        )

        assert isinstance(result, ShortAnswerEvaluationResult)
        assert result.score == 0  # 空答案应该得 0 分
        print(f"\n空答案评估结果：{result.score}/{result.max_score}")

    @pytest.mark.asyncio
    async def test_evaluate_short_answer_concurrent(self):
        """并发评估测试"""
        questions = [
            {
                "stem": "什么是变量？",
                "ref": "变量是存储数据的容器，可以在程序运行过程中改变其值。",
                "user": "变量就是用来存东西的。",
            },
            {
                "stem": "什么是函数？",
                "ref": "函数是一段可重复使用的代码块，用于执行特定任务。",
                "user": "函数是可以重复调用的代码。",
            },
        ]

        results = await asyncio.gather(
            *[
                evaluate_short_answer(
                    question_stem=q["stem"],
                    reference_answer=q["ref"],
                    user_answer=q["user"],
                )
                for q in questions
            ]
        )

        assert len(results) == 2
        for i, result in enumerate(results):
            assert isinstance(result, ShortAnswerEvaluationResult)
            print(f"\n题目 {i + 1} 评估结果：{result.score}/{result.max_score}")


if __name__ == "__main__":
    # 运行单元测试
    pytest.main([__file__, "-v", "-m", "not integration"])
