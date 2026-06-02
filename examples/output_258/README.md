# Результат анализа example_258.sql (Отчёт 258 НПО)

**Источник:** `../example_258.sql`
**Инструмент:** `exporters/normalizer.py` + `exporters/tables.py`
**Дата:** $(date -Iseconds)

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
└── tables/
    ├── nodes.csv
    ├── tempqueries_catalog.csv
    ├── edges_parent.csv
    ├── edges_refs.csv
    ├── sources_map.csv
    ├── union_parts.csv
    └── stubs.csv
```
