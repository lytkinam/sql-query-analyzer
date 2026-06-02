"""
exporters/texts.py
==================
Итерация 2: тексты узлов.

Выходные файлы (в output_dir):

  query_texts/
    node_{id}.sql          — текст узла с шапкой-комментарием
    node_{id}.md           — Markdown с метаданными
    texts_index.json       — каталог файлов: node_id, name, path, text_len, text_hash, line_count
    normalized_queries.sql — все ВТ подряд с разделителями

Использование
-------------
    from exporters.normalizer import normalize
    from exporters.texts import generate_texts
    import json

    raw = json.loads(analyze_sql_query(sql_text, detailed=True))
    model = normalize(raw)
    generate_texts(model, "./output")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any


# ---------------------------------------------------------------------------
# Ключевые слова 1С SQL (для нормализации регистра)
# ---------------------------------------------------------------------------

_SQL_KEYWORDS_1C = [
    "ВЫБРАТЬ", "ИЗ", "ГДЕ", "И", "ИЛИ",
    "НЕ", "НЕ В ", "ДА", "НЕТ",
    "СГРУППИРОВАТЬ ПО", "УПОРЯДОЧИТЬ ПО", "ИМЕЮЦИЙ",
    "ЛЕВОЕ СОЕДИНЕНИЕ", "ПРАВОЕ СОЕДИНЕНИЕ",
    "ВНУТРЕННЕЕ СОЕДИНЕНИЕ", "ПОЛНОЕ СОЕДИНЕНИЕ",
    "СОЕДИНЕНИЕ", "ОБЪЕДИНИТЬ", "ОБЪЕДИНИТЬ ВСЕ",
    "ПОМЕСТИТЬ", "КАК", "ИСТИНА", "ЛОЖЬ",
    "НУЛЬ", "ЕСТЬ НУЛЬ", "НЕ ЕСТЬ НУЛЬ",
    "ВЫБОР", "КОГДА", "ТОГДА", "ИНАЧЕ", "КОНЕЦ",
    "МЕЖДУ", "ПОДОБНО", "В ", "ИНОГО ТИПА",
    "РАЗРЕШИТЬ", "ИТОГО", "ССЫЛКА", "КАТАЛОГ",
    "ТИПЗНАЧЕНИЕ",
    # SQL-ключевые (ANSI)
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "FULL", "OUTER",
    "GROUP BY", "ORDER BY", "HAVING", "UNION", "UNION ALL", "INTO",
    "AND", "OR", "NOT", "NULL", "IS NULL", "IS NOT NULL",
    "CASE", "WHEN", "THEN", "ELSE", "END",
    "BETWEEN", "LIKE", "IN", "EXISTS", "AS",
    "TRUE", "FALSE",
]

# Сортируем по длине (длинные — первыми, чтобы не перекрывали короткие)
_SORTED_KEYWORDS = sorted(_SQL_KEYWORDS_1C, key=len, reverse=True)


def normalize_sql(text: str) -> str:
    """
    Нормализация SQL-текста:
    - Ключевые слова → верхний регистр
    - Лишние пробелы/табы → один пробел
    - Обрезать пустые строки
    """
    if not text:
        return ""

    result = text
    for kw in _SORTED_KEYWORDS:
        # \b не работает с кириллицей, поэтому используем lookahead/lookbehind
        pattern = r"(?<![\w\u0400-\u04ff])" + re.escape(kw) + r"(?![\w\u0400-\u04ff])"
        result = re.sub(pattern, kw.upper(), result, flags=re.IGNORECASE | re.UNICODE)

    # Лишние пробелы и табуляции
    result = re.sub(r"[ \t]+", " ", result)
    # Обрезать более 2 подряд пустых строк
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------
# query_texts/node_{id}.sql
# ---------------------------------------------------------------------------

def _render_sql_header(node: dict, nodes_by_id: dict) -> str:
    """Шапка SQL-файла."""
    parent_id = node.get("parent_id")
    parent_name = ""
    if parent_id is not None:
        pnode = nodes_by_id.get(parent_id)
        parent_name = pnode["name"] if pnode else str(parent_id)

    own_tables = node.get("own_in_tables", [])
    tables_str = ", ".join(own_tables) if own_tables else "нет"

    lines = [
        f"-- Node ID: {node['id']}",
        f"-- Name: {node['name'] or '(unnamed)'}",
        f"-- Type: {node['type']}",
        f"-- Parent: {parent_name or 'null'}",
        f"-- OwnInTables: {tables_str}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# query_texts/node_{id}.md
# ---------------------------------------------------------------------------

def _render_md(node: dict, nodes_by_id: dict) -> str:
    """Рендерит Markdown-файл узла."""
    name = node["name"] or "(unnamed)"
    nid = node["id"]
    ntype = node["type"]

    parent_id = node.get("parent_id")
    if parent_id is None:
        parent_str = "нет (корневая ВТ)"
    else:
        pnode = nodes_by_id.get(parent_id)
        parent_str = pnode["name"] if pnode else str(parent_id)

    children_ids = node.get("children_ids", [])
    children_str = ", ".join(str(c) for c in children_ids) if children_ids else "нет"

    own_tables = node.get("own_in_tables", [])
    sources_str = ", ".join(own_tables) if own_tables else "нет"

    text = node.get("text", "") or ""
    text_block = text.strip() if text.strip() else "(text not available)"

    parts = [
        f"# {name} (id: {nid})",
        "",
        f"**Тип:** {ntype}  ",
        f"**Родитель:** {parent_str}  ",
        f"**Дети:** [{children_str}]  ",
        f"**Источники:** {sources_str}  ",
        "",
        "## Текст запроса",
        "",
        "```sql",
        text_block,
        "```",
        "",
        "## Аннотации",
        "",
        "<!-- TODO: добавьте комментарий -->",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# query_texts/normalized_queries.sql
# ---------------------------------------------------------------------------

def _render_normalized_all(nodes: list[dict]) -> str:
    """
    Все узлы (только temp_query) в один файл с разделителями.
    sub_query включаем только если они являются частью UNION.
    """
    blocks = []
    for n in nodes:
        if n["type"] not in ("temp_query", "sub_query"):
            continue
        name = n["name"] or f"node_{n['id']}"
        sep = f"-- ===== {name} (id={n['id']}) ====="
        text = n.get("text", "") or ""
        normalized = normalize_sql(text)
        blocks.append(sep)
        blocks.append(normalized)
        blocks.append("")
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def generate_texts(model: dict[str, Any], output_dir: str) -> None:
    """
    Генерирует все текстовые файлы итерации 2 в output_dir.

    Параметры
    ----------
    model : dict
        Нормализованная модель из exporters.normalizer.normalize().
    output_dir : str
        Путь к корневому каталогу вывода.
    """
    texts_dir = os.path.join(output_dir, "query_texts")
    _mkdir(texts_dir)

    nodes = model["nodes"]
    nodes_by_id: dict[int, dict] = {n["id"]: n for n in nodes}

    index: list[dict] = []

    for node in nodes:
        nid = node["id"]
        text = node.get("text", "") or ""

        # --- node_{id}.sql ---
        header = _render_sql_header(node, nodes_by_id)
        sql_content = header + "\n\n" + text.strip()
        sql_path = os.path.join(texts_dir, f"node_{nid}.sql")
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)

        # --- node_{id}.md ---
        md_content = _render_md(node, nodes_by_id)
        md_path = os.path.join(texts_dir, f"node_{nid}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # --- запись в индекс ---
        text_stripped = text.strip()
        line_count = len(text_stripped.splitlines()) if text_stripped else 0
        index.append({
            "node_id":    nid,
            "name":       node["name"] or "",
            "path":       f"query_texts/node_{nid}.sql",
            "text_len":   len(text_stripped),
            "text_hash":  _sha256(text_stripped),
            "line_count": line_count,
        })

    # --- texts_index.json ---
    index_path = os.path.join(texts_dir, "texts_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # --- normalized_queries.sql ---
    norm_sql = _render_normalized_all(nodes)
    norm_path = os.path.join(texts_dir, "normalized_queries.sql")
    with open(norm_path, "w", encoding="utf-8") as f:
        f.write(norm_sql)
