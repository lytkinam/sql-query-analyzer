# Результат анализа example.sql

**Источник:** `../example.sql`
**Инструменты:** `exporters/normalizer.py`, `exporters/tables.py`, `exporters/texts.py`

## Статистика

- Узлов: 3
- Временных таблиц: 3
- Подзапросов: 0
- Рёбер зависимостей: 2
- Stub-таблиц: 0
- Union-частей: 0

## Структура каталогов

```
output_example/
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
│   └── stubs.csv
└── query_texts/            # ← Итерация 2
    ├── texts_index.json    # Каталог текстовых файлов
    ├── normalized_queries.sql
    └── node_{id}.sql / node_{id}.md
```
