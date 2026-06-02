"""
exporters/normalizer.py
=======================
Нормализация сырого JSON из sql_query_analyzer → canonical model.

Что делает:
  - result → temp_query (тип финального запроса без ПОМЕСТИТЬ)
  - Добавляет relation в edges: ref / parent_child / union_part
  - Генерирует структурные рёбра из parent_id (их нет в сыром edges)
  - Ничего не меняет в именах полей (snake_case остаётся каноническим)

Использование
-------------
    from exporters.normalizer import normalize

    raw = json.loads(analyze_sql_query(sql_text, detailed=True))
    model = normalize(raw)
    # model['nodes'] — список узлов
    # model['edges'] — все рёбра (data-flow + структурные)
    # model['drop_queries'] — DROP-таблицы
"""

from __future__ import annotations
from typing import Any


# ---------------------------------------------------------------------------
# Классификация источников по 1С-префиксу
# ---------------------------------------------------------------------------

_SOURCE_KIND_MAP: list[tuple[str, str]] = [
    ("СПРАВОЧНИК.",              "Catalog"),
    ("РЕГИСТРНАКОПЛЕНИЯ.",       "AccumulationRegister"),
    ("РЕГИСТРСВЕДЕНИЙ.",         "InformationRegister"),
    ("ДОКУМЕНТ.",                "Document"),
    ("РЕГИСТРБУХГАЛТЕРИИ.",      "AccountingRegister"),
    ("РЕГИСТРРАСЧЕТА.",          "CalculationRegister"),
    ("ПЛАНВИДОВХАРАКТЕРИСТИК.",  "ChartOfCharacteristicTypes"),
    ("ПЛАНСЧЕТОВ.",              "ChartOfAccounts"),
    ("ПЛАНВИДОВРАСЧЕТА.",        "ChartOfCalculationTypes"),
    ("ПЕРЕЧИСЛЕНИЕ.",            "Enum"),
    ("БИЗНЕСПРОЦЕСС.",           "BusinessProcess"),
    ("ЗАДАЧА.",                  "Task"),
    ("ОБРАБОТКА.",               "DataProcessor"),
    ("ОТЧЕТ.",                   "Report"),
    ("КОНСТАНТА.",               "Constant"),
    ("ПОСЛЕДОВАТЕЛЬНОСТЬ.",      "Sequence"),
]


def classify_source(name: str) -> str:
    """Определяет source_kind по имени источника (1С-префикс или временная таблица)."""
    upper = name.upper()
    if upper.startswith(("ВТ_", "~TT~")):
        return "TempTable"
    for prefix, kind in _SOURCE_KIND_MAP:
        if upper.startswith(prefix):
            return kind
    return "Unknown"


# ---------------------------------------------------------------------------
# Основная функция нормализации
# ---------------------------------------------------------------------------

def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Принимает сырой dict из analyze_sql_query (после json.loads).
    Возвращает нормализованную модель:

        {
          "nodes":        [...],   # с добавленными полями source_kinds[]
          "edges":        [...],   # data-flow + parent_child + union_part
          "drop_queries": [...]
        }

    Изменения по сравнению с сырым JSON:
      - type="result" → "temp_query"
      - edges[] дополнены полем "relation": "ref"
      - добавлены структурные рёбра из parent_id:
            relation=parent_child | union_part
      - каждый узел получает поле source_kinds[] (parallel к own_in_tables)
    """
    nodes: list[dict] = raw.get("nodes", [])
    raw_edges: list[dict] = raw.get("edges", [])
    drop_queries: list[str] = raw.get("drop_queries", [])

    # --- нормализуем узлы ---
    nodes_out: list[dict] = []
    node_by_id: dict[int, dict] = {}

    for n in nodes:
        node = dict(n)  # копия
        # result → temp_query
        if node.get("type") == "result":
            node["type"] = "temp_query"
        # добавляем source_kinds
        node["source_kinds"] = [
            classify_source(t) for t in node.get("own_in_tables", [])
        ]
        nodes_out.append(node)
        node_by_id[node["id"]] = node

    # --- нормализуем data-flow рёбра ---
    edges_out: list[dict] = []
    for e in raw_edges:
        edges_out.append({
            "from_id":   e["from"],
            "to_id":     e["to"],
            "from_name": e["from_name"],
            "to_name":   e["to_name"],
            "relation":  "ref",
        })

    # --- структурные рёбра из parent_id ---
    for node in nodes_out:
        pid = node.get("parent_id")
        if pid is None:
            continue
        parent = node_by_id.get(pid)
        relation = "union_part" if node.get("is_union_part") else "parent_child"
        edges_out.append({
            "from_id":   pid,
            "to_id":     node["id"],
            "from_name": parent["name"] if parent else "",
            "to_name":   node["name"],
            "relation":  relation,
        })

    return {
        "nodes":        nodes_out,
        "edges":        edges_out,
        "drop_queries": drop_queries,
    }
