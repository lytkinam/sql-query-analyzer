# Результат анализа example.sql

**Источник:** `../example.sql`
**Инструмент:** `exporters/normalizer.py` + `exporters/tables.py`
**Дата:** $(date -Iseconds)

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
└── tables/
    ├── nodes.csv
    ├── tempqueries_catalog.csv
    ├── edges_parent.csv
    ├── edges_refs.csv
    ├── sources_map.csv
    ├── union_parts.csv
    └── stubs.csv
```
