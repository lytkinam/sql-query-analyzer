"""
exporters/tables.py
===================
Генерация всех CSV/JSON-файлов итерации 1.

Выходные файлы (создаются в output_dir):

  normalized/
    nodes.json               — нормализованный JSON (без source_kinds)
    nodes.jsonl              — JSON Lines
    tempqueries.json         — только temp_query-узлы
    subqueries.json          — только sub_query-узлы

  tables/
    nodes.csv                — плоская таблица узлов
    tempqueries_catalog.csv  — каталог ВТ
    edges_parent.csv         — дерево родитель→потомок
    edges_refs.csv           — граф ссылок между ВТ
    sources_map.csv          — источники по узлам
    union_parts.csv          — карта объединений
    stubs.csv                — технические заглушки

Использование
-------------
    from exporters.normalizer import normalize
    from exporters.tables import generate_tables
    import json

    raw = json.loads(analyze_sql_query(sql_text, detailed=True))
    model = normalize(raw)
    generate_tables(model, "./output")
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from typing import Any


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_csv(filepath: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(filepath: str, data: Any) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_jsonl(filepath: str, records: list[dict]) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# normalized/
# ---------------------------------------------------------------------------

def _export_normalized(model: dict, out_dir: str) -> None:
    norm_dir = os.path.join(out_dir, "normalized")
    _mkdir(norm_dir)

    nodes = model["nodes"]

    # nodes.json — без служебного source_kinds (он внутренний)
    nodes_clean = [
        {k: v for k, v in n.items() if k != "source_kinds"}
        for n in nodes
    ]
    _write_json(os.path.join(norm_dir, "nodes.json"), nodes_clean)
    _write_jsonl(os.path.join(norm_dir, "nodes.jsonl"), nodes_clean)

    # tempqueries.json
    _write_json(
        os.path.join(norm_dir, "tempqueries.json"),
        [n for n in nodes_clean if n["type"] == "temp_query"],
    )

    # subqueries.json
    _write_json(
        os.path.join(norm_dir, "subqueries.json"),
        [n for n in nodes_clean if n["type"] == "sub_query"],
    )


# ---------------------------------------------------------------------------
# tables/nodes.csv
# ---------------------------------------------------------------------------

def _export_nodes_csv(nodes: list[dict], out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    rows = []
    for n in nodes:
        rows.append({
            "id":                  n["id"],
            "name":                n["name"],
            "type":                n["type"],
            "parent_id":          n.get("parent_id", "") if n.get("parent_id") is not None else "",
            "max_parent_id":      n.get("max_parent_id", "") if n.get("max_parent_id") is not None else "",
            "children_count":     len(n.get("children_ids", [])),
            "own_in_tables_count": len(n.get("own_in_tables", [])),
            "is_stub":            str(n.get("is_stub", False)).lower(),
            "is_union_part":      str(n.get("is_union_part", False)).lower(),
            "text_len":           len(n.get("text", "")),
        })

    _write_csv(
        os.path.join(tables_dir, "nodes.csv"),
        ["id", "name", "type", "parent_id", "max_parent_id",
         "children_count", "own_in_tables_count", "is_stub", "is_union_part", "text_len"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/tempqueries_catalog.csv
# ---------------------------------------------------------------------------

def _export_tempqueries_catalog(nodes: list[dict], out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    # собираем union_parts: parent_id → список child name
    union_map: dict[int, list[str]] = defaultdict(list)
    for n in nodes:
        if n.get("is_union_part") and n.get("parent_id") is not None:
            union_map[n["parent_id"]].append(n["name"])

    rows = []
    for n in nodes:
        if n["type"] != "temp_query":
            continue
        parts = union_map.get(n["id"], [])
        rows.append({
            "id":                  n["id"],
            "name":                n["name"],
            "type":                n["type"],
            "parent_id":          n.get("parent_id", "") if n.get("parent_id") is not None else "",
            "max_parent_id":      n.get("max_parent_id", "") if n.get("max_parent_id") is not None else "",
            "children_count":     len(n.get("children_ids", [])),
            "own_in_tables_count": len(n.get("own_in_tables", [])),
            "is_stub":            str(n.get("is_stub", False)).lower(),
            "is_union_part":      str(n.get("is_union_part", False)).lower(),
            "union_parts":        ";".join(parts),
        })

    _write_csv(
        os.path.join(tables_dir, "tempqueries_catalog.csv"),
        ["id", "name", "type", "parent_id", "max_parent_id",
         "children_count", "own_in_tables_count", "is_stub", "is_union_part", "union_parts"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/edges_parent.csv
# ---------------------------------------------------------------------------

def _export_edges_parent(model: dict, out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    # BFS для вычисления depth
    node_by_id = {n["id"]: n for n in model["nodes"]}
    depth: dict[int, int] = {}

    # Корни — узлы без parent_id
    from collections import deque
    queue: deque = deque()
    for n in model["nodes"]:
        if n.get("parent_id") is None:
            depth[n["id"]] = 0
            queue.append(n["id"])

    while queue:
        nid = queue.popleft()
        node = node_by_id.get(nid)
        if not node:
            continue
        for cid in node.get("children_ids", []):
            if cid not in depth:
                depth[cid] = depth[nid] + 1
                queue.append(cid)

    # Структурные рёбра из модели
    rows = []
    for e in model["edges"]:
        if e["relation"] not in ("parent_child", "union_part"):
            continue
        rows.append({
            "parent_id":   e["from_id"],
            "child_id":    e["to_id"],
            "parent_name": e["from_name"],
            "child_name":  e["to_name"],
            "depth":       depth.get(e["to_id"], ""),
            "relation":    e["relation"],
        })

    _write_csv(
        os.path.join(tables_dir, "edges_parent.csv"),
        ["parent_id", "child_id", "parent_name", "child_name", "depth", "relation"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/edges_refs.csv
# ---------------------------------------------------------------------------

def _export_edges_refs(model: dict, out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    rows = []
    for e in model["edges"]:
        if e["relation"] != "ref":
            continue
        rows.append({
            "from_id":  e["from_id"],
            "to_id":    e["to_id"],
            "fromname": e["from_name"],
            "toname":   e["to_name"],
            "relation": e["relation"],
        })

    _write_csv(
        os.path.join(tables_dir, "edges_refs.csv"),
        ["from_id", "to_id", "fromname", "toname", "relation"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/sources_map.csv
# ---------------------------------------------------------------------------

def _export_sources_map(nodes: list[dict], out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    rows = []
    for n in nodes:
        tables = n.get("own_in_tables", [])
        kinds = n.get("source_kinds", ["Unknown"] * len(tables))
        for i, (src, kind) in enumerate(zip(tables, kinds), start=1):
            rows.append({
                "node_id":    n["id"],
                "node_name":  n["name"],
                "source_name": src,
                "source_kind": kind,
                "ordinal":    i,
            })

    _write_csv(
        os.path.join(tables_dir, "sources_map.csv"),
        ["node_id", "node_name", "source_name", "source_kind", "ordinal"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/union_parts.csv
# ---------------------------------------------------------------------------

def _export_union_parts(nodes: list[dict], out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    node_by_id = {n["id"]: n for n in nodes}
    rows = []
    for n in nodes:
        if not n.get("is_union_part"):
            continue
        pid = n.get("parent_id")
        parent = node_by_id.get(pid) if pid is not None else None
        # Номер части: позиция среди union_part-детей родителя
        part_number = 1
        if parent:
            siblings = [
                c_id for c_id in parent.get("children_ids", [])
                if node_by_id.get(c_id, {}).get("is_union_part")
            ]
            if n["id"] in siblings:
                part_number = siblings.index(n["id"]) + 1

        rows.append({
            "parent_query_id": pid if pid is not None else "",
            "parent_name":     parent["name"] if parent else "",
            "part_id":         n["id"],
            "part_name":       n["name"],
            "part_number":     part_number,
            "is_union_part":   str(n.get("is_union_part", True)).lower(),
        })

    _write_csv(
        os.path.join(tables_dir, "union_parts.csv"),
        ["parent_query_id", "parent_name", "part_id", "part_name", "part_number", "is_union_part"],
        rows,
    )


# ---------------------------------------------------------------------------
# tables/stubs.csv
# ---------------------------------------------------------------------------

def _export_stubs(nodes: list[dict], out_dir: str) -> None:
    tables_dir = os.path.join(out_dir, "tables")
    _mkdir(tables_dir)

    rows = []
    for n in nodes:
        if not n.get("is_stub"):
            continue
        # Причина: нет имени → empty_body, нет потребителей → no_consumers
        reason = "empty_body" if not n.get("name") else "no_consumers"
        rows.append({
            "node_id":   n["id"],
            "node_name": n["name"],
            "type":      n["type"],
            "is_stub":   str(n.get("is_stub", True)).lower(),
            "reason":    reason,
        })

    _write_csv(
        os.path.join(tables_dir, "stubs.csv"),
        ["node_id", "node_name", "type", "is_stub", "reason"],
        rows,
    )


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def generate_tables(model: dict[str, Any], output_dir: str) -> None:
    """
    Генерирует все файлы итерации 1 в output_dir.

    Параметры
    ---------
    model : dict
        Нормализованная модель из exporters.normalizer.normalize().
    output_dir : str
        Путь к корневому каталогу вывода.
    """
    nodes = model["nodes"]

    _export_normalized(model, output_dir)
    _export_nodes_csv(nodes, output_dir)
    _export_tempqueries_catalog(nodes, output_dir)
    _export_edges_parent(model, output_dir)
    _export_edges_refs(model, output_dir)
    _export_sources_map(nodes, output_dir)
    _export_union_parts(nodes, output_dir)
    _export_stubs(nodes, output_dir)
