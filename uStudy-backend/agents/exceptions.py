"""Agent 模块异常定义"""


class AgentError(Exception):
    """Agent 基础异常"""

    pass


class LLMClientError(AgentError):
    """LLM API 调用失败"""

    pass


class LLMParsingError(AgentError):
    """LLM 输出解析失败"""

    pass


class LLMParsingErrorWithOutput(LLMParsingError):
    """带有 LLM 原始输出的解析错误（用于调试）"""

    def __init__(self, message: str, llm_output: str) -> None:
        super().__init__(message)
        self.llm_output = llm_output


class TaskNotFoundError(AgentError):
    """任务不存在"""

    pass


class SpaceNotFoundError(AgentError):
    """学习空间不存在"""

    pass


class SpaceAccessDeniedError(AgentError):
    """学习空间访问被拒绝（不属于当前用户）"""

    pass
