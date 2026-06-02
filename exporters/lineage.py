"""
exporters/lineage.py
====================
Итерация 4 — трассировка происхождения полей.

Что генерирует:
  tables/fields.csv             — реестр полей всех узлов
  tables/expressions.csv        — сложные вычисляемые выражения
  tables/conditions.csv         — WHERE / JOIN ON
  tables/joins.csv              — карта соединений
  lineage/field_lineage.json    — цепочки от финального поля до физической таблицы
  lineage/lineage_key_fields.json — цепочки для ключевых полей из extractor.yaml
  lineage/field_mapping.csv     — прямое сопоставление output → input
  lineage/dependency_matrix.csv — pivot-матрица зависимостей узлов

Зависимость: generate_tables(model, output_dir) должен быть вызван раньше,
             т.к. используется tables/edges_refs.csv для построения цепочек.

Известные ограничения:
  - parse_select_list — regex-парсер; ВЫБОР КОГДА и вложенные функции
    помечаются is_computed=True без глубокого разбора выражения.
  - ТабА.* → source_field="*", lineage не строится.
  - alias_map строится regex-парсингом FROM/JOIN; отсутствие явного алиаса
    → имя таблицы используется как алиас.
  - Циклы ограничены max_depth=20.
  - extractor.yaml опционален; при отсутствии key_fields = все поля финала.

ВОЗМОЖНЫЕ ОШИБКИ (зафиксированы в debug/iteration_04.md):
  1. generate_lineage вызывается без предварительного generate_tables —
     edges_refs.csv будет отсутствовать, цепочки не построятся.
  2. Для ЕСТЬНУЛЛ/ISNULL source_table — алиас ("Д"), а не полное имя таблицы.
     Проверить, что alias_map разрешает алиас → имя ВТ перед записью в fields.csv.
  3. field_lineage.json — корень должен быть list[], НЕ dict.
     Проверить тип перед json.dump.
  4. dependency_matrix.csv — матрица НЕ квадратная по спецификации:
     строки = только зависимые узлы, столбцы = все узлы-источники.
     Диагональ проверять только если row_id in col_ids.
  5. Поле final_node_id обязательно в каждом entry field_lineage.json.
  6. chain[-1] идентифицируется по node_id == null (не по source_kind).
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

MAX_DEPTH = 20

# Агрегатные функции 1С/SQL
_AGGREGATE_FUNCS = {
    "СУММА", "КОЛИЧЕСТВО", "МАКСИМУМ", "МИНИМУМ", "СРЕДНЕЕ",
    "SUM", "COUNT", "MAX", "MIN", "AVG",
}

# Типы вычисляемых выражений
_EXPR_TYPES = {
    "ЕСТЬНУЛЛ": "ISNULL",   "ISNULL": "ISNULL",
    "ВЫБОР":   "CASE",      "CASE":   "CASE",
    "ПОДСТРОКА": "SUBSTRING", "SUBSTRING": "SUBSTRING",
    "ВЫРАЗИТЬ": "CAST",     "CAST": "CAST",
}

# JOIN-ключевые слова 1С/SQL (порядок важен — длинные раньше)
_JOIN_TYPES_RE = re.compile(
    r"(ПОЛНОЕ\s+ВНЕШНЕЕ|ЛЕВОЕ\s+ВНЕШНЕЕ|ПРАВОЕ\s+ВНЕШНЕЕ|ВНУТРЕННЕЕ|ПОЛНОЕ|ЛЕВОЕ|ПРАВОЕ|CROSS)\s+СОЕДИНЕНИЕ"
    r"|(FULL\s+OUTER|LEFT\s+OUTER|RIGHT\s+OUTER|INNER|FULL|LEFT|RIGHT|CROSS)\s+JOIN",
    re.IGNORECASE
)

_JOIN_TYPE_NORM = {
    "ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ": "FULL JOIN",
    "ЛЕВОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ":  "LEFT JOIN",
    "ПРАВОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ": "RIGHT JOIN",
    "ВНУТРЕННЕЕ СОЕДИНЕНИЕ":     "INNER JOIN",
    "ПОЛНОЕ СОЕДИНЕНИЕ":         "FULL JOIN",
    "ЛЕВОЕ СОЕДИНЕНИЕ":          "LEFT JOIN",
    "ПРАВОЕ СОЕДИНЕНИЕ":         "RIGHT JOIN",
    "CROSS СОЕДИНЕНИЕ":          "CROSS JOIN",
    "FULL OUTER JOIN":            "FULL JOIN",
    "LEFT OUTER JOIN":            "LEFT JOIN",
    "RIGHT OUTER JOIN":           "RIGHT JOIN",
    "INNER JOIN":                 "INNER JOIN",
    "FULL JOIN":                  "FULL JOIN",
    "LEFT JOIN":                  "LEFT JOIN",
    "RIGHT JOIN":                 "RIGHT JOIN",
    "CROSS JOIN":                 "CROSS JOIN",
}


# ---------------------------------------------------------------------------
# parse_select_list
# ---------------------------------------------------------------------------

def parse_select_list(node_text: str) -> list[dict]:
    """
    Разбирает SELECT/ВЫБРАТЬ-список из полного текста узла.

    Возвращает список dict:
        field_ordinal  int
        field_alias    str        # псевдоним или имя поля
        expression     str        # исходный текст выражения
        source_table   str|None   # алиас таблицы
        source_field   str|None   # имя поля
        is_computed    bool

    ВОЗМОЖНЫЕ ОШИБКИ:
      - ВЫБОР КОГДА / CASE WHEN: распознаётся как is_computed=True,
        но source_table/source_field = None (выражение не раскрывается).
      - Вложенные функции: ЕСТЬНУЛЛ(СУММА(Т.П),0) — source_field берётся
        из первого найденного Таблица.Поле внутри, что может быть неточно.
      - ТабА.* → source_field="*", is_computed=False, alias="*".
      - Без явного КАК/AS alias = имя поля (последний компонент после точки).
    """
    text = node_text.strip()

    # Найти блок ВЫБРАТЬ ... ИЗ  (или ВЫБРАТЬ ... без ИЗ)
    select_match = re.search(
        r"(?i)(?:ВЫБРАТЬ|SELECT)\s+(РАЗЛИЧНЫЕ\s+)?(.+?)(?=\s+(?:ИЗ|FROM|ГДЕ|WHERE|СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЯ|HAVING|$))",
        text,
        re.DOTALL,
    )
    if not select_match:
        return []

    select_body = select_match.group(2).strip()
    raw_fields = _split_select_fields(select_body)

    result = []
    for ordinal, raw in enumerate(raw_fields):
        raw = raw.strip()
        if not raw:
            continue
        result.append(_parse_one_field(ordinal, raw))
    return result


def _split_select_fields(body: str) -> list[str]:
    """Разбивает список полей по запятой с учётом скобок."""
    fields, depth, buf = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        fields.append("".join(buf))
    return fields


def _parse_one_field(ordinal: int, raw: str) -> dict:
    """Парсит одно поле SELECT."""
    # КАК/AS алиас — только на верхнем уровне (не внутри скобок)
    alias = None
    expression = raw
    as_match = _top_level_as(raw)
    if as_match:
        expression = raw[: as_match.start()].strip()
        alias = as_match.group(1).strip()

    upper_expr = expression.upper().strip()
    is_computed = False
    source_table = None
    source_field = None

    # ВЫБОР КОГДА / CASE WHEN
    if re.match(r"(?i)ВЫБОР\b|CASE\b", upper_expr):
        is_computed = True
        if alias is None:
            alias = "_case_"

    # Агрегат
    elif re.match(r"(?i)(" + "|".join(_AGGREGATE_FUNCS) + r")\s*\(", upper_expr):
        is_computed = True
        inner = re.search(r"\((.+?)\)", expression, re.DOTALL)
        if inner:
            tp = _extract_table_field(inner.group(1).strip())
            source_table, source_field = tp
        if alias is None:
            alias = expression.split("(")[0].strip()

    # ЕСТЬНУЛЛ / ISNULL / другие функции с Таблица.Поле внутри
    elif re.match(r"(?i)(ЕСТЬНУЛЛ|ISNULL|ПОДСТРОКА|SUBSTRING|ВЫРАЗИТЬ|CAST)\s*\(", upper_expr):
        is_computed = True
        inner = re.search(r"\((.+)", expression, re.DOTALL)
        if inner:
            first_arg = inner.group(1).split(",")[0].strip().rstrip(")")
            tp = _extract_table_field(first_arg)
            source_table, source_field = tp
        if alias is None:
            alias = expression.split("(")[0].strip()

    # Функция общего вида
    elif re.search(r"(?i)\w+\s*\(", upper_expr):
        is_computed = True
        if alias is None:
            alias = expression.split("(")[0].strip()

    # Звёздочка ТабА.* — проверяем раньше арифметики, иначе .* попадёт под * в [+\-*/]
    elif upper_expr.endswith(".*"):
        parts = expression.strip().split(".")
        source_table = parts[0].strip() if len(parts) >= 2 else None
        source_field = "*"
        alias = alias or "*"

    # Арифметика
    elif re.search(r"[+\-*/]", expression):
        is_computed = True

    # Литерал (число, строка, булево, параметр)
    elif re.match(r"^[0-9]", upper_expr) or upper_expr.startswith(("'", '"', "&", ":")):
        is_computed = True

    # Простая ссылка Таблица.Поле
    elif "." in expression:
        tp = _extract_table_field(expression)
        source_table, source_field = tp
        if alias is None and source_field:
            alias = source_field

    # Одиночное имя (без точки)
    else:
        source_field = expression.strip()
        if alias is None:
            alias = source_field

    # Нормализуем alias
    if alias is None:
        alias = expression.strip()

    return {
        "field_ordinal": ordinal,
        "field_alias":   alias.strip(),
        "expression":    expression.strip(),
        "source_table":  source_table.strip() if source_table else None,
        "source_field":  source_field.strip() if source_field else None,
        "is_computed":   is_computed,
    }


def _top_level_as(text: str):
    """Ищет КАК/AS на верхнем уровне (не внутри скобок)."""
    depth = 0
    for m in re.finditer(r"[()]|\b(?:КАК|AS)\b", text, re.IGNORECASE):
        ch = m.group(0)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            rest = text[m.end():].strip()
            alias_m = re.match(r"([\w\u0400-\u04FFА-Яа-яЁё_]+)", rest)
            if alias_m:
                return type("M", (), {"start": lambda s, i=m.start(): i,
                                      "end":   lambda s, i=m.end(): i,
                                      "group": lambda s, g=1, a=alias_m: a.group(g)})()
    return None


def _extract_table_field(expr: str) -> tuple[str | None, str | None]:
    """Извлекает (таблица, поле) из выражения вида Таблица.Поле."""
    m = re.match(r"([\w\u0400-\u04FFА-Яа-яЁё_]+)\.([\w\u0400-\u04FFА-Яа-яЁё_*]+)", expr.strip())
    if m:
        return m.group(1), m.group(2)
    return None, None


# ---------------------------------------------------------------------------
# Вспомогательные парсеры FROM / JOIN / WHERE
# ---------------------------------------------------------------------------

def _parse_alias_map(node_text: str, own_in_tables: list[str]) -> dict[str, str]:
    """
    Строит alias_map: алиас → имя ВТ (из own_in_tables).

    ВОЗМОЖНАЯ ОШИБКА:
      Если таблица без явного алиаса — её имя используется как алиас.
      Если aliases совпадают у разных таблиц — побеждает последний.
    """
    alias_map: dict[str, str] = {}
    upper_tables = {t.upper(): t for t in own_in_tables}

    pattern = re.compile(
        r"(?i)(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+([\w.~]+)(?:\s+(?:КАК|AS)\s+([\w]+))?",
        re.DOTALL,
    )
    for m in pattern.finditer(node_text):
        table_name = m.group(1).strip()
        alias      = (m.group(2) or table_name).strip()
        # проверяем, есть ли table_name в own_in_tables (без учёта регистра)
        upper_tname = table_name.upper()
        canonical = upper_tables.get(upper_tname)
        if canonical:
            alias_map[alias.upper()] = canonical

    return alias_map


def _parse_joins(node_id: int, node_name: str, node_text: str) -> list[dict]:
    """Извлекает JOIN-записи для joins.csv."""
    joins = []
    pattern = re.compile(
        r"(?i)((?:ПОЛНОЕ\s+ВНЕШНЕЕ|ЛЕВОЕ\s+ВНЕШНЕЕ|ПРАВОЕ\s+ВНЕШНЕЕ|ВНУТРЕННЕЕ|ПОЛНОЕ|ЛЕВОЕ|ПРАВОЕ|CROSS)\s+СОЕДИНЕНИЕ"
        r"|(?:FULL\s+OUTER|LEFT\s+OUTER|RIGHT\s+OUTER|INNER|FULL|LEFT|RIGHT|CROSS)\s+JOIN)"
        r"\s+([\w.~]+)(?:\s+(?:КАК|AS)\s+([\w]+))?\s+(?:ПО|ON)\s+(.+?)(?=\n|$|"
        r"(?:ПОЛНОЕ|ЛЕВОЕ|ПРАВОЕ|ВНУТРЕННЕЕ|LEFT|RIGHT|INNER|FULL|CROSS|ГДЕ|WHERE|СГРУППИРОВАТЬ|GROUP))",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(node_text):
        raw_jtype = " ".join(m.group(1).upper().split())
        join_type = _JOIN_TYPE_NORM.get(raw_jtype, raw_jtype)
        right_src   = m.group(2).strip()
        right_alias = (m.group(3) or right_src).strip()
        on_expr     = m.group(4).strip()
        joins.append({
            "node_id":     node_id,
            "node_name":   node_name,
            "join_type":   join_type,
            "left_source":  "",   # заполняется по контексту FROM
            "left_alias":   "",
            "right_source": right_src,
            "right_alias":  right_alias,
            "on_expression": on_expr,
        })
    return joins


def _parse_conditions(node_id: int, node_name: str, node_text: str) -> list[dict]:
    """Извлекает WHERE/JOIN ON условия для conditions.csv."""
    conditions = []
    # WHERE
    where_m = re.search(r"(?i)(?:ГДЕ|WHERE)\s+(.+?)(?=\n\s*(?:СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЯ|HAVING|$))",
                        node_text, re.DOTALL)
    if where_m:
        expr = where_m.group(1).strip()
        tables = list({m.group(1) for m in re.finditer(r"([\w\u0400-\u04FFА-Яа-яЁё_]+)\.", expr)})
        conditions.append({
            "node_id":           node_id,
            "node_name":         node_name,
            "condition_type":    "WHERE",
            "expression":        expr,
            "involved_tables":   ";".join(tables),
            "involves_parameter": str(bool(re.search(r"[&:][\w]+", expr))).lower(),
        })
    # JOIN ON
    for m in re.finditer(r"(?i)(?:ПО|ON)\s+(.+?)(?=\n|$|(?:ГДЕ|WHERE|СОЕДИНЕНИЕ|JOIN))",
                         node_text, re.DOTALL):
        expr = m.group(1).strip()
        tables = list({m2.group(1) for m2 in re.finditer(r"([\w\u0400-\u04FFА-Яа-яЁё_]+)\.", expr)})
        conditions.append({
            "node_id":           node_id,
            "node_name":         node_name,
            "condition_type":    "JOIN_ON",
            "expression":        expr,
            "involved_tables":   ";".join(tables),
            "involves_parameter": str(bool(re.search(r"[&:][\w]+", expr))).lower(),
        })
    return conditions


def _parse_expressions(node_id: int, node_name: str, fields: list[dict]) -> list[dict]:
    """Извлекает сложные вычисляемые выражения для expressions.csv."""
    exprs = []
    for i, f in enumerate(fields):
        if not f["is_computed"]:
            continue
        expr_text = f["expression"]
        upper = expr_text.upper().strip()
        expr_type = "FUNCTION"  # fallback
        for kw, etype in _EXPR_TYPES.items():
            if upper.startswith(kw):
                expr_type = etype
                break
        else:
            for agg in _AGGREGATE_FUNCS:
                if upper.startswith(agg):
                    expr_type = "AGGREGATE"
                    break
            else:
                if re.search(r"[+\-*/]", expr_text):
                    expr_type = "ARITHMETIC"
                elif re.match(r"[&:]", expr_text.strip()):
                    expr_type = "PARAMETER"
        exprs.append({
            "node_id":      node_id,
            "node_name":    node_name,
            "expr_type":    expr_type,
            "expr_text":    expr_text,
            "output_alias": f["field_alias"],
            "line":         i + 1,
        })
    return exprs


# ---------------------------------------------------------------------------
# Построение цепочек lineage
# ---------------------------------------------------------------------------

def _build_ref_index(edges: list[dict]) -> dict[str, list[dict]]:
    """
    Строит индекс рёбер по to_name для быстрого поиска источника.
    Возвращает: {to_name_upper: [edge, ...]}

    ВОЗМОЖНАЯ ОШИБКА:
      edges содержит только relation="ref" (data-flow).
      Структурные рёбра (parent_child, union_part) не используются для lineage.
    """
    index: dict[str, list[dict]] = {}
    for e in edges:
        if e.get("relation") == "ref":
            key = e["to_name"].upper()
            index.setdefault(key, []).append(e)
    return index


def _build_node_index(nodes: list[dict]) -> dict[int, dict]:
    return {n["id"]: n for n in nodes}


def _trace_field(
    field_alias: str,
    source_table_alias: str | None,
    source_field: str | None,
    start_node: dict,
    alias_map: dict[str, str],
    ref_index: dict[str, list[dict]],
    node_index: dict[int, dict],
    depth: int = 0,
) -> list[dict]:
    """
    Рекурсивно трассирует поле до физической таблицы.

    Возвращает chain[] согласно спецификации:
      промежуточные: {node_id, node_name, alias, expr}
      финальное:     {node_id: null, node_name: null, source_table, source_field}

    ВОЗМОЖНЫЕ ОШИБКИ:
      - Если alias_map не содержит source_table_alias — цепочка обрывается.
      - Если поле переименовано (КАК) — source_field в следующем узле
        ищется по field_alias текущего узла, что корректно только для
        прямых переносов; вычисляемые поля не трассируются глубже.
      - При depth >= MAX_DEPTH возвращается текущая цепочка как есть
        (неполная — без финального физического звена).
    """
    if depth >= MAX_DEPTH:
        return []

    step = {
        "node_id":   start_node["id"],
        "node_name": start_node["name"],
        "alias":     field_alias,
        "expr":      f"{source_table_alias}.{source_field}" if source_table_alias and source_field else field_alias,
    }

    if source_table_alias is None or source_field is None:
        # вычисляемое выражение — цепочка заканчивается здесь без физического звена
        return [step]

    # Разрешаем алиас → имя ВТ
    vt_name = alias_map.get(source_table_alias.upper())
    if vt_name is None:
        # source_table_alias не является ВТ — это физическая таблица
        return [
            step,
            {"node_id": None, "node_name": None,
             "source_table": source_table_alias, "source_field": source_field},
        ]

    # Ищем узел-источник по имени ВТ в ref-рёбрах
    candidates = ref_index.get(vt_name.upper(), [])
    if not candidates:
        # ВТ есть, но нет входящего ребра — завершаем
        return [
            step,
            {"node_id": None, "node_name": None,
             "source_table": vt_name, "source_field": source_field},
        ]

    # Берём первый (обычно единственный) источник
    src_edge = candidates[0]
    src_node = node_index.get(src_edge["from_id"])
    if src_node is None:
        return [step]

    # Ищем поле source_field в SELECT src_node
    src_alias_map = _parse_alias_map(src_node.get("text", ""), src_node.get("own_in_tables", []))
    src_fields = parse_select_list(src_node.get("text", ""))

    matched = next(
        (f for f in src_fields if f["field_alias"].upper() == source_field.upper()),
        None,
    )
    if matched is None:
        # поле не найдено в источнике — конечная точка
        return [
            step,
            {"node_id": None, "node_name": None,
             "source_table": vt_name, "source_field": source_field},
        ]

    tail = _trace_field(
        field_alias=matched["field_alias"],
        source_table_alias=matched["source_table"],
        source_field=matched["source_field"],
        start_node=src_node,
        alias_map=src_alias_map,
        ref_index=ref_index,
        node_index=node_index,
        depth=depth + 1,
    )
    return [step] + tail


# ---------------------------------------------------------------------------
# Матрица зависимостей
# ---------------------------------------------------------------------------

def _build_dependency_matrix(nodes: list[dict], edges: list[dict]) -> tuple[list[int], dict[int, dict[int, int]]]:
    """
    Строит pivot-матрицу зависимостей.

    Возвращает:
      col_ids  — список всех node_id (заголовки столбцов)
      matrix   — {row_node_id: {col_node_id: 0|1}}

    Строки = узлы, от которых кто-то зависит (зависимые).
    Столбцы = все узлы-источники (могут не совпадать со строками).

    ВОЗМОЖНАЯ ОШИБКА:
      Матрица НЕ квадратная по спецификации — не все узлы присутствуют
      одновременно и в строках, и в столбцах.
      Диагональ 0 проверяется только если node присутствует в обеих осях.
    """
    all_ids = sorted({n["id"] for n in nodes})
    ref_edges = [e for e in edges if e.get("relation") == "ref"]

    # Строки = узлы, которые ЗАВИСЯТ от кого-то (имеют входящие ref-рёбра)
    dependent_ids = sorted({e["to_id"] for e in ref_edges})

    matrix: dict[int, dict[int, int]] = {}
    for did in dependent_ids:
        row: dict[int, int] = {cid: 0 for cid in all_ids}
        # прямые зависимости
        for e in ref_edges:
            if e["to_id"] == did:
                row[e["from_id"]] = 1
        # диагональ = 0 (нет самозависимости)
        if did in row:
            row[did] = 0
        matrix[did] = row

    return all_ids, matrix


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def generate_lineage(model: dict[str, Any], output_dir: str) -> None:
    """
    Генерирует все файлы итерации 4.

    Args:
        model:      нормализованная модель из exporters.normalizer.normalize()
        output_dir: корневая папка для записи файлов

    ВОЗМОЖНАЯ ОШИБКА (критичная):
        generate_tables(model, output_dir) должен быть вызван ДО generate_lineage,
        т.к. для построения цепочек используется edges из model["edges"],
        которые должны быть полными (включая ref-рёбра).
        Если model не содержит нормализованных edges — цепочки не построятся.
    """
    nodes: list[dict] = model["nodes"]
    edges: list[dict] = model["edges"]

    ref_index  = _build_ref_index(edges)
    node_index = _build_node_index(nodes)

    tables_dir  = os.path.join(output_dir, "tables")
    lineage_dir = os.path.join(output_dir, "lineage")
    os.makedirs(tables_dir,  exist_ok=True)
    os.makedirs(lineage_dir, exist_ok=True)

    all_fields:      list[dict] = []
    all_expressions: list[dict] = []
    all_conditions:  list[dict] = []
    all_joins:       list[dict] = []

    for node in nodes:
        nid   = node["id"]
        nname = node["name"]
        text  = node.get("text", "")
        own   = node.get("own_in_tables", [])

        fields = parse_select_list(text)
        for f in fields:
            all_fields.append({
                "node_id":      nid,
                "node_name":    nname,
                "field_ordinal": f["field_ordinal"],
                "field_alias":   f["field_alias"],
                "expression":    f["expression"],
                "source_table":  f["source_table"] or "",
                "source_field":  f["source_field"] or "",
                "is_computed":   str(f["is_computed"]).lower(),
            })

        all_expressions.extend(_parse_expressions(nid, nname, fields))
        all_conditions.extend(_parse_conditions(nid, nname, text))
        joins = _parse_joins(nid, nname, text)
        # Заполнить left_source из FROM
        from_m = re.search(r"(?i)(?:ИЗ|FROM)\s+([\w.~]+)(?:\s+(?:КАК|AS)\s+([\w]+))?", text)
        if from_m and joins:
            ls = from_m.group(1).strip()
            la = (from_m.group(2) or ls).strip()
            for j in joins:
                j["left_source"] = ls
                j["left_alias"]  = la
        all_joins.extend(joins)

    # --- tables/fields.csv ---
    _write_csv(
        os.path.join(tables_dir, "fields.csv"),
        ["node_id", "node_name", "field_ordinal", "field_alias",
         "expression", "source_table", "source_field", "is_computed"],
        all_fields,
    )

    # --- tables/expressions.csv ---
    _write_csv(
        os.path.join(tables_dir, "expressions.csv"),
        ["node_id", "node_name", "expr_type", "expr_text", "output_alias", "line"],
        all_expressions,
    )

    # --- tables/conditions.csv ---
    _write_csv(
        os.path.join(tables_dir, "conditions.csv"),
        ["node_id", "node_name", "condition_type", "expression",
         "involved_tables", "involves_parameter"],
        all_conditions,
    )

    # --- tables/joins.csv ---
    _write_csv(
        os.path.join(tables_dir, "joins.csv"),
        ["node_id", "node_name", "join_type", "left_source", "left_alias",
         "right_source", "right_alias", "on_expression"],
        all_joins,
    )

    # --- field_lineage.json ---
    # Финальный узел: последний temp_query без исходящих ref-рёбер
    final_node = _find_final_node(nodes, edges)
    lineage_list: list[dict] = []
    field_mapping_rows: list[dict] = []

    if final_node:
        fn_alias_map = _parse_alias_map(
            final_node.get("text", ""),
            final_node.get("own_in_tables", []),
        )
        fn_fields = parse_select_list(final_node.get("text", ""))

        for f in fn_fields:
            chain = _trace_field(
                field_alias=f["field_alias"],
                source_table_alias=f["source_table"],
                source_field=f["source_field"],
                start_node=final_node,
                alias_map=fn_alias_map,
                ref_index=ref_index,
                node_index=node_index,
            )
            entry = {
                "output_field": f["field_alias"],
                "final_node_id": final_node["id"],   # ОБЯЗАТЕЛЬНОЕ ПОЛЕ
                "chain": chain,
                "depth": len(chain),
            }
            lineage_list.append(entry)

            # field_mapping row
            intermediate_id = chain[1]["node_id"] if len(chain) > 1 and chain[1].get("node_id") else ""
            last = chain[-1] if chain else {}
            rule = "computed" if f["is_computed"] else "direct"
            field_mapping_rows.append({
                "output_field":        f["field_alias"],
                "final_node_id":       final_node["id"],
                "intermediate_node_id": intermediate_id,
                "input_field":         last.get("source_field") or f["source_field"] or "",
                "rule_type":           rule,
                "transform_desc":      f["expression"] if f["is_computed"] else "Прямой перенос",
            })

    # ВОЗМОЖНАЯ ОШИБКА: корень field_lineage.json должен быть list[], не dict
    with open(os.path.join(lineage_dir, "field_lineage.json"), "w", encoding="utf-8") as fh:
        json.dump(lineage_list, fh, ensure_ascii=False, indent=2)

    # --- lineage/field_mapping.csv ---
    _write_csv(
        os.path.join(lineage_dir, "field_mapping.csv"),
        ["output_field", "final_node_id", "intermediate_node_id",
         "input_field", "rule_type", "transform_desc"],
        field_mapping_rows,
    )

    # --- lineage/lineage_key_fields.json ---
    key_fields = _build_key_fields(lineage_list, output_dir)
    with open(os.path.join(lineage_dir, "lineage_key_fields.json"), "w", encoding="utf-8") as fh:
        json.dump(key_fields, fh, ensure_ascii=False, indent=2)

    # --- lineage/dependency_matrix.csv ---
    col_ids, matrix = _build_dependency_matrix(nodes, edges)
    dependent_ids = sorted(matrix.keys())
    with open(os.path.join(lineage_dir, "dependency_matrix.csv"), "w",
              newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["node_id"] + [str(c) for c in col_ids])
        for rid in dependent_ids:
            row = matrix[rid]
            writer.writerow([str(rid)] + [str(row.get(c, 0)) for c in col_ids])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _find_final_node(nodes: list[dict], edges: list[dict]) -> dict | None:
    """
    Возвращает финальный узел: temp_query без исходящих ref-рёбер.
    Если таких несколько — берётся с максимальным id.
    """
    out_ids = {e["from_id"] for e in edges if e.get("relation") == "ref"}
    candidates = [
        n for n in nodes
        if n.get("type") == "temp_query" and n["id"] not in out_ids
    ]
    return max(candidates, key=lambda n: n["id"]) if candidates else None


def _build_key_fields(lineage_list: list[dict], output_dir: str) -> dict:
    """
    Формирует lineage_key_fields.json.
    Читает ключевые поля из extractor.yaml (если есть),
    иначе включает все поля из lineage_list.
    """
    yaml_path = os.path.join(output_dir, "extractor.yaml")
    key_field_names: list[str] | None = None

    if os.path.exists(yaml_path):
        try:
            import yaml  # опциональная зависимость
            with open(yaml_path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh)
            key_field_names = cfg.get("key_fields", None)
        except Exception:
            pass

    key_entries: list[dict] = []
    for entry in lineage_list:
        fname = entry["output_field"]
        if key_field_names is not None and fname not in key_field_names:
            continue
        # branching = True если в chain более одного промежуточного звена
        # с разными source_table (поле проходит через разные ВТ)
        intermediate = [s for s in entry["chain"] if s.get("node_id") is not None]
        branching = len({s.get("expr", "").split(".")[0] for s in intermediate if s.get("expr")}) > 1
        key_entries.append({
            "field":       fname,
            "description": "",
            "chain":       entry["chain"],
            "branching":   branching,  # ДОЛЖЕН быть bool, не str
            "notes":       "",
        })

    source_file = os.path.basename(output_dir) or ""
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "source_file":  source_file,
        "key_fields":   key_entries,
    }


def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
