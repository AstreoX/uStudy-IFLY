"""测试评估模块"""

__all__ = [
    "ShortAnswerEvaluationResult",
    "evaluate_short_answer",
    "extract_score_from_evaluation",
]


def __getattr__(name):
    if name in __all__:
        from quiz.evaluator import (
            ShortAnswerEvaluationResult,
            evaluate_short_answer,
            extract_score_from_evaluation,
        )

        return {
            "ShortAnswerEvaluationResult": ShortAnswerEvaluationResult,
            "evaluate_short_answer": evaluate_short_answer,
            "extract_score_from_evaluation": extract_score_from_evaluation,
        }[name]
    raise AttributeError(f"module 'quiz' has no attribute {name!r}")
