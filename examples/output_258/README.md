# Результат анализа example_258.sql (Отчёт 258 НПО)

**Источник:** `../example_258.sql`
**Инструменты:** `exporters/normalizer.py`, `exporters/tables.py`, `exporters/texts.py`

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
│   ├── tempqueries.json    # Только ВТ (116)
│   └── subqueries.json     # Только подзапросы (182)
├── tables/
│   ├── nodes.csv
│   ├── tempqueries_catalog.csv
│   ├── edges_parent.csv
│   ├── edges_refs.csv
│   ├── sources_map.csv
│   ├── union_parts.csv
│   └── stubs.csv
└── query_texts/            # ← Итерация 2 (298 файлов .sql + 298 .md)
    ├── texts_index.json
    ├── normalized_queries.sql
    ├── node_0.sql … node_297.sql
    └── node_0.md … node_297.md
```
