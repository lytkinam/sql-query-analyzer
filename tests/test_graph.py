"""
tests/test_graph.py
===================
Тесты итерации 3: exporters/graph.py

Запуск:
    pytest tests/test_graph.py -v
"""

import json
import os
import sys
import tempfile
from xml.etree import ElementTree as ET

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.graph import generate_graph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SMALL_SQL_PATH = os.path.join(ROOT, "examples", "example.sql")
LARGE_SQL_PATH = os.path.join(ROOT, "examples", "example_258.sql")


@pytest.fixture(scope="module")
def small_model():
    with open(SMALL_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return normalize(json.loads(analyze_sql_query(sql, detailed=True)))


@pytest.fixture(scope="module")
def small_output(small_model):
    tmp = tempfile.mkdtemp()
    generate_graph(small_model, tmp)
    return tmp


@pytest.fixture(scope="module")
def large_model():
    with open(LARGE_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return normalize(json.loads(analyze_sql_query(sql, detailed=True)))


@pytest.fixture(scope="module")
def large_output(large_model):
    tmp = tempfile.mkdtemp()
    generate_graph(large_model, tmp)
    return tmp


# ---------------------------------------------------------------------------
# TestGraphFilesExist
# ---------------------------------------------------------------------------

EXPECTED_FILES = [
    "query_graph.json",
    "query_tree.json",
    "query_graph.mmd",
    "query_graph.dot",
    "query_graph.gexf",
    "query_graph.graphml",
    "cytoscape.json",
    "d3_graph.json",
]


class TestGraphFilesExist:
    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_file_exists(self, small_output, filename):
        path = os.path.join(small_output, "graph", filename)
        assert os.path.exists(path), f"Отсутствует: {filename}"

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_file_nonempty(self, small_output, filename):
        path = os.path.join(small_output, "graph", filename)
        assert os.path.getsize(path) > 0, f"Пустой: {filename}"


# ---------------------------------------------------------------------------
# TestFlatGraph
# ---------------------------------------------------------------------------

class TestFlatGraph:
    def test_has_nodes_and_edges(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data and "edges" in data

    def test_node_count_matches_model(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["nodes"]) == len(small_model["nodes"])

    def test_only_ref_edges(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        for e in data["edges"]:
            assert e["label"] == "ref"

    def test_node_fields(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        for node in data["nodes"]:
            assert "id" in node and "label" in node and "type" in node

    def test_edge_fields(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        for e in data["edges"]:
            assert "from" in e and "to" in e and "label" in e


# ---------------------------------------------------------------------------
# TestTree
# ---------------------------------------------------------------------------

class TestTree:
    def test_is_list(self, small_output):
        with open(os.path.join(small_output, "graph", "query_tree.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_each_node_has_children_field(self, small_output):
        with open(os.path.join(small_output, "graph", "query_tree.json"), encoding="utf-8") as f:
            data = json.load(f)

        def check(nodes):
            for n in nodes:
                assert "children" in n, f"Нет children: {n}"
                assert "id" in n and "type" in n
                check(n["children"])

        check(data)

    def test_total_node_count(self, small_model, small_output):
        """BFS по query_tree.json даёт то же кол-во узлов, что и в модели."""
        with open(os.path.join(small_output, "graph", "query_tree.json"), encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        stack = list(data)
        while stack:
            n = stack.pop()
            count += 1
            stack.extend(n["children"])

        assert count == len(small_model["nodes"])


# ---------------------------------------------------------------------------
# TestMermaid
# ---------------------------------------------------------------------------

class TestMermaid:
    def test_starts_with_graph_td(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.mmd"), encoding="utf-8") as f:
            content = f.read()
        assert content.startswith("graph TD")

    def test_contains_node_definitions(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.mmd"), encoding="utf-8") as f:
            content = f.read()
        for n in small_model["nodes"]:
            assert f"n{n['id']}[" in content, f"Нет узла n{n['id']}"

    def test_contains_arrows_for_ref_edges(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.mmd"), encoding="utf-8") as f:
            content = f.read()
        ref_edges = [e for e in small_model["edges"] if e["relation"] == "ref"]
        for e in ref_edges:
            assert f"n{e['from_id']} --> n{e['to_id']}" in content


# ---------------------------------------------------------------------------
# TestDot
# ---------------------------------------------------------------------------

class TestDot:
    def test_starts_with_digraph(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        assert "digraph QueryGraph" in content

    def test_contains_rankdir(self, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        assert "rankdir=LR" in content

    def test_color_lightgreen_for_temp_query(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        # Хотя бы один узел temp_query с цветом
        assert "lightgreen" in content or "lightsalmon" in content

    def test_all_nodes_present(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        for n in small_model["nodes"]:
            assert f"n{n['id']} [" in content

    def test_ref_edges_present(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        for e in [e for e in small_model["edges"] if e["relation"] == "ref"]:
            assert f"n{e['from_id']} -> n{e['to_id']}" in content


# ---------------------------------------------------------------------------
# TestGexf
# ---------------------------------------------------------------------------

class TestGexf:
    def test_valid_xml(self, small_output):
        path = os.path.join(small_output, "graph", "query_graph.gexf")
        tree = ET.parse(path)  # не падает — валидный XML
        root = tree.getroot()
        assert root.tag.endswith("gexf")

    def test_node_count(self, small_model, small_output):
        tree = ET.parse(os.path.join(small_output, "graph", "query_graph.gexf"))
        ns = {"g": "http://gexf.net/1.3"}
        nodes_el = tree.findall(".//g:node", ns)
        assert len(nodes_el) == len(small_model["nodes"])

    def test_edge_count(self, small_model, small_output):
        tree = ET.parse(os.path.join(small_output, "graph", "query_graph.gexf"))
        ns = {"g": "http://gexf.net/1.3"}
        edges_el = tree.findall(".//g:edge", ns)
        ref_count = sum(1 for e in small_model["edges"] if e["relation"] == "ref")
        assert len(edges_el) == ref_count


# ---------------------------------------------------------------------------
# TestGraphml
# ---------------------------------------------------------------------------

class TestGraphml:
    def test_valid_xml(self, small_output):
        tree = ET.parse(os.path.join(small_output, "graph", "query_graph.graphml"))
        root = tree.getroot()
        assert "graphml" in root.tag

    def test_node_count(self, small_model, small_output):
        tree = ET.parse(os.path.join(small_output, "graph", "query_graph.graphml"))
        ns = {"g": "http://graphml.graphdrawing.org/graphml"}
        nodes_el = tree.findall(".//g:node", ns)
        assert len(nodes_el) == len(small_model["nodes"])

    def test_has_key_definitions(self, small_output):
        tree = ET.parse(os.path.join(small_output, "graph", "query_graph.graphml"))
        ns = {"g": "http://graphml.graphdrawing.org/graphml"}
        keys = tree.findall(".//g:key", ns)
        assert len(keys) >= 2  # name, type


# ---------------------------------------------------------------------------
# TestCytoscape
# ---------------------------------------------------------------------------

class TestCytoscape:
    def test_structure(self, small_output):
        with open(os.path.join(small_output, "graph", "cytoscape.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "elements" in data
        assert "nodes" in data["elements"]
        assert "edges" in data["elements"]

    def test_node_count(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "cytoscape.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["elements"]["nodes"]) == len(small_model["nodes"])

    def test_node_data_fields(self, small_output):
        with open(os.path.join(small_output, "graph", "cytoscape.json"), encoding="utf-8") as f:
            data = json.load(f)
        for n in data["elements"]["nodes"]:
            assert "id" in n["data"] and "label" in n["data"] and "type" in n["data"]


# ---------------------------------------------------------------------------
# TestD3
# ---------------------------------------------------------------------------

class TestD3:
    def test_structure(self, small_output):
        with open(os.path.join(small_output, "graph", "d3_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data and "links" in data

    def test_node_count(self, small_model, small_output):
        with open(os.path.join(small_output, "graph", "d3_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["nodes"]) == len(small_model["nodes"])

    def test_node_has_group(self, small_output):
        with open(os.path.join(small_output, "graph", "d3_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        for n in data["nodes"]:
            assert "group" in n
            assert n["group"] in (0, 1, 2)

    def test_links_use_numeric_ids(self, small_output):
        with open(os.path.join(small_output, "graph", "d3_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        for lnk in data["links"]:
            assert isinstance(lnk["source"], int)
            assert isinstance(lnk["target"], int)


# ---------------------------------------------------------------------------
# TestGraphLarge
# ---------------------------------------------------------------------------

class TestGraphLarge:
    def test_node_count_large(self, large_model, large_output):
        with open(os.path.join(large_output, "graph", "query_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["nodes"]) >= 100

    def test_mmd_large_size(self, large_output):
        path = os.path.join(large_output, "graph", "query_graph.mmd")
        assert os.path.getsize(path) > 5000

    def test_dot_large_valid(self, large_output):
        with open(os.path.join(large_output, "graph", "query_graph.dot"), encoding="utf-8") as f:
            content = f.read()
        assert content.startswith("digraph QueryGraph")
        assert content.strip().endswith("}")

    def test_gexf_large_valid_xml(self, large_output):
        ET.parse(os.path.join(large_output, "graph", "query_graph.gexf"))  # не падает

    def test_d3_links_reference_existing_nodes(self, large_output):
        with open(os.path.join(large_output, "graph", "d3_graph.json"), encoding="utf-8") as f:
            data = json.load(f)
        node_ids = {n["id"] for n in data["nodes"]}
        for lnk in data["links"]:
            assert lnk["source"] in node_ids
            assert lnk["target"] in node_ids
