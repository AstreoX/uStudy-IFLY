"""Agent 测试专用 fixtures"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DifficultyLevel, Quiz, QuestionType, Space, User

# 示例 LLM 响应：有效的知识图谱
VALID_LLM_RESPONSE = """
Here is the knowledge graph for Python basics:

<knowledge_graph>
/basic_knowledge_tree
* Python 基础 [0.8]
** 变量与数据类型 [0.9]
*** 字符串操作 [0.7]
*** 数字类型 [0.85]
** 控制流程 [0.6]
*** 条件判断 [0.7]
*** 循环结构 [0.5]
* 函数与模块 [0.4]
** 函数定义 [0.5]
** 模块导入 [0.3]

/advanced_knowledge_connections
变量与数据类型->函数定义
控制流程->函数定义
字符串操作->模块导入
</knowledge_graph>

This knowledge graph covers the basics of Python programming.
"""

# 简单的 LLM 响应：最小有效结构
SIMPLE_LLM_RESPONSE = """
<knowledge_graph>
/basic_knowledge_tree
* Topic A [0.5]
** Sub A1 [0.3]
** Sub A2 [0.7]

/advanced_knowledge_connections
Sub A1->Sub A2
</knowledge_graph>
"""

# 无高级连接的响应
NO_ADVANCED_CONNECTIONS_RESPONSE = """
<knowledge_graph>
/basic_knowledge_tree
* Root [0.5]
** Child 1 [0.3]
** Child 2 [0.7]
</knowledge_graph>
"""

# 多层级树结构响应
MULTI_LEVEL_RESPONSE = """
<knowledge_graph>
/basic_knowledge_tree
* Level 1 [0.8]
** Level 2A [0.7]
*** Level 3A [0.6]
**** Level 4A [0.5]
** Level 2B [0.4]
*** Level 3B [0.3]

/advanced_knowledge_connections
Level 3A->Level 3B
Level 4A->Level 2B
</knowledge_graph>
"""

# 带未知掌握度 (-1) 的响应
UNKNOWN_MASTERY_RESPONSE = """
<knowledge_graph>
/basic_knowledge_tree
* Topic [-1]
** Known [0.5]
** Unknown [-1]

/advanced_knowledge_connections
</knowledge_graph>
"""

# 边界掌握度值的响应
BOUNDARY_MASTERY_RESPONSE = """
<knowledge_graph>
/basic_knowledge_tree
* Zero [0]
** Full [1]
** Over [1.5]

/advanced_knowledge_connections
</knowledge_graph>
"""


@pytest.fixture
def valid_llm_response() -> str:
    """有效的 LLM 响应"""
    return VALID_LLM_RESPONSE


@pytest.fixture
def simple_llm_response() -> str:
    """简单的 LLM 响应"""
    return SIMPLE_LLM_RESPONSE


@pytest.fixture
def no_advanced_connections_response() -> str:
    """无高级连接的响应"""
    return NO_ADVANCED_CONNECTIONS_RESPONSE


@pytest.fixture
def multi_level_response() -> str:
    """多层级树结构响应"""
    return MULTI_LEVEL_RESPONSE


@pytest.fixture
def unknown_mastery_response() -> str:
    """带未知掌握度的响应"""
    return UNKNOWN_MASTERY_RESPONSE


@pytest.fixture
def boundary_mastery_response() -> str:
    """边界掌握度值的响应"""
    return BOUNDARY_MASTERY_RESPONSE


# 无效响应数据
INVALID_RESPONSES = {
    "empty": "",
    "no_tags": "some random text without knowledge_graph tags",
    "malformed_tags": "<knowledge_graph>content without closing tag",
    "missing_tree_section": """
<knowledge_graph>
/advanced_knowledge_connections
A->B
</knowledge_graph>
""",
    "empty_tree": """
<knowledge_graph>
/basic_knowledge_tree

/advanced_knowledge_connections
</knowledge_graph>
""",
}


@pytest.fixture(params=list(INVALID_RESPONSES.keys()))
def invalid_response(request) -> tuple[str, str]:
    """参数化的无效响应 (key, response)"""
    key = request.param
    return key, INVALID_RESPONSES[key]


# ============ Quiz 测试专用 Fixtures ============


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """创建测试用户"""
    user = User(
        id=uuid4(),
        email="quiz_test@test.com",
        nickname="Quiz Test User",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_space(db_session: AsyncSession, test_user: User) -> Space:
    """创建测试学习空间"""
    space = Space(
        id=uuid4(),
        user_id=test_user.id,
        name="Quiz Test Space",
        color="#FF5500",
    )
    db_session.add(space)
    await db_session.commit()
    return space


@pytest_asyncio.fixture
async def test_quiz(db_session: AsyncSession, test_space: Space) -> Quiz:
    """创建测试用 Quiz 记录"""
    quiz = Quiz(
        id=uuid4(),
        space_id=test_space.id,
        title="Python 基础测试",
        topic="Python 编程",
        difficulty=DifficultyLevel.MEDIUM,
        total_questions=0,
    )
    db_session.add(quiz)
    await db_session.commit()
    return quiz


@pytest.fixture
def sample_test_struct() -> list[dict[str, Any]]:
    """样例 test_struct"""
    return [
        {"question_type": "single_choice", "question_num": 3},
        {"question_type": "multiple_choice", "question_num": 2},
        {"question_type": "true_false", "question_num": 2},
    ]


@pytest.fixture
def sample_test_struct_with_short_answer() -> list[dict[str, Any]]:
    """包含简答题的样例 test_struct"""
    return [
        {"question_type": "single_choice", "question_num": 2},
        {"question_type": "short_answer", "question_num": 1},
    ]


# ============ Mock LLM 响应 Fixtures ============


@dataclass
class MockToolCall:
    """模拟工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class MockLLMResult:
    """模拟 LLM 返回结果"""
    content: str | None
    tool_calls: list[MockToolCall] | None
    finish_reason: str


@pytest.fixture
def mock_llm_single_tool_response() -> MockLLMResult:
    """Mock: LLM 返回单个工具调用"""
    return MockLLMResult(
        content=None,
        tool_calls=[
            MockToolCall(
                id="call_1",
                name="create_single_choice_question",
                arguments={
                    "question_stem": "Python 中哪个关键字用于定义函数？",
                    "options": ["def", "func", "function", "define"],
                    "correct_answer_index": 0,
                },
            )
        ],
        finish_reason="tool_calls",
    )


@pytest.fixture
def mock_llm_multiple_tools_response() -> MockLLMResult:
    """Mock: LLM 返回多个工具调用"""
    return MockLLMResult(
        content=None,
        tool_calls=[
            MockToolCall(
                id="call_1",
                name="create_single_choice_question",
                arguments={
                    "question_stem": "Python 中哪个关键字用于定义函数？",
                    "options": ["def", "func", "function", "define"],
                    "correct_answer_index": 0,
                },
            ),
            MockToolCall(
                id="call_2",
                name="create_true_false_question",
                arguments={
                    "question_stem": "Python 是一种解释型语言。",
                    "correct_answer": True,
                },
            ),
            MockToolCall(
                id="call_3",
                name="create_multiple_choice_question",
                arguments={
                    "question_stem": "以下哪些是 Python 的内置数据类型？",
                    "options": ["int", "str", "list", "array", "dict"],
                    "correct_answer_indices": [0, 1, 2, 4],
                },
            ),
        ],
        finish_reason="tool_calls",
    )


@pytest.fixture
def mock_llm_stop_early_response() -> MockLLMResult:
    """Mock: LLM 提前停止 (finish_reason=stop)"""
    return MockLLMResult(
        content="我已经完成了所有题目的生成。",
        tool_calls=None,
        finish_reason="stop",
    )


@pytest.fixture
def mock_llm_no_tools_response() -> MockLLMResult:
    """Mock: LLM 不调用工具"""
    return MockLLMResult(
        content="让我为您生成测试题...",
        tool_calls=[],
        finish_reason="tool_calls",
    )


@pytest.fixture
def mock_llm_short_answer_response() -> MockLLMResult:
    """Mock: LLM 返回简答题工具调用"""
    return MockLLMResult(
        content=None,
        tool_calls=[
            MockToolCall(
                id="call_1",
                name="create_short_answer_question",
                arguments={
                    "question_stem": "请简述 Python 中列表和元组的主要区别。",
                    "reference_answer": "列表是可变的，元组是不可变的。列表使用方括号[]，元组使用圆括号()。",
                },
            )
        ],
        finish_reason="tool_calls",
    )


def created_question_factory(
    question_type: QuestionType = QuestionType.SINGLE_CHOICE,
    question_stem: str = "测试题目",
    options: list[str] | None = None,
    correct_answer: Any = None,
):
    """CreatedQuestion 工厂函数"""
    from agents.tools.quiz_tools import CreatedQuestion

    if options is None and question_type in (
        QuestionType.SINGLE_CHOICE,
        QuestionType.MULTIPLE_CHOICE,
    ):
        options = ["选项A", "选项B", "选项C", "选项D"]

    if correct_answer is None:
        if question_type == QuestionType.SINGLE_CHOICE:
            correct_answer = {"index": 0}
        elif question_type == QuestionType.MULTIPLE_CHOICE:
            correct_answer = {"indices": [0, 1]}
        elif question_type == QuestionType.TRUE_FALSE:
            correct_answer = {"value": True}
        elif question_type == QuestionType.SHORT_ANSWER:
            correct_answer = {"reference": "参考答案"}

    return CreatedQuestion(
        question_type=question_type,
        question_stem=question_stem,
        options=options,
        correct_answer=correct_answer,
    )


@pytest.fixture
def question_factory():
    """提供 CreatedQuestion 工厂函数"""
    return created_question_factory
