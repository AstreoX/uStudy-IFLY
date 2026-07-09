"""jieba 中文分词工具（用于全文检索）"""

import re

import jieba


def segment_for_search(text: str) -> str:
    """jieba 搜索模式分词，返回空格分隔的 token 串。

    使用 cut_for_search 模式（细粒度），适合全文检索场景。
    """
    tokens = jieba.cut_for_search(text)
    filtered = [t.strip() for t in tokens if t.strip() and not re.match(r"^[\W]+$", t)]
    return " ".join(filtered)


def build_tsquery(query: str) -> str:
    """将查询文本分词后构建 tsquery 格式（OR 连接以提高召回）。

    过滤单字符 token 以减少噪声。
    """
    segmented = segment_for_search(query)
    tokens = [t for t in segmented.split() if len(t) > 1]
    if not tokens:
        # fallback：保留所有 token
        return segmented.replace(" ", " | ") if segmented.strip() else ""
    return " | ".join(tokens)
