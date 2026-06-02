# SQL Query Analyzer

Анализатор пакетных SQL/1C-запросов. Разбирает запрос на подзапросы, строит граф зависимостей по временным таблицам и возвращает JSON.

## Поддерживаемый синтаксис

| Возможность | 1C BSL | SQL |
|---|---|---|
| Временная таблица | `ПОМЕСТИТЬ` | `INTO` |
| Источник | `ИЗ` | `FROM` |
| Соединение | `СОЕДИНЕНИЕ` | `JOIN` |
| Объединение | `ОБЪЕДИНИТЬ ВСЕ` | `UNION ALL` |
| Уничтожение ВТ | `УНИЧТОЖИТЬ` | `DROP` |
| Псевдоним | `КАК` | `AS` |
| Комментарии | `// ...` | — |
| Вложенные подзапросы | ✅ | ✅ |
| Пакетный запрос | `;` | `;` |

---

## Установка

```bash
git clone https://github.com/lytkinam/sql-query-analyzer.git
cd sql-query-analyzer
# Зависимостей нет — только стандартная библиотека Python 3.8+
```

---

## Способы запуска

### 1. Как Python-модуль

```python
from sql_query_analyzer import analyze_sql_query

sql = """
ВЫБРАТЬ Т.Ссылка ПОМЕСТИТЬ ВТ_1 ИЗ Справочник.Т КАК Т;
ВЫБРАТЬ ВТ_1.Ссылка ИЗ ВТ_1 КАК ВТ_1
"""
json_str = analyze_sql_query(sql, detailed=False)
print(json_str)
```

### 2. Командная строка (CLI)

```bash
# Из файла
python cli.py examples/example.sql

# Детальный режим (UNION разбивается на части)
python cli.py examples/example.sql --detailed

# Сохранить результат в файл
python cli.py examples/example.sql --output result.json

# Из stdin
echo "ВЫБРАТЬ 1 ИЗ Таблица КАК Т" | python cli.py -
```

---

## Параметры `analyze_sql_query`

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `sql_text` | `str` | — | Текст запроса |
| `detailed` | `bool` | `False` | `True` — ОБЪЕДИНИТЬ/UNION разбивается на дочерние узлы `Часть_N` |

---

## Формат результата (JSON)

```json
{
  "nodes": [
    {
      "id":            0,
      "name":          "ВТ_Сотрудники",
      "type":          "temp_query",
      "text":          "ВЫБРАТЬ ...",
      "parent_id":     null,
      "max_parent_id": null,
      "children_ids":  [],
      "own_in_tables": ["СПРАВОЧНИК.СОТРУДНИКИ"],
      "is_stub":        false,
      "is_union_part":  false
    }
  ],
  "edges": [
    {
      "from":      0,
      "from_name": "ВТ_Сотрудники",
      "to":        1,
      "to_name":   "Результат_1"
    }
  ],
  "drop_queries": ["ВТ_Сотрудники"]
}
```

### Поля `nodes`

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | Уникальный номер узла |
| `name` | str | Имя ВТ, псевдоним или `Результат_N` |
| `type` | str | `temp_query` / `result` / `sub_query` |
| `text` | str | Развёрнутый SQL-текст узла |
| `parent_id` | int\|null | Ближайший родитель (для вложенных) |
| `max_parent_id` | int\|null | Корневой запрос в пакете |
| `children_ids` | [int] | Дочерние узлы |
| `own_in_tables` | [str] | Таблицы, которые читает этот узел |
| `is_stub` | bool | `true` — ВТ создана, но никем не читается |
| `is_union_part` | bool | `true` — узел есть часть UNION (detailed-режим) |

### Поля `edges`

Каждое ребро — зависимость по временной таблице:
`temp_query` с именем `from_name` → узел `to_name`, который её читает.

---

## Тесты

```bash
python tests.py
```

---

## Структура проекта

```
sql-query-analyzer/
├── sql_query_analyzer.py   # Ядро анализатора
├── cli.py                  # Командная строка
├── tests.py                # Базовые тесты
├── examples/
│   └── example.sql         # Пример пакетного 1C-запроса
└── README.md
```
