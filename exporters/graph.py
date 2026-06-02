"""
exporters/graph.py
==================
Итерация 3: граф зависимостей в разных форматах.

Выходные файлы (в output_dir/graph/):

  graph/
    query_graph.json     — {nodes: [{id, label, type}], edges: [{from, to, label}]}
    query_tree.json      — вложенный JSON с children[]
    query_graph.mmd      — Mermaid graph TD
    query_graph.dot      — Graphviz DOT с цветовой схемой
    query_graph.gexf     — GEXF XML для Gephi
    query_graph.graphml  — GraphML XML для yEd / NetworkX
    cytoscape.json       — Cytoscape.js формат
    d3_graph.json        — D3.js формат

Цветовая схема DOT:
  temp_query             → lightgreen
  sub_query              → lightblue
  is_stub=true           → lightyellow
  финальный результат (нет исходящих ref-рёбер) → lightsalmon

Использование
-------------
    from exporters.normalizer import normalize
    from exporters.graph import generate_graph
    import json

    raw = json.loads(analyze_sql_query(sql_text, detailed=True))
    model = normalize(raw)
    generate_graph(model, "./output")
"""

from __future__ import annotations

import json
import os
from typing import Any
from xml.etree import ElementTree as ET


def _mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write(filepath: str, content: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def _write_json(filepath: str, data: Any) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Определяем цвет узла для DOT
# ---------------------------------------------------------------------------

def _dot_color(node: dict, has_outgoing_ref: bool) -> str:
    if node.get("is_stub"):
        return "lightyellow"
    if not has_outgoing_ref and node["type"] == "temp_query":
        return "lightsalmon"
    if node["type"] == "temp_query":
        return "lightgreen"
    return "lightblue"  # sub_query


# ---------------------------------------------------------------------------
# graph/query_graph.json
# ---------------------------------------------------------------------------

def _build_flat_graph(model: dict) -> dict:
    nodes = [
        {"id": n["id"], "label": n["name"] or f"node_{n['id']}", "type": n["type"]}
        for n in model["nodes"]
    ]
    edges = [
        {"from": e["from_id"], "to": e["to_id"], "label": e["relation"]}
        for e in model["edges"]
        if e["relation"] == "ref"  # только data-flow
    ]
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# graph/query_tree.json
# ---------------------------------------------------------------------------

def _build_tree(model: dict) -> list[dict]:
    """Вложенный JSON: корневые узлы + children[]."""
    nodes_by_id: dict[int, dict] = {n["id"]: n for n in model["nodes"]}

    def build_node(n: dict) -> dict:
        children_ids = n.get("children_ids", [])
        return {
            "id":           n["id"],
            "name":         n["name"] or "",
            "type":         n["type"],
            "is_union_part": n.get("is_union_part", False),
            "is_stub":      n.get("is_stub", False),
            "children":     [build_node(nodes_by_id[c]) for c in children_ids if c in nodes_by_id],
        }

    roots = [n for n in model["nodes"] if n.get("parent_id") is None]
    return [build_node(r) for r in roots]


# ---------------------------------------------------------------------------
# graph/query_graph.mmd
# ---------------------------------------------------------------------------

def _build_mermaid(model: dict) -> str:
    lines = ["graph TD"]
    id_to_safe: dict[int, str] = {}

    for n in model["nodes"]:
        safe = f"n{n['id']}"
        id_to_safe[n["id"]] = safe
        label = (n["name"] or f"node_{n['id']}").replace('"', "'")
        lines.append(f'    {safe}["{label}\\n(id:{n["id"]})"]')

    for e in model["edges"]:
        if e["relation"] != "ref":
            continue
        src = id_to_safe.get(e["from_id"])
        dst = id_to_safe.get(e["to_id"])
        if src and dst:
            lines.append(f"    {src} --> {dst}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# graph/query_graph.dot
# ---------------------------------------------------------------------------

def _build_dot(model: dict) -> str:
    # Узлы, из которых есть исходящие ref-рёбра
    nodes_with_outgoing: set[int] = {
        e["from_id"] for e in model["edges"] if e["relation"] == "ref"
    }

    lines = [
        "digraph QueryGraph {",
        "    rankdir=LR;",
        '    node [shape=box, style=filled, fillcolor=lightblue];',
        "",
    ]

    for n in model["nodes"]:
        label = (n["name"] or f"node_{n['id']}").replace('"', "'")
        color = _dot_color(n, n["id"] in nodes_with_outgoing)
        lines.append(f'    n{n["id"]} [label="{label}\\n(id:{n["id"]})", fillcolor={color}];')

    lines.append("")

    for e in model["edges"]:
        if e["relation"] != "ref":
            continue
        lines.append(f'    n{e["from_id"]} -> n{e["to_id"]} [label="ref"];')

    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# graph/query_graph.gexf
# ---------------------------------------------------------------------------

def _build_gexf(model: dict) -> str:
    root = ET.Element("gexf", {"xmlns": "http://gexf.net/1.3", "version": "1.3"})
    graph = ET.SubElement(root, "graph", {"defaultedgetype": "directed"})

    nodes_el = ET.SubElement(graph, "nodes")
    for n in model["nodes"]:
        ET.SubElement(nodes_el, "node", {
            "id":    str(n["id"]),
            "label": n["name"] or f"node_{n['id']}",
        })

    edges_el = ET.SubElement(graph, "edges")
    for i, e in enumerate(e for e in model["edges"] if e["relation"] == "ref"):
        ET.SubElement(edges_el, "edge", {
            "id":     str(i),
            "source": str(e["from_id"]),
            "target": str(e["to_id"]),
        })

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


# ---------------------------------------------------------------------------
# graph/query_graph.graphml
# ---------------------------------------------------------------------------

def _build_graphml(model: dict) -> str:
    ns = "http://graphml.graphdrawing.org/graphml"
    root = ET.Element("graphml", {"xmlns": ns})

    # ключи атрибутов
    ET.SubElement(root, "key", {"id": "name", "for": "node", "attr.name": "name", "attr.type": "string"})
    ET.SubElement(root, "key", {"id": "type", "for": "node", "attr.name": "type", "attr.type": "string"})
    ET.SubElement(root, "key", {"id": "is_stub", "for": "node", "attr.name": "is_stub", "attr.type": "boolean"})
    ET.SubElement(root, "key", {"id": "rel", "for": "edge", "attr.name": "relation", "attr.type": "string"})

    graph_el = ET.SubElement(root, "graph", {"id": "QueryGraph", "edgedefault": "directed"})

    for n in model["nodes"]:
        node_el = ET.SubElement(graph_el, "node", {"id": str(n["id"])})
        d = ET.SubElement(node_el, "data", {"key": "name"})
        d.text = n["name"] or ""
        d2 = ET.SubElement(node_el, "data", {"key": "type"})
        d2.text = n["type"]
        d3 = ET.SubElement(node_el, "data", {"key": "is_stub"})
        d3.text = str(n.get("is_stub", False)).lower()

    for i, e in enumerate(e for e in model["edges"] if e["relation"] == "ref"):
        edge_el = ET.SubElement(graph_el, "edge", {
            "id":     f"e{i}",
            "source": str(e["from_id"]),
            "target": str(e["to_id"]),
        })
        d = ET.SubElement(edge_el, "data", {"key": "rel"})
        d.text = e["relation"]

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


# ---------------------------------------------------------------------------
# graph/cytoscape.json
# ---------------------------------------------------------------------------

def _build_cytoscape(model: dict) -> dict:
    nodes = [
        {"data": {
            "id":    str(n["id"]),
            "label": n["name"] or f"node_{n['id']}",
            "type":  n["type"],
        }}
        for n in model["nodes"]
    ]
    edges = [
        {"data": {
            "id":     f"e{i}",
            "source": str(e["from_id"]),
            "target": str(e["to_id"]),
            "label":  e["relation"],
        }}
        for i, e in enumerate(e for e in model["edges"] if e["relation"] == "ref")
    ]
    return {"elements": {"nodes": nodes, "edges": edges}}


# ---------------------------------------------------------------------------
# graph/d3_graph.json
# ---------------------------------------------------------------------------

def _build_d3(model: dict) -> dict:
    # group: 1=temp_query, 2=sub_query, 0=stub
    def group(n: dict) -> int:
        if n.get("is_stub"):
            return 0
        return 1 if n["type"] == "temp_query" else 2

    nodes = [
        {"id": n["id"], "name": n["name"] or f"node_{n['id']}", "type": n["type"], "group": group(n)}
        for n in model["nodes"]
    ]
    links = [
        {"source": e["from_id"], "target": e["to_id"], "value": 1}
        for e in model["edges"]
        if e["relation"] == "ref"
    ]
    return {"nodes": nodes, "links": links}


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def generate_graph(model: dict[str, Any], output_dir: str) -> None:
    """
    Генерирует все графовые файлы итерации 3 в output_dir/graph/.

    Параметры
    ----------
    model : dict
        Нормализованная модель из exporters.normalizer.normalize().
    output_dir : str
        Путь к корневому каталогу вывода.
    """
    graph_dir = os.path.join(output_dir, "graph")
    _mkdir(graph_dir)

    _write_json(os.path.join(graph_dir, "query_graph.json"), _build_flat_graph(model))
    _write_json(os.path.join(graph_dir, "query_tree.json"), _build_tree(model))
    _write(os.path.join(graph_dir, "query_graph.mmd"), _build_mermaid(model))
    _write(os.path.join(graph_dir, "query_graph.dot"), _build_dot(model))
    _write(os.path.join(graph_dir, "query_graph.gexf"), _build_gexf(model))
    _write(os.path.join(graph_dir, "query_graph.graphml"), _build_graphml(model))
    _write_json(os.path.join(graph_dir, "cytoscape.json"), _build_cytoscape(model))
    _write_json(os.path.join(graph_dir, "d3_graph.json"), _build_d3(model))
