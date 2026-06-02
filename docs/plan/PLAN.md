# ПЛАН РЕАЛИЗАЦИИ — sql-query-analyzer

## 0. Ключевые решения

**Принцип:** парсер генерирует «сырой» JSON (текущий формат), слой `exporters/` конвертирует его во все целевые форматы. Парсер не меняется ради форматов.

**Нормализация типов:**
- `temp_query` → `temp_query` (без изменений)
- `result` → `temp_query` (результирующий запрос без ПОМЕСТИТЬ — особый вид ВТ)
- `sub_query` → `sub_query` (без изменений)

**Нормализация полей:** текущий snake_case парсера является каноническим. Целевые форматы подстраиваются под него:
- `parent_id`, `max_parent_id`, `own_in_tables`, `is_stub`, `is_union_part` — эталонные имена
- Спецификации `01-machine-formats.md` и `02-table-formats.md` привести в соответствие

**Рёбра:** в `edges` сейчас только data-flow. Структурные рёбра (parent_child, union_part) генерирует normalizer из `parent_id` и `children_ids`.

---

## 1. Структура проекта (целевая)

```
sql-query-analyzer/
├── sql_query_analyzer.py        ← парсер (не меняется)
├── cli.py                       ← расширить флагами --format, --output-dir
├── exporters/
│   ├── __init__.py
│   ├── normalizer.py            ← сырой JSON → canonical model
│   ├── tables.py                ← CSV-файлы (nodes, edges, sources, stubs, union_parts)
│   ├── texts.py                 ← node_*.sql, node_*.md, texts_index.json
│   ├── lineage.py               ← field_lineage.json (требует парсинга SELECT-списка)
│   ├── graph.py                 ← .dot, .mmd, .gexf, .graphml, cytoscape.json, d3_graph.json
│   ├── reports.py               ← overview.md, catalog.xlsx
│   ├── search.py                ← corpus.jsonl, chunks.jsonl, inverted_index.json
│   └── db.py                   ← analysis.sqlite
├── tests/
│   ├── fixtures/
│   │   ├── small.sql            ← = examples/example.sql
│   │   └── large.sql            ← = examples/example_258.sql
│   ├── golden/
│   │   ├── small_nodes.csv
│   │   ├── small_edges_refs.csv
│   │   └── large_nodes_count.txt
│   └── test_exporters.py
├── examples/                    ← существующие примеры
└── docs/
    ├── output-formats/          ← существующие спецификации
    └── plan/
        └── PLAN.md              ← этот файл
```

---

## 2. Этапы — итерации

### Итерация 1: Normalizer + базовые CSV (🔴 обязательный минимум)

**Файл:** `exporters/normalizer.py`

Задачи:
- Принимает сырой JSON из парсера
- Нормализует тип: `result` → `temp_query`
- Добавляет `relation` в рёбра: `ref` для data-flow, `parent_child` / `union_part` для структурных
- Генерирует структурные рёбра из `parent_id` (сейчас в `edges` только data-flow)

**Файл:** `exporters/tables.py`

Генерирует (по спецификациям `01` и `02`):
- `normalized/nodes.json` — нормализованный JSON
- `normalized/nodes.jsonl` — JSON Lines
- `tables/nodes.csv` — плоская таблица: `id, name, type, parent_id, max_parent_id, children_count, own_in_tables_count, is_stub, is_union_part, text_len`
- `tables/tempqueries_catalog.csv` — только ВТ + колонка `union_parts`
- `tables/edges_parent.csv` — дерево: `parent_id, child_id, parent_name, child_name, depth, relation`
- `tables/edges_refs.csv` — граф: `from_id, to_id, from_name, to_name, relation`
- `tables/sources_map.csv` — `node_id, node_name, source_name, source_kind, ordinal`
- `tables/union_parts.csv` — карта ОБЪЕДИНИТЬ
- `tables/stubs.csv` — заглушки

Задача: `source_kind` — классификация по префиксу имени объекта:
- `Справочник.*` → `Catalog`
- `РегистрНакопления.*` → `AccumulationRegister`
- `РегистрСведений.*` → `InformationRegister`
- `Документ.*` → `Document`
- `РегистрБухгалтерии.*` → `AccountingRegister`
- `ВТ_*` или `~TT~*` → `TempTable`
- остальное → `Unknown`

**Расчёт `depth`** для `edges_parent.csv`: BFS от корневых узлов (`parent_id == null`).

---

### Итерация 2: Тексты по узлам

**Файл:** `exporters/texts.py`

Генерирует (по спецификации `03`):
- `texts/node_{id}.sql` — текст узла с шапкой комментария
- `texts/node_{id}.md` — Markdown с метаданными
- `texts/texts_index.json` — каталог: `node_id, name, path, text_len, text_hash, line_count`
- `texts/normalized_queries.sql` — все ВТ подряд с разделителями

Правила нормализации SQL:
- Ключевые слова → ВЕРХНИЙ РЕГИСТР
- Удалить лишние пробелы/переносы
- Разделитель: `-- ===== ВТ_Имя (id=N) =====`

---

### Итерация 3: Граф

**Файл:** `exporters/graph.py`

Генерирует (по спецификации `05`):
- `graph/query_graph.json` — `{nodes: [{id, label, type}], edges: [{from, to, label}]}`
- `graph/query_tree.json` — вложенный JSON с `children[]`
- `graph/query_graph.mmd` — Mermaid `graph TD`
- `graph/query_graph.dot` — Graphviz DOT с цветами по типу узла
- `graph/query_graph.gexf` — GEXF XML
- `graph/query_graph.graphml` — GraphML XML
- `graph/cytoscape.json` — Cytoscape.js формат
- `graph/d3_graph.json` — D3.js формат

Цветовая схема DOT:
- `temp_query` → `lightgreen`
- `sub_query` → `lightblue`
- `is_stub=true` → `lightyellow`
- финальный результат → `lightsalmon`

---

### Итерация 4: Lineage полей

**Файл:** `exporters/lineage.py`

Это самая сложная итерация — требует разбора SELECT-списка.

Задачи:
- Простой regex-парсер SELECT-списка: извлечь `alias`, `expression`, `source_table.source_field`
- `tables/fields.csv` — реестр полей: `node_id, node_name, field_ordinal, field_alias, expression, source_table, source_field, is_computed`
- `lineage/field_lineage.json` — цепочки: для каждого поля финального узла traced через граф ВТ
- `lineage/lineage_key_fields.json` — только для ключевых полей из `extractor.yaml`
- `tables/expressions.csv` — ISNULL, ВЫБОР КОГДА, агрегаты
- `tables/conditions.csv` — WHERE, JOIN ON
- `tables/joins.csv` — карта соединений
- `lineage/dependency_matrix.csv` — матрица X зависит от Y

**Алгоритм построения цепочки:**
1. Взять финальный узел (type=result/последняя ВТ)
2. Для каждого поля: найти выражение в SELECT-списке
3. Если `expr = alias.field` → найти узел-источник по `edges_refs`
4. Рекурсивно трассировать вглубь до физической таблицы
5. Записать цепочку как `chain[]`

---

### Итерация 5: Отчёты

**Файл:** `exporters/reports.py`

Генерирует (по спецификации `06`):
- `reports/overview.md` — Markdown-отчёт: статистика, граф в Mermaid, список ВТ
- `reports/catalog.xlsx` — Excel с листами: Nodes, TempQueries, Edges, Sources, Fields, Lineage
- `reports/index.txt` — текстовый индекс для CLI

Для XLSX используется `openpyxl`. Зависимость опциональная.

---

### Итерация 6: Search / DB

**Файл:** `exporters/search.py` + `exporters/db.py`

Генерирует (по спецификациям `07`, `08`):
- `search/corpus.jsonl` — каждый узел как документ: `id, name, type, text, tables[]`
- `search/chunks.jsonl` — нарезка текстов по `chunk_size=512` токенов с overlap
- `search/inverted_index.json` — слово → список `node_id`
- `db/analysis.sqlite` — таблицы: `nodes, edges, sources, fields`
- `meta/version.json` — метаданные генерации
- `meta/pipeline.yaml` — манифест шагов
- `meta/validation.csv` — отчёт валидации целостности
- `meta/checksums.txt` — SHA-256 всех файлов

---

### Итерация 7: CLI и конфигурация

**Файл:** `cli.py` (расширить)

```bash
python cli.py input.sql --output-dir ./output --format all
python cli.py input.sql --output-dir ./output --format tables,graph,reports
python cli.py input.sql --output-dir ./output --format minimal
python cli.py input.sql --list-formats
python cli.py input.json --from-json --format graph  # принять готовый JSON
```

**Профили форматов:**
- `minimal` → tables (5 CSV обязательных)
- `standard` → minimal + texts + graph + reports
- `full` → всё
- `all` → всё

**Файл:** `extractor.yaml` (конфиг)
- `key_fields[]` — поля для lineage
- `skip_stubs`
- `chunk_size`, `chunk_overlap`
- `output_dir`
- `include_formats[]`

---

## 3. Golden tests

Каждая итерация закрывается тестом:

| Тест | Fixture | Проверяет |
|---|---|---|
| `test_normalizer_small` | `small.sql` | Счётчики узлов, типы, рёбра |
| `test_tables_small` | `small.sql` | CSV-контракт: колонки, значения |
| `test_tables_large` | `large.sql` | ~296 узлов в nodes.csv |
| `test_graph_mermaid` | `small.sql` | Валидный Mermaid, все рёбра |
| `test_graph_dot` | `small.sql` | Валидный DOT |
| `test_lineage_fields` | `small.sql` | Цепочки не обрываются |
| `test_sqlite` | `small.sql` | SQL-запрос к nodes возвращает корректное количество |

Тесты используют `pytest`, golden-файлы лежат в `tests/golden/`.

---

## 4. Порядок запуска пайплайна

```python
from exporters.normalizer import normalize
from exporters.tables import generate_tables
from exporters.texts import generate_texts
from exporters.graph import generate_graph
from exporters.lineage import generate_lineage
from exporters.reports import generate_reports
from exporters.search import generate_search
from exporters.db import generate_db

raw = json.loads(analyze_sql_query(sql_text, detailed=True))
model = normalize(raw)

generate_tables(model, output_dir)
generate_texts(model, output_dir)
generate_graph(model, output_dir)
generate_lineage(model, output_dir)     # зависит от tables
generate_reports(model, output_dir)    # зависит от lineage, graph
generate_search(model, output_dir)     # зависит от texts
generate_db(model, output_dir)         # зависит от tables
```

---

## 5. Открытые вопросы

| Вопрос | Влияние | Рекомендация |
|---|---|---|
| Нужен ли тип `result` отдельно или всё → `temp_query`? | Схема `nodes.json` | Привести `01-machine-formats.md` в соответствие |
| Как парсить SELECT-список для lineage? | Итерация 4 | Начать с regex, потом расширить |
| `detailed=True` или `False` для экспорта? | Все CSV | Использовать `detailed=True` для `union_parts.csv`, `False` для `edges_refs.csv` |
| Что делать с очень большими узлами (>10 КБ текст)? | `texts/`, `search/` | Писать в файл, в CSV — только `text_len` |
| Нужен ли `openpyxl` как обязательная зависимость? | `reports/catalog.xlsx` | Опциональный, с graceful fallback |

---

## 6. Summary

### Что уже есть

| Компонент | Статус | Примечание |
|---|---|---|
| `sql_query_analyzer.py` | ✅ готов | Парсер 1C/SQL, граф зависимостей, JSON-вывод |
| `examples/example.sql` | ✅ | Маленький пример (~10 узлов) |
| `examples/example_258.sql` | ✅ | Большой пример (~296 узлов, 519 КБ) |
| `examples/example_258_result.json` | ✅ | Эталонный результат большого примера |
| `docs/output-formats/` | ✅ | 10 спецификаций форматов вывода |
| `cli.py` | ⚠️ базовый | Требует расширения флагами форматов |

### Что нужно сделать

| Итерация | Файлы | Сложность | Приоритет |
|---|---|---|---|
| 1 — Normalizer + CSV | `exporters/normalizer.py`, `tables.py` | 🟡 средняя | 🔴 обязательно |
| 2 — Тексты | `exporters/texts.py` | 🟢 низкая | 🟠 важно |
| 3 — Граф | `exporters/graph.py` | 🟡 средняя | 🟠 важно |
| 4 — Lineage | `exporters/lineage.py` | 🔴 высокая | 🟡 желательно |
| 5 — Отчёты | `exporters/reports.py` | 🟡 средняя | 🟡 желательно |
| 6 — Search/DB | `exporters/search.py`, `db.py` | 🟡 средняя | 🟢 опционально |
| 7 — CLI | `cli.py` | 🟢 низкая | 🟠 важно |

### Ключевые риски

- **Lineage** — самая неопределённая часть. Regex-парсинг SELECT срабатывает для простых случаев, но сложные выражения (`ВЫБОР КОГДА`, вложенные функции) потребуют более полного парсера
- **Большой пример** — 296 узлов, часть с текстом >10 КБ. Нужна стратегия отсечки для CSV
- **`source_kind`** — классификация по префиксу покрывает ~90% случаев; оставшиеся 10% (произвольные алиасы) останутся `Unknown`

### Метрики готовности

- Итерация 1 закрыта: `example_258.sql` → корректный `nodes.csv` с 296 строками
- Итерация 3 закрыта: граф большого примера рендерится в Graphviz без ошибок
- Итерация 4 закрыта: lineage 5 ключевых полей прослежены до физических таблиц
- Полная готовность: `python cli.py example_258.sql --format full` завершается за <10 с
