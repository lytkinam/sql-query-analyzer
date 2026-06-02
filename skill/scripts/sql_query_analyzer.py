"""
sql_query_analyzer.py
=====================
Скилл: разбор SQL/1C-запроса на подзапросы и построение графа зависимостей.

Поддерживается:
  - 1С-синтаксис (ВЫБРАТЬ, ПОМЕСТИТЬ, ИЗ, СОЕДИНЕНИЕ, ОБЪЕДИНИТЬ ВСЕ, ...)
  - SQL-синтаксис (SELECT INTO, FROM, JOIN, UNION ALL, ...)
  - Вложенные подзапросы с псевдонимами (КАК / AS)
  - Пакетные запросы через ";"
  - Временные таблицы → граф зависимостей
  - Детальный режим: разбивает ОБЪЕДИНИТЬ/UNION на отдельные узлы

Использование
-------------
    from sql_query_analyzer import analyze_sql_query

    json_str = analyze_sql_query(sql_text, detailed=False)

Формат результата (JSON)
------------------------
{
  "nodes": [
    {
      "id":           int,        # уникальный номер узла
      "name":         str,        # имя таблицы/подзапроса
      "type":         str,        # "temp_query" | "result" | "sub_query"
      "text":         str,        # SQL-текст узла
      "parent_id":    int|null,   # ближайший родитель (для вложенных)
      "max_parent_id":int|null,   # корневой запрос в пакете
      "children_ids": [int],      # дочерние узлы
      "own_in_tables":[str],      # таблицы, читаемые этим узлом
      "is_stub":      bool,       # true = temp_query без потребителей
      "is_union_part":bool        # true = часть UNION (в detailed-режиме)
    }, ...
  ],
  "edges": [
    {
      "from":      int,  # id узла-источника (temp_query)
      "from_name": str,
      "to":        int,  # id узла-потребителя
      "to_name":   str
    }, ...
  ],
  "drop_queries": [str]  # таблицы из УНИЧТОЖИТЬ/DROP
}
"""

import re
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Node:
    id: int
    name: str
    text: str
    type: str
    children: list = field(default_factory=list)
    parent: "Optional[Node]" = field(default=None, repr=False)
    max_parent: "Optional[Node]" = field(default=None, repr=False)
    own_in_tables: list = field(default_factory=list)
    is_stub: bool = False
    is_union_part: bool = False


@dataclass
class Edge:
    out_node: Node
    in_node: Node


def _remove_innermost_round_brackets(text: str) -> str:
    while True:
        new = re.sub(r'\(([^()]*)\)', lambda m: '[' + m.group(1) + ']', text)
        if new == text:
            break
        text = new
    return text


def _remove_innermost_square_brackets(text: str) -> str:
    while True:
        new = re.sub(r'\[([^\[\]]*)\]', ' ', text)
        if new == text:
            break
        text = new
    return text


def _remove_innermost_curly_brackets(text: str) -> str:
    pattern = re.compile(
        r'\{(?!\s*\S+\s+(?:СОЕДИНЕНИЕ|JOIN)\s)([^{}]*)\}',
        re.IGNORECASE)
    while True:
        new = pattern.sub(' ', text)
        if new == text:
            break
        text = new
    return text


def get_own_in_tables(text: str) -> list:
    """
    Извлекает список имён таблиц из секций FROM/ИЗ/JOIN/СОЕДИНЕНИЕ.
    Вложенные скобки и нерелевантные клаузы удаляются перед поиском.
    """
    text = _remove_innermost_round_brackets(text)
    text = _remove_innermost_square_brackets(text)
    text = _remove_innermost_curly_brackets(text)
    text = re.sub(
        r'(?:^|\s)(?:ОБЪЕДИНИТЬ|UNION)(?:\s+(?:ВСЕ|ALL))?(?:$|\s)',
        ' ! ', text, flags=re.IGNORECASE)
    text = re.sub(
        r'(?:^|\s)(?:ВЫБРАТЬ|SELECT)\s(?:(?!![\s\S])*?(?:^|\s)(?:ИЗ|FROM)\s)',
        'ИЗ ', text, flags=re.IGNORECASE)
    for kw in [
        r'(?:СГРУППИРОВАТЬ|GROUP)\s+(?:ПО|BY)',
        r'(?:ДЛЯ ИЗМЕНЕНИЯ|FOR\s+UPDATE)',
        r'(?:ИНДЕКСИРОВАТЬ|INDEX)',
        r'(?:УПОРЯДОЧИТЬ|ORDER)',
        r'(?:ИТОГИ|TOTALS)',
    ]:
        text = re.sub(r'(?:^|\s)' + kw + r'[\s\S]*$', ' ', text, flags=re.IGNORECASE)
    matches = re.findall(
        r'(?:(?:(?:^|\s)(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+)|(?:,\s*))(\S+)(?:\s|$)',
        text, flags=re.IGNORECASE | re.MULTILINE)
    result = []
    for m in matches:
        upper = m.upper()
        if upper not in result:
            result.append(upper)
    return result


class SqlQueryAnalyzer:
    """Анализатор SQL/1C-запросов."""

    def __init__(self, detailed: bool = False):
        self.detailed = detailed
        self._nodes: list = []
        self._id_counter: int = 0
        self._unnamed_sub_query_count: int = 0
        self._result_table_count: int = 0
        self._drop_queries: list = []
        self._quotation_marks: dict = {}

    def analyze(self, sql_text: str) -> dict:
        self._reset()
        sql_text = re.sub(r'//.*', '', sql_text)
        sql_text = self._hide_quoted_strings(sql_text)
        for part in sql_text.split(';'):
            part = part.strip()
            if not part:
                continue
            if re.search(r'(?:^|\s)(?:УНИЧТОЖИТЬ|DROP)\s+', part, re.IGNORECASE):
                table = re.sub(r'(?:^|\s)(?:УНИЧТОЖИТЬ|DROP)\s+', '', part,
                               flags=re.IGNORECASE).strip()
                self._drop_queries.append(table)
                continue
            self._parse_query_part(part)
        self._restore_quoted_strings()
        edges = self._build_edges()
        return self._to_json(edges)

    def _reset(self):
        self._nodes = []
        self._id_counter = 0
        self._unnamed_sub_query_count = 0
        self._result_table_count = 0
        self._drop_queries = []
        self._quotation_marks = {}

    def _next_id(self) -> int:
        i = self._id_counter
        self._id_counter += 1
        return i

    def _hide_quoted_strings(self, text: str) -> str:
        def replacer(m):
            key = '__QM_' + uuid.uuid4().hex + '__'
            self._quotation_marks[key] = m.group(0)
            return key
        while True:
            new = re.sub(r'"[^"]*"', replacer, text, count=1)
            if new == text:
                break
            text = new
        return text

    def _restore_quoted_strings(self):
        for node in self._nodes:
            for key, val in self._quotation_marks.items():
                node.text = node.text.replace(key, val)

    def _brackets_to_square(self, text: str) -> str:
        while True:
            new = re.sub(
                r'\((?!\s*(?:ВЫБРАТЬ|SELECT)\s)([^()]*)\)',
                lambda m: '[' + m.group(1) + ']',
                text, flags=re.IGNORECASE)
            if new == text:
                break
            text = new
        return text

    def _parse_query_part(self, text: str):
        match = re.search(r'(?:\s|^)(?:ПОМЕСТИТЬ|INTO)\s+(\S+)', text, re.IGNORECASE)
        node_id = self._next_id()
        if match:
            name = match.group(1).strip()
            node_type = "temp_query"
        else:
            self._result_table_count += 1
            name = "Результат_" + str(self._result_table_count)
            node_type = "result"

        root_node = Node(id=node_id, name=name, text=text, type=node_type)
        self._nodes.append(root_node)

        work_text = self._brackets_to_square(text)
        context = {"current_parent": root_node}

        def replacer(m):
            full_match = m.group(0)
            alias = m.group(1)
            sub_id = self._next_id()
            if alias is None:
                self._unnamed_sub_query_count += 1
                alias = "Подзапрос_" + str(self._unnamed_sub_query_count)
            sub_node = Node(id=sub_id, name=alias, text="", type="sub_query")
            self._nodes.append(sub_node)
            saved_parent = context["current_parent"]
            context["current_parent"] = sub_node
            self._split_union(full_match, sub_node, context)
            context["current_parent"] = saved_parent
            saved_parent.children.append(sub_node)
            return "~" + str(sub_id) + "~"

        pattern = re.compile(
            r'\(\s*(?:ВЫБРАТЬ|SELECT)\s[^()]*\)'
            r'\s*(?:(?:КАК|AS)\s+([^\s),]+)(?=(?:\s|$|\)|,)))?',
            re.IGNORECASE)
        while True:
            new = pattern.sub(replacer, work_text, count=1)
            if new == work_text:
                break
            work_text = self._brackets_to_square(new)

        self._split_union(work_text, root_node, context, is_root=True)

        for child in root_node.children:
            self._set_parent(child, root_node)
        self._set_max_parent(root_node)

        for node in self._nodes:
            if node.type == "sub_query" and not node.is_union_part:
                node.text = re.sub(r'^\s*\(', '', node.text)
                node.text = re.sub(r'\s*\)(?![\s\S]*[()][\s\S]*)[\s\S]*', '', node.text)
            node.text = node.text.replace('[', '(').replace(']', ')')
            node.text = re.sub(r'~(\d+)~',
                               lambda m: self._nodes[int(m.group(1))].text,
                               node.text)
        for node in self._nodes:
            node.own_in_tables = [t for t in node.own_in_tables
                                  if not re.match(r'^~\d+~$', t)]

    def _split_union(self, text: str, node: Node, context: dict, is_root: bool = False):
        union_pattern = re.compile(
            r'(?:^|\s)(?:ОБЪЕДИНИТЬ|UNION)(?:\s+(?:ВСЕ|ALL))?(?:\s|$)',
            re.IGNORECASE)
        parts = re.split(union_pattern, text)
        if self.detailed and len(parts) > 1:
            part_count = 0
            for part in parts:
                if union_pattern.search(part):
                    continue
                part_count += 1
                part_id = self._next_id()
                part_node = Node(id=part_id, name="Часть_" + str(part_count),
                                 text=part, type="sub_query")
                part_node.is_union_part = True
                clean = re.sub(r'^\s*\(', '', part)
                clean = re.sub(r'\)\s*(?:(?:КАК|AS)\s+\S+)?\s*$', '', clean)
                part_node.own_in_tables = get_own_in_tables(clean)
                self._nodes.append(part_node)
                node.children.append(part_node)
            node.text = text
        else:
            clean = re.sub(r'^\s*\(', '', text)
            clean = re.sub(r'\)\s*(?:(?:КАК|AS)\s+\S+)?\s*$', '', clean)
            node.own_in_tables = get_own_in_tables(clean)
            node.text = text

    def _set_parent(self, node: Node, parent: Node):
        node.parent = parent
        for child in node.children:
            self._set_parent(child, node)

    def _set_max_parent(self, root: Node):
        stack = [root]
        while stack:
            current = stack.pop()
            current.max_parent = root
            stack.extend(current.children)

    def _build_edges(self) -> list:
        edges = []
        for src in self._nodes:
            if src.type != "temp_query":
                continue
            has_out = False
            for dst in self._nodes:
                if src.name.upper() in dst.own_in_tables:
                    edges.append(Edge(out_node=src, in_node=dst))
                    has_out = True
            src.is_stub = not has_out
        return edges

    def _node_to_dict(self, node: Node) -> dict:
        return {
            "id": node.id,
            "name": node.name,
            "type": node.type,
            "text": node.text.strip(),
            "parent_id": node.parent.id if node.parent else None,
            "max_parent_id": node.max_parent.id if node.max_parent else None,
            "children_ids": [c.id for c in node.children],
            "own_in_tables": node.own_in_tables,
            "is_stub": node.is_stub,
            "is_union_part": node.is_union_part,
        }

    def _to_json(self, edges: list) -> dict:
        return {
            "nodes": [self._node_to_dict(n) for n in self._nodes],
            "edges": [
                {
                    "from": e.out_node.id,
                    "from_name": e.out_node.name,
                    "to": e.in_node.id,
                    "to_name": e.in_node.name,
                }
                for e in edges
            ],
            "drop_queries": self._drop_queries,
        }


def analyze_sql_query(sql_text: str, detailed: bool = False) -> str:
    """
    Разбирает SQL/1C-запрос и возвращает JSON-строку.

    Параметры
    ---------
    sql_text : str
        Текст запроса (1C BSL или стандартный SQL).
    detailed : bool
        True — ОБЪЕДИНИТЬ/UNION разбивается на дочерние узлы Часть_N.

    Возвращает
    ----------
    str
        JSON-строка (схема описана в docstring модуля).
    """
    analyzer = SqlQueryAnalyzer(detailed=detailed)
    result = analyzer.analyze(sql_text)
    return json.dumps(result, ensure_ascii=False, indent=2)
