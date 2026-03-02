"""Prompt templates for learning path auto-expansion."""

LEARNING_PATH_PRINCIPLES = """
- **短路径原则**：单次路径不超过 5 个知识点，仅规划"临近学习内容"。
- **结构优先参考**：通常优先参考某节点子树的后序遍历路径（先基础后整合），再结合用户情况进行微调。
- **动态调整**：根据用户掌握情况灵活规划，已掌握的节点可跳过。
- **连续性**：新扩展的路径必须从当前路径的末尾节点开始，保证路径的连续性。
""".strip()


def build_path_expansion_system_prompt(
    knowledge_tree_text: str,
    learning_path_text: str,
    last_path_node: str,
    uncovered_nodes_text: str,
    preferences_text: str,
) -> str:
    """Build the system prompt for learning path expansion.

    Args:
        knowledge_tree_text: Formatted knowledge tree from build_knowledge_tree_text()
        learning_path_text: Current learning path from build_learning_path_chain()
        last_path_node: Name of the last node in the current path
        uncovered_nodes_text: Formatted list of uncovered node names
        preferences_text: Formatted user learning preferences

    Returns:
        Complete system prompt string
    """
    return f"""你是一个学习路径扩展专家。你的任务是根据学生当前的学习进度和知识图谱结构，为学生规划下一阶段的学习路径。

## 当前知识图谱

{knowledge_tree_text}

格式说明：
- *数量=层级深度
- [分数]=当前掌握度(0-1 对应 0-100分)

## 当前学习路径

{learning_path_text}

## 当前路径末尾节点

**{last_path_node}**

## 未被学习路径覆盖的知识点

{uncovered_nodes_text}

{preferences_text}

## 学习路径规划原则

{LEARNING_PATH_PRINCIPLES}

## 任务

请分析当前的知识图谱和学习进度，使用 `extend_learning_path` 工具扩展学习路径。

**重要规则**：
1. `extend_learning_path` 的 `node_sequence` 参数的**第一个节点必须是当前路径的末尾节点 "{last_path_node}"**，以保证路径连续性。
2. 后续节点从未覆盖的知识点中选择，优先选择与末尾节点在知识树中相邻的节点。
3. 总共选择 3-5 个节点（含末尾衔接节点），即新增 2-4 个节点。
4. 如果工具返回错误，请根据错误信息修正后重试。"""


def format_learning_preferences(prefs: dict | None) -> str:
    """Format user learning preferences into readable text.

    Args:
        prefs: Learning preferences dict from Space.learning_preferences

    Returns:
        Formatted preferences text (empty string if no preferences)
    """
    if not prefs:
        return ""

    parts = ["## 用户学习偏好\n"]

    preset_map = {
        "university": "大学课程学习",
        "quick": "快速入门",
        "solid": "扎实掌握",
        "hobby": "兴趣爱好",
        "exam": "考试备考",
        "work": "工作技能",
        "research": "学术研究",
        "practice": "实践应用",
    }

    preset_preferences = prefs.get("preset_preferences", [])
    if preset_preferences:
        labels = [preset_map.get(p, p) for p in preset_preferences]
        parts.append(f"偏好类型：{', '.join(labels)}")

    custom = prefs.get("custom_preference")
    if custom:
        parts.append(f"自定义偏好：{custom}")

    return "\n".join(parts)


def format_uncovered_nodes(uncovered_node_names: list[str]) -> str:
    """Format uncovered node names into a readable list.

    Args:
        uncovered_node_names: List of node names not covered by learning path

    Returns:
        Formatted text listing uncovered nodes
    """
    if not uncovered_node_names:
        return "（无未覆盖节点）"

    items = [f"- {name}" for name in uncovered_node_names]
    return "\n".join(items)
