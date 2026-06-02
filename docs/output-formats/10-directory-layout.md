# Рекомендуемая структура каталогов

Стандартная организация всех артефактов анализа в файловой системе.

---

## Полная структура

```
output/
├── README.md                        ← Описание набора
├── version.json                     ← Метаданные генерации
│
├── raw/
│   └── 258_npo_analysis.json        ← Исходный сводный JSON (только для чтения)
│
├── normalized/
│   ├── nodes.json                   ← Все узлы, нормализованный JSON
│   ├── nodes.jsonl                  ← Все узлы, JSON Lines
│   ├── tempqueries.json             ← Только ВТ (type=tempquery)
│   └── subqueries.json              ← Только подзапросы (type=subquery)
│
├── tables/
│   ├── nodes.csv                    ← Плоская таблица узлов
│   ├── tempqueries_catalog.csv      ← Каталог ВТ
│   ├── edges_parent.csv             ← Дерево родитель→потомок
│   ├── edges_refs.csv               ← Граф ссылок между ВТ
│   ├── sources_map.csv              ← Источники по узлам
│   ├── union_parts.csv              ← Карта объединений
│   ├── stubs.csv                    ← Технические заглушки
│   ├── fields.csv                   ← Реестр полей
│   ├── expressions.csv              ← Вычисляемые выражения
│   ├── conditions.csv               ← Условия WHERE/JOIN
│   ├── joins.csv                    ← Карта JOIN-соединений
│   └── field_mapping.csv            ← Mapping выход→вход
│
├── texts/
│   ├── node_132.sql                 ← Текст ВТ как SQL
│   ├── node_132.md                  ← Текст ВТ как Markdown с метаданными
│   ├── texts_index.json             ← Индекс текстовых файлов
│   ├── normalized_queries.sql       ← Нормализованный SQL всех ВТ
│   └── tokens.csv                   ← Токенизированные тексты
│
├── lineage/
│   ├── field_lineage.json           ← Lineage всех полей
│   ├── lineage_key_fields.json      ← Lineage ключевых граф
│   ├── dependency_matrix.csv        ← Матрица зависимостей узлов
│   └── aliases.json                 ← Словарь псевдонимов полей
│
├── graph/
│   ├── query_graph.json             ← Граф в универсальном JSON
│   ├── query_tree.json              ← Дерево (вложенный JSON)
│   ├── query_graph.dot              ← Graphviz DOT
│   ├── query_graph.mmd              ← Mermaid
│   ├── query_graph.gexf             ← GEXF для Gephi
│   ├── query_graph.graphml          ← GraphML
│   ├── cytoscape.json               ← Cytoscape.js
│   ├── d3_graph.json                ← D3.js
│   ├── query_graph.svg              ← Векторное изображение
│   └── query_graph.png              ← Растровое изображение
│
├── reports/
│   ├── overview.md                  ← Markdown-отчёт
│   ├── overview.html                ← HTML-отчёт
│   ├── overview.pdf                 ← PDF-отчёт
│   ├── catalog.xlsx                 ← Excel-каталог (все листы)
│   ├── catalog.ods                  ← ODS-каталог
│   └── index.txt                    ← Текстовый индекс для CLI
│
├── search/
│   ├── corpus.jsonl                 ← Корпус для семантического поиска
│   ├── chunks.jsonl                 ← Нарезка текстов для LLM
│   ├── inverted_index.json          ← Инвертированный индекс
│   ├── keywords.csv                 ← Ключевые слова по узлам
│   └── embeddings.parquet           ← Векторные представления
│
├── db/
│   ├── analysis.sqlite              ← SQLite база со всеми таблицами
│   └── analysis.duckdb              ← DuckDB для аналитики
│
├── meta/
│   ├── schema.json                  ← JSON Schema для валидации
│   ├── pipeline.yaml                ← Манифест пайплайна
│   ├── extractor.yaml               ← Конфигурация извлечения
│   ├── dictionary.md                ← Словарь данных
│   ├── processing.jsonl             ← Лог обработки
│   ├── validation.csv               ← Отчёт валидации
│   └── checksums.txt                ← Контрольные суммы
│
└── release/
    └── v1.0.0/
        ├── analysis_bundle.zip
        ├── datapackage.json
        └── checksums.txt
```

---

## Минимальный набор (быстрый старт)

Для начала работы достаточно создать:

```
output/
├── tables/
│   ├── nodes.csv
│   ├── tempqueries_catalog.csv
│   ├── edges_parent.csv
│   ├── edges_refs.csv
│   └── sources_map.csv
├── lineage/
│   ├── field_lineage.json
│   └── lineage_key_fields.json
└── reports/
    ├── overview.md
    └── catalog.xlsx
```

---

## Правила именования

| Правило | Пример |
|---|---|
| Файлы: `snake_case` | `nodes.csv`, `field_lineage.json` |
| Папки: `snake_case` | `query_texts/`, `lineage/` |
| Текстовые файлы: `node_{id}.sql` или `node_{id}_{name}.sql` | `node_132.sql`, `node_132_ВТ_ПС.sql` |
| Архивы: `{query_id}_{tag}_bundle.{ext}` | `258_npo_bundle.zip` |
| Версии: `v{major}.{minor}.{patch}` | `v1.0.0` |
