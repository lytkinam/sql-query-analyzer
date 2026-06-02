#!/usr/bin/env python3
"""
field_resolver.py
=================
Глубокое разрешение поля: lineage + "проваливание" через временные таблицы.

Проблема: lineage останавливается на границе ВТ (expr = "ВТ_Х.Поле").
Этот модуль проваливается внутрь ВТ, находит UNION-части или подзапросы,
где поле реально вычисляется, и возвращает их SQL-тексты.

Использование ИИ-моделями:
    from scripts.lib.field_resolver import FieldResolver
    from scripts.lib.output_reader import OutputReader

    reader = OutputReader("examples/output_258")
    resolver = FieldResolver(reader)
    result = resolver.resolve("ВидОбязательств_гр1а")
"""

import re
from typing import Dict, List, Optional, Tuple

from .output_reader import OutputReader


class FieldResolver:
    def __init__(self, reader: OutputReader):
        self.reader = reader

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def resolve(self, field_name: str) -> Dict:
        """
        Возвращает полную карту разрешения поля:
        {
            "field": str,
            "lineage": {...},           # из field_lineage.json
            "defining_nodes": [...],    # узлы, где поле реально определяется
            "sql_snippets": [...],      # фрагменты SQL с выделенными строками
            "upstream_fields": [...],   # исходные поля (распакованные из ВТ_Х.Поле)
        }
        """
        lineage = self.reader.lineage_for(field_name) or {}
        chain = lineage.get("chain", [])

        defining_nodes = []
        upstream_fields = []
        sql_snippets = []

        # 1. Последняя точка lineage (обычно ВТ_Х.Поле)
        if chain:
            last_step = chain[-1]
            src_table = last_step.get("source_table")
            src_field = last_step.get("source_field")
            if src_table and src_field:
                upstream_fields.append(f"{src_table}.{src_field}")

        # 2. Находим узел, который поставляет поле в финальную ВТ
        final_node_id = lineage.get("final_node_id")
        if final_node_id is not None:
            final_node = self.reader.node_by_id(final_node_id)
            if final_node:
                defining_nodes.append(self._node_info(final_node_id, final_node, field_name))
                sql_snippets.append(self._extract_sql_snippet(final_node_id, field_name))

        # 3. "Проваливаемся" — если поле приходит из другой ВТ, ищем там
        visited = set()
        worklist: List[Tuple[str, str]] = []
        for uf in upstream_fields:
            parts = uf.split(".")
            if len(parts) == 2:
                worklist.append((parts[0], parts[1]))

        while worklist:
            table, fld = worklist.pop(0)
            key = f"{table}.{fld}"
            if key in visited:
                continue
            visited.add(key)

            node = self.reader.node_by_name(table)
            if not node:
                continue

            nid = node.get("id")
            defining_nodes.append(self._node_info(nid, node, fld))
            sql_snippets.append(self._extract_sql_snippet(nid, fld))

            # Анализируем SQL этого узла: есть ли здесь UNION?
            # Если да — собираем все части UNION, где определяется fld
            union_parts = self._find_union_parts(node, fld)
            for part_nid, part_node in union_parts:
                if part_nid not in [d["node_id"] for d in defining_nodes]:
                    defining_nodes.append(self._node_info(part_nid, part_node, fld))
                    sql_snippets.append(self._extract_sql_snippet(part_nid, fld))

            # Если внутри узла поле приходит из ещё одной ВТ — добавляем в worklist
            inner_src = self._find_inner_source(node, fld)
            if inner_src:
                worklist.append(inner_src)

        return {
            "field": field_name,
            "lineage": lineage,
            "defining_nodes": defining_nodes,
            "sql_snippets": sql_snippets,
            "upstream_fields": list(visited),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _node_info(self, nid: int, node: Dict, field_name: str) -> Dict:
        return {
            "node_id": nid,
            "node_name": node.get("name"),
            "node_type": node.get("type"),
            "field_name": field_name,
        }

    def _extract_sql_snippet(self, nid: int, field_name: str) -> Dict:
        """Извлекает SQL узла + номера строк, где упоминается поле."""
        text = self.reader.node_sql_text(nid)
        if not text:
            return {"node_id": nid, "lines": [], "sql": ""}

        lines = text.splitlines()
        matched = []
        for i, line in enumerate(lines, start=1):
            if field_name in line:
                matched.append({"line_no": i, "text": line.rstrip()})

        return {
            "node_id": nid,
            "lines": matched,
            "sql": text,
        }

    def _find_union_parts(self, node: Dict, field_name: str) -> List[Tuple[int, Dict]]:
        """
        Если node — UNION (temp_query с UNION), находит все части UNION
        (sub_query), где определяется field_name, используя edges_parent.csv.
        """
        text = node.get("text", "")
        # Быстрая проверка: есть ли UNION?
        if "ОБЪЕДИНИТЬ" not in text and "UNION" not in text:
            return []

        nid = node.get("id")
        if nid is None:
            return []

        # Используем edges_parent для нахождения дочерних union_part
        parts = []
        for edge in self.reader.children_of(nid):
            if edge.get("relation") != "union_part":
                continue
            child_id = int(edge["child_id"])
            child_node = self.reader.node_by_id(child_id)
            if child_node and field_name in child_node.get("text", ""):
                parts.append((child_id, child_node))
        return parts

    def _find_inner_source(self, node: Dict, field_name: str) -> Optional[Tuple[str, str]]:
        """
        В SQL-tekcte узла ищет строку вида `ВТ_Х.Поле КАК field_name`
        и возвращает (ВТ_Х, Поле) для дальнейшего "проваливания".
        """
        text = node.get("text", "")
        if not text:
            return None

        # Регулярка: ВТ_Имя.Поле КАК field_name (с учётом русского КАК)
        pattern = re.compile(
            rf"([\w_]+)\.({re.escape(field_name)})\s+КАК\s+{re.escape(field_name)}",
            re.IGNORECASE,
        )
        m = pattern.search(text)
        if m:
            return (m.group(1), m.group(2))

        # Если alias отличается (ВТ_Х.Поле КАК field_name, где Поле != field_name)
        pattern2 = re.compile(
            rf"([\w_]+)\.(\w+)\s+КАК\s+{re.escape(field_name)}",
            re.IGNORECASE,
        )
        m2 = pattern2.search(text)
        if m2:
            return (m2.group(1), m2.group(2))

        return None
