"""知识图谱解析器单元测试"""

import pytest

from agents.exceptions import LLMParsingError
from agents.parsers.knowledge_graph import (
    KnowledgeGraphParser,
    ParsedEdge,
    ParsedKnowledgeGraph,
    ParsedNode,
)


class TestKnowledgeGraphParser:
    """KnowledgeGraphParser 单元测试"""

    @pytest.fixture
    def parser(self) -> KnowledgeGraphParser:
        """创建解析器实例"""
        return KnowledgeGraphParser()

    # ==================== 基础解析测试 ====================

    def test_parse_simple_tree_structure(
        self, parser: KnowledgeGraphParser, simple_llm_response: str
    ):
        """测试解析简单树形结构"""
        result = parser.parse(simple_llm_response)

        assert isinstance(result, ParsedKnowledgeGraph)
        assert len(result.nodes) == 3
        assert len(result.edges) == 3  # 2个树边 + 1个高级连接

        # 验证根节点
        root = result.nodes[0]
        assert root.label == "Topic A"
        assert root.mastery == 50
        assert root.level == 1
        assert root.parent_label is None

        # 验证子节点
        child1 = result.nodes[1]
        assert child1.label == "Sub A1"
        assert child1.mastery == 30
        assert child1.level == 2
        assert child1.parent_label == "Topic A"

    def test_parse_multi_level_tree(
        self, parser: KnowledgeGraphParser, multi_level_response: str
    ):
        """测试解析多层级树 (4层)"""
        result = parser.parse(multi_level_response)

        # 验证节点数量
        assert len(result.nodes) == 6

        # 验证层级分布
        levels = [n.level for n in result.nodes]
        assert levels == [1, 2, 3, 4, 2, 3]

        # 验证4层节点
        level4_node = next(n for n in result.nodes if n.level == 4)
        assert level4_node.label == "Level 4A"
        assert level4_node.parent_label == "Level 3A"

    def test_parse_with_mastery_values(
        self, parser: KnowledgeGraphParser, valid_llm_response: str
    ):
        """测试带掌握度值的解析"""
        result = parser.parse(valid_llm_response)

        # 验证掌握度转换 (0.8 -> 80)
        root = result.nodes[0]
        assert root.mastery == 80

        # 验证其他掌握度
        mastery_values = [n.mastery for n in result.nodes]
        assert 80 in mastery_values  # 0.8 -> 80
        assert 90 in mastery_values  # 0.9 -> 90
        assert 70 in mastery_values  # 0.7 -> 70

    def test_parse_without_mastery_values(
        self, parser: KnowledgeGraphParser, unknown_mastery_response: str
    ):
        """测试无掌握度值 (-1) 的解析"""
        result = parser.parse(unknown_mastery_response)

        # -1 应该转换为 None
        unknown_nodes = [n for n in result.nodes if n.mastery is None]
        assert len(unknown_nodes) == 2

        # 0.5 应该转换为 50
        known_node = next(n for n in result.nodes if n.label == "Known")
        assert known_node.mastery == 50

    # ==================== 高级连接测试 ====================

    def test_parse_advanced_connections(
        self, parser: KnowledgeGraphParser, simple_llm_response: str
    ):
        """测试基本高级连接解析"""
        result = parser.parse(simple_llm_response)

        # 找到高级连接边
        advanced_edges = [e for e in result.edges if e.edge_type == "advanced"]
        assert len(advanced_edges) == 1

        edge = advanced_edges[0]
        assert edge.source_label == "Sub A1"
        assert edge.target_label == "Sub A2"

    def test_parse_multiple_advanced_connections(
        self, parser: KnowledgeGraphParser, valid_llm_response: str
    ):
        """测试多个高级连接"""
        result = parser.parse(valid_llm_response)

        advanced_edges = [e for e in result.edges if e.edge_type == "advanced"]
        assert len(advanced_edges) == 3

        # 验证连接存在
        edge_pairs = [(e.source_label, e.target_label) for e in advanced_edges]
        assert ("变量与数据类型", "函数定义") in edge_pairs
        assert ("控制流程", "函数定义") in edge_pairs
        assert ("字符串操作", "模块导入") in edge_pairs

    def test_skip_invalid_node_references(self, parser: KnowledgeGraphParser):
        """测试跳过无效节点引用"""
        response = """
<knowledge_graph>
/basic_knowledge_tree
* Node A [0.5]
** Node B [0.3]

/advanced_knowledge_connections
Node A->Node B
Node A->NonExistent
NonExistent->Node B
</knowledge_graph>
"""
        result = parser.parse(response)

        # 只有有效的连接应该被保留
        advanced_edges = [e for e in result.edges if e.edge_type == "advanced"]
        assert len(advanced_edges) == 1
        assert advanced_edges[0].source_label == "Node A"
        assert advanced_edges[0].target_label == "Node B"

    def test_no_advanced_connections_section(
        self, parser: KnowledgeGraphParser, no_advanced_connections_response: str
    ):
        """测试缺少高级连接部分"""
        result = parser.parse(no_advanced_connections_response)

        # 应该只有树边
        assert all(e.edge_type == "knowledge_tree" for e in result.edges)
        assert len(result.edges) == 2  # Root->Child1, Root->Child2

    # ==================== 边界情况测试 ====================

    def test_empty_input(self, parser: KnowledgeGraphParser):
        """测试空输入"""
        with pytest.raises(LLMParsingError, match="未找到 <knowledge_graph> 标签块"):
            parser.parse("")

    def test_malformed_xml_tags(self, parser: KnowledgeGraphParser):
        """测试格式错误的标签"""
        malformed = "<knowledge_graph>content without closing"
        with pytest.raises(LLMParsingError, match="未找到 <knowledge_graph> 标签块"):
            parser.parse(malformed)

    def test_missing_knowledge_graph_tag(self, parser: KnowledgeGraphParser):
        """测试缺少标签"""
        no_tags = "some random text without any tags"
        with pytest.raises(LLMParsingError, match="未找到 <knowledge_graph> 标签块"):
            parser.parse(no_tags)

    def test_missing_tree_section(self, parser: KnowledgeGraphParser):
        """测试缺少 basic_knowledge_tree 部分"""
        missing_tree = """
<knowledge_graph>
/advanced_knowledge_connections
A->B
</knowledge_graph>
"""
        with pytest.raises(LLMParsingError, match="未找到 /basic_knowledge_tree 部分"):
            parser.parse(missing_tree)

    def test_empty_tree_section(self, parser: KnowledgeGraphParser):
        """测试空的树部分"""
        empty_tree = """
<knowledge_graph>
/basic_knowledge_tree

/advanced_knowledge_connections
</knowledge_graph>
"""
        with pytest.raises(LLMParsingError, match="未找到任何知识节点"):
            parser.parse(empty_tree)

    def test_special_characters_in_node_names(self, parser: KnowledgeGraphParser):
        """测试节点名称中的特殊字符"""
        response = """
<knowledge_graph>
/basic_knowledge_tree
* C++ 编程 [0.5]
** 指针 & 引用 [0.3]
** 模板<T> [0.4]

/advanced_knowledge_connections
</knowledge_graph>
"""
        result = parser.parse(response)

        labels = [n.label for n in result.nodes]
        assert "C++ 编程" in labels
        assert "指针 & 引用" in labels
        assert "模板<T>" in labels

    def test_unicode_chinese_content(
        self, parser: KnowledgeGraphParser, valid_llm_response: str
    ):
        """测试中文内容"""
        result = parser.parse(valid_llm_response)

        # 验证中文节点正确解析
        labels = [n.label for n in result.nodes]
        assert "Python 基础" in labels
        assert "变量与数据类型" in labels
        assert "字符串操作" in labels

    def test_mastery_out_of_range(
        self, parser: KnowledgeGraphParser, boundary_mastery_response: str
    ):
        """测试掌握度超出范围"""
        result = parser.parse(boundary_mastery_response)

        # 0 -> 0
        zero_node = next(n for n in result.nodes if n.label == "Zero")
        assert zero_node.mastery == 0

        # 1 -> 100
        full_node = next(n for n in result.nodes if n.label == "Full")
        assert full_node.mastery == 100

        # 1.5 -> 应该被限制在 100
        over_node = next(n for n in result.nodes if n.label == "Over")
        assert over_node.mastery == 100

    # ==================== 性能测试 ====================

    def test_large_tree_50_nodes(self, parser: KnowledgeGraphParser):
        """测试大型树结构 (50个节点)"""
        # 生成大型树
        lines = ["* Root [0.5]"]
        for i in range(49):
            level = (i % 3) + 2  # 2-4 层交替
            asterisks = "*" * level
            lines.append(f"{asterisks} Node_{i} [{i / 100}]")

        response = f"""
<knowledge_graph>
/basic_knowledge_tree
{chr(10).join(lines)}

/advanced_knowledge_connections
</knowledge_graph>
"""
        result = parser.parse(response)
        assert len(result.nodes) == 50

    # ==================== 树边构建测试 ====================

    def test_tree_edges_built_correctly(
        self, parser: KnowledgeGraphParser, valid_llm_response: str
    ):
        """测试树边正确构建"""
        result = parser.parse(valid_llm_response)

        tree_edges = [e for e in result.edges if e.edge_type == "knowledge_tree"]

        # 验证树边数量等于有父节点的节点数
        nodes_with_parent = [n for n in result.nodes if n.parent_label]
        assert len(tree_edges) == len(nodes_with_parent)

        # 验证所有树边的源节点和目标节点匹配
        for edge in tree_edges:
            target_node = next(n for n in result.nodes if n.label == edge.target_label)
            assert target_node.parent_label == edge.source_label

    def test_sibling_nodes_same_parent(self, parser: KnowledgeGraphParser):
        """测试兄弟节点有相同父节点"""
        response = """
<knowledge_graph>
/basic_knowledge_tree
* Parent [0.5]
** Child A [0.3]
** Child B [0.4]
** Child C [0.5]

/advanced_knowledge_connections
</knowledge_graph>
"""
        result = parser.parse(response)

        children = [n for n in result.nodes if n.level == 2]
        assert all(c.parent_label == "Parent" for c in children)
        assert len(children) == 3

    # ==================== 数据类完整性测试 ====================

    def test_parsed_node_dataclass(self, parser: KnowledgeGraphParser):
        """测试 ParsedNode 数据类"""
        node = ParsedNode(
            label="Test",
            mastery=50,
            level=1,
            parent_label=None,
        )
        assert node.label == "Test"
        assert node.mastery == 50
        assert node.level == 1
        assert node.parent_label is None

    def test_parsed_edge_dataclass(self, parser: KnowledgeGraphParser):
        """测试 ParsedEdge 数据类"""
        edge = ParsedEdge(
            source_label="A",
            target_label="B",
            edge_type="knowledge_tree",
        )
        assert edge.source_label == "A"
        assert edge.target_label == "B"
        assert edge.edge_type == "knowledge_tree"

    def test_parsed_knowledge_graph_dataclass(self, parser: KnowledgeGraphParser):
        """测试 ParsedKnowledgeGraph 数据类"""
        nodes = [ParsedNode("A", 50, 1, None)]
        edges = [ParsedEdge("A", "B", "advanced")]
        graph = ParsedKnowledgeGraph(nodes=nodes, edges=edges)

        assert len(graph.nodes) == 1
        assert len(graph.edges) == 1


class TestMasteryConversion:
    """掌握度转换专项测试"""

    @pytest.fixture
    def parser(self) -> KnowledgeGraphParser:
        return KnowledgeGraphParser()

    @pytest.mark.parametrize(
        "score,expected",
        [
            (-1, None),
            (-0.5, None),
            (0, 0),
            (0.5, 50),
            (0.99, 99),
            (1, 100),
            (1.5, 100),
            (2, 100),
        ],
    )
    def test_mastery_conversion(
        self, parser: KnowledgeGraphParser, score: float, expected: int | None
    ):
        """参数化测试掌握度转换"""
        result = parser._convert_mastery(score)
        assert result == expected


class TestEdgePatterns:
    """边模式匹配测试"""

    @pytest.fixture
    def parser(self) -> KnowledgeGraphParser:
        return KnowledgeGraphParser()

    @pytest.mark.parametrize(
        "edge_str,expected",
        [
            ("A->B", ("A", "B")),
            ("A -> B", ("A", "B")),
            ("A  ->  B", ("A", "B")),
            ("Node A->Node B", ("Node A", "Node B")),
            ("中文节点->英文Node", ("中文节点", "英文Node")),
        ],
    )
    def test_edge_pattern_matching(
        self, parser: KnowledgeGraphParser, edge_str: str, expected: tuple[str, str]
    ):
        """参数化测试边模式匹配"""
        match = parser.EDGE_PATTERN.match(edge_str)
        assert match is not None
        assert match.group(1).strip() == expected[0]
        assert match.group(2).strip() == expected[1]
