#!/usr/bin/env python3
"""
output_reader.py
================
Библиотека чтения артефактов sql-query-analyzer из output-директории.

Предназначена для импорта ИИ-моделями и скриптами.
"""

import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any


class OutputReader:
    """Читает артефакты из output-директории (tables/, lineage/, normalized/)."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        if not self.output_dir.exists():
            raise FileNotFoundError(f"Output dir not found: {self.output_dir}")

        self.tables_dir = self.output_dir / "tables"
        self.lineage_dir = self.output_dir / "lineage"
        self.norm_dir = self.output_dir / "normalized"
        self.texts_dir = self.output_dir / "query_texts"

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------
    def _read_csv(self, rel_path: str) -> List[Dict[str, str]]:
        path = self.output_dir / rel_path
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def fields(self) -> List[Dict[str, str]]:
        return self._read_csv("tables/fields.csv")

    def expressions(self) -> List[Dict[str, str]]:
        return self._read_csv("tables/expressions.csv")

    def conditions(self) -> List[Dict[str, str]]:
        return self._read_csv("tables/conditions.csv")

    def joins(self) -> List[Dict[str, str]]:
        return self._read_csv("tables/joins.csv")

    def field_mapping(self) -> List[Dict[str, str]]:
        return self._read_csv("lineage/field_mapping.csv")

    def dependency_matrix(self) -> List[Dict[str, str]]:
        return self._read_csv("lineage/dependency_matrix.csv")

    def edges_parent(self) -> List[Dict[str, str]]:
        """parent_id,child_id,parent_name,child_name,depth,relation"""
        return self._read_csv("tables/edges_parent.csv")

    def edges_refs(self) -> List[Dict[str, str]]:
        """from_id,to_id,fromname,toname,relation"""
        return self._read_csv("tables/edges_refs.csv")

    def children_of(self, node_id: int) -> List[Dict[str, str]]:
        """Возвращает дочерние узлы через edges_parent (union parts, subqueries)."""
        return [r for r in self.edges_parent() if r.get("parent_id") == str(node_id)]

    def parents_of(self, node_id: int) -> List[Dict[str, str]]:
        """Возвращает родительские узлы через edges_parent."""
        return [r for r in self.edges_parent() if r.get("child_id") == str(node_id)]

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------
    def _read_json(self, rel_path: str) -> Any:
        path = self.output_dir / rel_path
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def field_lineage(self) -> Optional[List[Dict]]:
        return self._read_json("lineage/field_lineage.json")

    def lineage_key_fields(self) -> Optional[Dict]:
        return self._read_json("lineage/lineage_key_fields.json")

    def nodes(self) -> List[Dict]:
        """Возвращает список узлов из nodes.jsonl (потоковое чтение)."""
        path = self.norm_dir / "nodes.jsonl"
        if not path.exists():
            return []
        nodes = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    nodes.append(json.loads(line))
        return nodes

    def node_by_id(self, node_id: int) -> Optional[Dict]:
        """Возвращает узел по ID (ленивое потоковое чтение)."""
        for node in self.nodes():
            if node.get("id") == node_id:
                return node
        return None

    def node_by_name(self, name: str) -> Optional[Dict]:
        for node in self.nodes():
            if node.get("name", "").upper() == name.upper():
                return node
        return None

    def node_sql_text(self, node_id: int) -> Optional[str]:
        """Возвращает SQL-текст узла из query_texts/node_{id}.sql."""
        path = self.texts_dir / f"node_{node_id}.sql"
        if path.exists():
            return path.read_text(encoding="utf-8")
        # fallback на nodes.jsonl
        node = self.node_by_id(node_id)
        return node.get("text") if node else None

    def node_md_text(self, node_id: int) -> Optional[str]:
        path = self.texts_dir / f"node_{node_id}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def find_field_rows(self, alias: str) -> List[Dict[str, str]]:
        """Все строки fields.csv с заданным alias."""
        return [r for r in self.fields() if r.get("alias") == alias]

    def find_expression_rows(self, alias: str) -> List[Dict[str, str]]:
        """Все строки expressions.csv с заданным output_alias."""
        return [r for r in self.expressions() if r.get("output_alias") == alias]

    def lineage_for(self, field_name: str) -> Optional[Dict]:
        """Цепочка lineage для поля."""
        data = self.field_lineage()
        if not data:
            return None
        for item in data:
            if item.get("output_field") == field_name:
                return item
        return None
