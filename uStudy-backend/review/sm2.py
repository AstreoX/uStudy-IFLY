"""SM-2 间隔重复算法

基于 SuperMemo SM-2 算法，根据复习质量动态调整复习间隔。
所有函数均为纯函数，无副作用，便于单元测试。
"""


def sm2_next_review(
    review_number: int,
    previous_ef: float,
    quality: int,
    previous_interval: int,
) -> tuple[int, float]:
    """SM-2 算法：根据复习质量计算下一次间隔和新的易度因子。

    Args:
        review_number: 当前是第几次复习 (1-based)
        previous_ef: 上一次的易度因子 (>= 1.3)
        quality: 复习质量评分 (0-5)
        previous_interval: 上一次的间隔天数

    Returns:
        (next_interval_days, new_ease_factor)
    """
    # 更新易度因子
    new_ef = max(
        1.3,
        previous_ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
    )

    # 质量不及格，重置间隔
    if quality < 3:
        return (1, new_ef)

    # 及格，按 SM-2 规则计算间隔
    if review_number == 1:
        next_interval = 1
    elif review_number == 2:
        next_interval = 6
    else:
        next_interval = round(previous_interval * new_ef)

    return (next_interval, new_ef)


def score_to_quality(score: int, total_score: int) -> int:
    """测试题得分率 → SM-2 质量评分 (0-5)。

    Args:
        score: 用户得分
        total_score: 总分

    Returns:
        SM-2 质量评分 (0-5)
    """
    if total_score <= 0:
        return 0

    pct = score / total_score * 100

    if pct >= 90:
        return 5
    if pct >= 75:
        return 4
    if pct >= 60:
        return 3
    if pct >= 40:
        return 2
    if pct >= 20:
        return 1
    return 0


def should_graduate(review_number: int, quality: int) -> bool:
    """判断是否应该毕业（停止生成新复习）。

    毕业条件：已完成 10 次以上复习，且最近一次质量评分 >= 4。

    Args:
        review_number: 当前完成的复习编号
        quality: 本次复习质量评分

    Returns:
        True 表示可以毕业，不再生成后续复习
    """
    return review_number >= 10 and quality >= 4
