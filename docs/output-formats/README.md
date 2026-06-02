# Каталог форматов вывода SQL Query Analyzer

Этот каталог описывает все форматы файлов, которые могут быть получены из сводного JSON (результата парсинга 1С-запроса), их структуру, назначение и рекомендуемый порядок генерации.

## Структура каталога

```
docs/output-formats/
├── README.md                    ← этот файл
├── 01-machine-formats.md        ← базовые машинно-читаемые форматы
├── 02-query-structure.md        ← структура запроса: узлы, дерево, граф
├── 03-text-decompilation.md     ← тексты и декомпиляция
├── 04-lineage-fields.md         ← lineage полей и ключевые цепочки
├── 05-visualization.md          ← форматы для визуализации
├── 06-human-readable.md         ← документы и отчёты для людей
├── 07-search-index.md           ← индексирование и AI-обработка
├── 08-etl-pipeline.md           ← ETL, воспроизводимость, метаданные
├── 09-archive-publish.md        ← архивирование и публикация
└── 10-directory-layout.md       ← рекомендуемая структура каталогов
```

## Приоритетный минимум

Если нужно быстро начать работу — минимально достаточный набор:

| Приоритет | Файл | Формат | Назначение |
|---|---|---|---|
| 🔴 Обязательный | `nodes.csv` | CSV | Реестр всех узлов |
| 🔴 Обязательный | `tempqueries_catalog.csv` | CSV | Список ВТ с метаданными |
| 🔴 Обязательный | `edges_parent.csv` | CSV | Дерево вложенности |
| 🔴 Обязательный | `edges_refs.csv` | CSV | Граф зависимостей между ВТ |
| 🔴 Обязательный | `sources_map.csv` | CSV | Источники по узлам |
| 🟡 Желательный | `query_tree.json` | JSON | Иерархическое дерево |
| 🟡 Желательный | `field_lineage.json` | JSON | Происхождение полей |
| 🟡 Желательный | `lineage_key_fields.json` | JSON | Цепочки ключевых граф |
| 🟡 Желательный | `catalog.xlsx` | XLSX | Сводный каталог для Excel |
| 🟢 Продвинутый | `query_graph.dot` | DOT | Визуализация графа |
| 🟢 Продвинутый | `analysis.sqlite` | SQLite | SQL-запросы по графу |
| 🟢 Продвинутый | `corpus.jsonl` | JSONL | Подготовка к LLM-обработке |

## Рекомендуемый порядок генерации

1. Нормализация: `nodes.json`, `edges_parent.csv`, `edges_refs.csv`
2. Каталогизация: `tempqueries_catalog.csv`, `sources_map.csv`
3. Тексты: `query_texts/node_*.sql`
4. Lineage: `field_lineage.json`, `lineage_key_fields.json`
5. Граф: `query_graph.json`, `query_graph.dot`
6. Отчёты: `overview.md`, `catalog.xlsx`
7. Архив: `analysis.sqlite`, `corpus.jsonl`, `pipeline.yaml`

## Связанные файлы проекта

- `sql_query_analyzer.py` — основной парсер, источник сводного JSON
- `cli.py` — CLI-интерфейс для запуска парсера
- `examples/` — примеры входных и выходных данных
