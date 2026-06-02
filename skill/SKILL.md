---
name: sql-query-analyzer
description: |
  Анализатор пакетных SQL/1C-запросов. Разбирает запрос на подзапросы,
  строит граф зависимостей по временным таблицам (ВТ) и возвращает JSON.
  Применяется для структурного разбора сложных 1С-запросов отчётов НПО
  (в частности, форма 0420258 и других многослойных запросов).
---

# SQL-QUERY-ANALYZER — Skill анализа 1C/SQL-запросов

## Назначение

Разбор монолитных пакетных запросов 1С (ВЫБРАТЬ / SELECT с ПОМЕСТИТЬ / INTO)
на управляемый набор компонентов с построением графа зависимостей.

Источник: https://github.com/lytkinam/sql-query-analyzer

## Структура skill

```
sql-query-analyzer/
├── SKILL.md                              # Этот файл
├── scripts/
│   ├── sql_query_analyzer.py             # Ядро анализатора (исправленная версия)
│   ├── analyze_1c_query.py               # Скрипт запуска анализа
│   ├── generate_report.py                # Генерация Markdown-отчёта из JSON
│   └── fix_upstream.py                   # Исправление upstream-файла
└── references/
    ├── usage.md                          # Подробная инструкция
    └── 258_npo_query_structure.md        # Пример результата (отчёт 258 НПО)
```

## Быстрый старт

### 1. Анализ запроса (CLI)

```bash
cd ~/.kimi/skills/sql-query-analyzer/scripts

# Базовый запуск
python analyze_1c_query.py /path/to/query.sql -o result.json

# Детальный режим + сводка в консоль
python analyze_1c_query.py /path/to/query.sql --detailed --summary
```

### 2. Генерация отчёта

```bash
cd ~/.kimi/skills/sql-query-analyzer/scripts

python generate_report.py result.json -o report.md -t "Анализ запроса 258 НПО"
```

### 3. Python API

```python
import sys
sys.path.insert(0, "~/.kimi/skills/sql-query-analyzer/scripts")

from sql_query_analyzer import analyze_sql_query

with open("query.sql", "r", encoding="utf-8") as f:
    sql = f.read()

json_str = analyze_sql_query(sql, detailed=True)
print(json_str)
```

## Поддерживаемый синтаксис

| Возможность | 1C BSL | SQL |
|-------------|--------|-----|
| Временная таблица | `ПОМЕСТИТЬ` | `INTO` |
| Источник | `ИЗ` | `FROM` |
| Соединение | `СОЕДИНЕНИЕ` | `JOIN` |
| Объединение | `ОБЪЕДИНИТЬ ВСЕ` | `UNION ALL` |
| Уничтожение ВТ | `УНИЧТОЖИТЬ` | `DROP` |
| Псевдоним | `КАК` | `AS` |
| Комментарии | `// ...` | — |
| Вложенные подзапросы | ✅ | ✅ |
| Пакетный запрос | `;` | `;` |

## Формат результата (JSON)

```json
{
  "nodes": [
    {
      "id": 0,
      "name": "ВТ_Сотрудники",
      "type": "temp_query",
      "text": "ВЫБРАТЬ ...",
      "parent_id": null,
      "max_parent_id": null,
      "children_ids": [],
      "own_in_tables": ["СПРАВОЧНИК.СОТРУДНИКИ"],
      "is_stub": false,
      "is_union_part": false
    }
  ],
  "edges": [
    {
      "from": 0,
      "from_name": "ВТ_Сотрудники",
      "to": 1,
      "to_name": "Результат_1"
    }
  ],
  "drop_queries": ["ВТ_Сотрудники"]
}
```

### Типы узлов (`nodes.type`)

| Тип | Описание |
|-----|----------|
| `temp_query` | Запрос, создающий временную таблицу (`ПОМЕСТИТЬ` / `INTO`) |
| `result` | Итоговый запрос без `ПОМЕСТИТЬ`, выдающий результат |
| `sub_query` | Вложенный подзапрос или часть UNION |

### Флаги узлов

| Флаг | Значение |
|------|----------|
| `is_stub` | `true` — ВТ создана, но никем не читается |
| `is_union_part` | `true` — узел является частью `ОБЪЕДИНИТЬ ВСЕ` / `UNION ALL` |

### Рёбра (`edges`)

Каждое ребро — зависимость по временной таблице:
`temp_query` с именем `from_name` → узел `to_name`, который её читается.

## Применение в проекте ai.hmnpf

### Рекомендуемый workflow

1. **Экспортировать запрос** из 1С в файл `.md` или `.sql`
2. **Запустить анализатор** через `analyze_1c_query.py --detailed --summary`
3. **Изучить `nodes`** — получить список всех ВТ, определить stub-таблицы
4. **Изучить `edges`** — построить дерево зависимостей
5. **Сгруппировать узлы** в логические компоненты (C1–C16 для отчёта 258)
6. **Построить матрицу трассировки** «графа отчёта → компоненты → ВТ»

### Пример применения: отчёт 0420258 (НПО)

Запрос: `258 НПО запрос 1С.MD` (родительская задача #560)

Результат анализа:
- **298 узлов** (55+ временных таблиц, 102 части UNION, подзапросы)
- **312 рёбер** зависимостей
- **7 stub-таблиц** (не используются в downstream)

Компоненты декомпозиции см. в `references/258_npo_query_structure.md`.

## Интеграция с другими skills

- `markitdown` — конвертация исходных документов 1С в Markdown
- `1c-knowledge-consolidator` — индексация извлечённых метаданных
- `ai_job_requirements` — включение структуры запроса в artifact inventory (ADD05, INT02, DAT-1C-*)

## Агент Checklist

- [ ] Проверить, что upstream-файл `sql_query_analyzer.py` не содержит literal `\n`
- [ ] Запускать с `detailed=True` для запросов с `ОБЪЕДИНИТЬ ВСЕ`
- [ ] Сохранять JSON-результат рядом с исходным запросом
- [ ] Документировать stub-таблицы (возможно, мёртвый код)
- [ ] Связывать ВТ с графами отчёта в матрице трассировки

## Ссылки

- `references/usage.md` — Подробная инструкция по установке и применению
- `references/258_npo_query_structure.md` — Результат анализа запроса 258 НПО
