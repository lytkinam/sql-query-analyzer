# Результат анализа example_258.sql

**Источник:** `../example_258.sql`
**Инструменты:** `exporters/normalizer.py`, `exporters/tables.py`, `exporters/texts.py`, `exporters/lineage.py`

## Статистика

- Узлов: 298
- Временных таблиц: 116
- Подзапросов: 182
- Рёбер зависимостей: 312
- Stub-таблиц: 7
- Union-частей: 102

## Структура каталогов

```
output_258/
├── normalized/
│   ├── nodes.json          # Все узлы (нормализованный JSON)
│   ├── nodes.jsonl         # Все узлы (JSON Lines)
│   ├── tempqueries.json    # Только ВТ
│   └── subqueries.json     # Только подзапросы
├── tables/
│   ├── nodes.csv
│   ├── tempqueries_catalog.csv
│   ├── edges_parent.csv
│   ├── edges_refs.csv
│   ├── sources_map.csv
│   ├── union_parts.csv
│   ├── stubs.csv
│   ├── fields.csv          # ← Итерация 4
│   ├── expressions.csv
│   ├── conditions.csv
│   └── joins.csv
├── query_texts/            # ← Итерация 2
│   ├── texts_index.json
│   ├── normalized_queries.sql
│   └── node_{id}.sql / node_{id}.md
└── lineage/                # ← Итерация 4
    ├── field_lineage.json
    ├── lineage_key_fields.json
    ├── field_mapping.csv
    └── dependency_matrix.csv
```
