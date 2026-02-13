"""Prompt 构建函数测试"""

import pytest

from agents.llm.prompts import build_test_generation_prompt


class TestBuildTestGenerationPrompt:
    """build_test_generation_prompt 函数测试"""

    def test_topic_substitution(self):
        """主题正确替换"""
        messages = build_test_generation_prompt(
            topic="Python 基础",
            difficulty="easy",
            test_struct=[{"question_type": "single_choice", "question_num": 3}],
        )

        system_content = messages[0]["content"]
        user_content = messages[1]["content"]

        assert "Python 基础" in system_content
        assert "Python 基础" in user_content

    def test_difficulty_substitution(self):
        """难度正确替换"""
        messages = build_test_generation_prompt(
            topic="测试主题",
            difficulty="hard",
            test_struct=[{"question_type": "single_choice", "question_num": 3}],
        )

        system_content = messages[0]["content"]
        user_content = messages[1]["content"]

        assert "hard" in system_content
        assert "hard" in user_content

    def test_test_struct_formatting(self):
        """题目结构格式化"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 3},
            {"question_type": "multiple_choice", "question_num": 2},
        ]

        messages = build_test_generation_prompt(
            topic="测试主题",
            difficulty="medium",
            test_struct=test_struct,
        )

        system_content = messages[0]["content"]

        # 验证题目结构被格式化
        assert "single_choice: 3道" in system_content
        assert "multiple_choice: 2道" in system_content

    def test_chinese_topic(self):
        """中文主题"""
        messages = build_test_generation_prompt(
            topic="数据结构与算法",
            difficulty="medium",
            test_struct=[{"question_type": "single_choice", "question_num": 5}],
        )

        system_content = messages[0]["content"]
        user_content = messages[1]["content"]

        assert "数据结构与算法" in system_content
        assert "数据结构与算法" in user_content

    def test_english_topic(self):
        """英文主题"""
        messages = build_test_generation_prompt(
            topic="Machine Learning Fundamentals",
            difficulty="hard",
            test_struct=[{"question_type": "short_answer", "question_num": 2}],
        )

        system_content = messages[0]["content"]
        user_content = messages[1]["content"]

        assert "Machine Learning Fundamentals" in system_content
        assert "Machine Learning Fundamentals" in user_content

    def test_multiple_question_types(self):
        """多种题型组合"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 3},
            {"question_type": "multiple_choice", "question_num": 2},
            {"question_type": "true_false", "question_num": 4},
            {"question_type": "short_answer", "question_num": 1},
        ]

        messages = build_test_generation_prompt(
            topic="综合测试",
            difficulty="medium",
            test_struct=test_struct,
        )

        system_content = messages[0]["content"]

        assert "single_choice: 3道" in system_content
        assert "multiple_choice: 2道" in system_content
        assert "true_false: 4道" in system_content
        assert "short_answer: 1道" in system_content

    def test_returns_two_messages(self):
        """返回两条消息（system 和 user）"""
        messages = build_test_generation_prompt(
            topic="测试",
            difficulty="easy",
            test_struct=[{"question_type": "single_choice", "question_num": 1}],
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_all_difficulty_levels(self):
        """所有难度级别"""
        for difficulty in ["easy", "medium", "hard"]:
            messages = build_test_generation_prompt(
                topic="测试",
                difficulty=difficulty,
                test_struct=[{"question_type": "single_choice", "question_num": 1}],
            )

            system_content = messages[0]["content"]
            assert difficulty in system_content

    def test_empty_test_struct(self):
        """空 test_struct"""
        messages = build_test_generation_prompt(
            topic="测试",
            difficulty="easy",
            test_struct=[],
        )

        # 应该正常工作，不抛出异常
        assert len(messages) == 2

    def test_single_question_type(self):
        """单一题型"""
        messages = build_test_generation_prompt(
            topic="Python 函数",
            difficulty="medium",
            test_struct=[{"question_type": "true_false", "question_num": 5}],
        )

        system_content = messages[0]["content"]
        assert "true_false: 5道" in system_content

    def test_special_characters_in_topic(self):
        """主题包含特殊字符"""
        topic = "C++ & C# 编程: 基础 <入门>"
        messages = build_test_generation_prompt(
            topic=topic,
            difficulty="easy",
            test_struct=[{"question_type": "single_choice", "question_num": 2}],
        )

        system_content = messages[0]["content"]
        user_content = messages[1]["content"]

        assert topic in system_content
        assert topic in user_content

    def test_long_topic(self):
        """长主题"""
        topic = "这是一个非常长的主题名称，" * 20
        messages = build_test_generation_prompt(
            topic=topic,
            difficulty="medium",
            test_struct=[{"question_type": "single_choice", "question_num": 1}],
        )

        system_content = messages[0]["content"]
        assert topic in system_content

    def test_large_question_num(self):
        """大数量题目"""
        test_struct = [{"question_type": "single_choice", "question_num": 100}]

        messages = build_test_generation_prompt(
            topic="测试",
            difficulty="easy",
            test_struct=test_struct,
        )

        system_content = messages[0]["content"]
        assert "single_choice: 100道" in system_content

    def test_system_prompt_contains_instructions(self):
        """系统提示包含必要的指令"""
        messages = build_test_generation_prompt(
            topic="测试",
            difficulty="medium",
            test_struct=[{"question_type": "single_choice", "question_num": 1}],
        )

        system_content = messages[0]["content"]

        # 验证包含关键指令
        assert "测试题生成专家" in system_content or "Test_Generation_Agent" in system_content
        assert "easy" in system_content  # 难度说明
        assert "medium" in system_content  # 中等难度
        assert "hard" in system_content  # 高难度

    def test_system_prompt_contains_tool_names(self):
        """系统提示包含工具名称"""
        messages = build_test_generation_prompt(
            topic="测试",
            difficulty="easy",
            test_struct=[{"question_type": "single_choice", "question_num": 1}],
        )

        system_content = messages[0]["content"]

        # 验证包含工具名称
        assert "create_single_choice_question" in system_content
        assert "create_multiple_choice_question" in system_content
        assert "create_true_false_question" in system_content
        assert "create_short_answer_question" in system_content
