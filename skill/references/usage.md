# SQL-Query-Analyzer — Пошаговая инструкция

## 1. Структура skill и скриптов

Все рабочие файлы находятся в `~/.kimi/skills/sql-query-analyzer/scripts/`:

| Файл | Назначение |
|------|------------|
| `sql_query_analyzer.py` | Ядро анализатора (исправленная версия upstream) |
| `analyze_1c_query.py` | **Основной скрипт** — запуск анализа 1C/SQL-запроса |
| `generate_report.py` | Генерация Markdown-отчёта из JSON-результата |
| `fix_upstream.py` | Исправление дефектного upstream-файла (если скачали с GitHub) |

## 2. Быстрый запуск (уже готовые скрипты)

### 2.1. Анализ запроса

```bash
cd ~/.kimi/skills/sql-query-analyzer/scripts

# Простой запуск
python analyze_1c_query.py /path/to/query.sql

# С детальным режимом и сводкой
python analyze_1c_query.py /path/to/query.sql --detailed --summary

# Сохранить в конкретный файл
python analyze_1c_query.py /path/to/query.sql -o /path/to/result.json --detailed
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `query_file` | Путь к файлу с 1C/SQL-запросом |
| `-o, --output` | Путь для JSON-результата (default: `result.json`) |
| `-d, --detailed` | Детальный режим: разбивка `ОБЪЕДИНИТЬ ВСЕ` на отдельные узлы |
| `-s, --summary` | Вывести сводку в консоль после анализа |

**Пример вывода:**

```
[INFO] Чтение запроса: 258_npo_query.md (288720 символов)
[INFO] Режим detailed=True
[OK] Результат сохранён: result.json
==================================================
СВОДКА ПО АНАЛИЗУ ЗАПРОСА
==================================================
Всего узлов:           298
Временных таблиц:      116
Подзапросов:           182
Рёбер зависимостей:    312
Stub-таблиц:           7
Union-частей:          102
DROP-запросов:         0
--------------------------------------------------
Stub-таблицы (не используются):
  - ВТ_ИСПОЛЬЗОВАТЬДЛЯНПО
  - ВТ_СторнированныеСуммыТранзитныеВиды
  ...
==================================================
```

### 2.2. Генерация отчёта

```bash
cd ~/.kimi/skills/sql-query-analyzer/scripts

# Базовый отчёт
python generate_report.py result.json

# С заданным заголовком и именем файла
python generate_report.py result.json -o "258_structure.md" -t "Отчёт 258 НПО"
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `json_file` | Путь к JSON-результату от `analyze_1c_query.py` |
| `-o, --output` | Путь для Markdown-отчёта (default: `report.md`) |
| `-t, --title` | Заголовок отчёта |

Отчёт включает:
- Общую статистику
- Список корневых узлов
- Stub-таблицы
- Полный перечень ВТ с входами/выходами
- Топ-30 используемых 1С-метаданных
- Дерево зависимостей

### 2.3. Python API (для встраивания в другие скрипты)

```python
import sys
sys.path.insert(0, "~/.kimi/skills/sql-query-analyzer/scripts")

from sql_query_analyzer import analyze_sql_query

with open("query.sql", "r", encoding="utf-8") as f:
    sql = f.read()

# detailed=True — разбивка UNION
json_str = analyze_sql_query(sql, detailed=True)

# Дальнейшая обработка...
import json
data = json.loads(json_str)
print(f"Узлов: {len(data['nodes'])}")
```

## 3. Если скачали upstream с GitHub

Файл `sql_query_analyzer.py` в репозитории на GitHub содержит дефект загрузки
(literal `\n`, экранированные кавычки). В skill уже включена **исправленная версия**.

Если вы склонировали оригинал и хотите исправить его:

```bash
cd /path/to/sql-query-analyzer  # директория с оригинальным репозиторием
python ~/.kimi/skills/sql-query-analyzer/scripts/fix_upstream.py sql_query_analyzer.py
```

Скрипт:
- Создаёт бэкап `.bak`
- Исправляет экранирование
- Проверяет синтаксис через `py_compile`

## 4. Анализ результата вручную

### 4.1. Список всех ВТ

```python
import json

data = json.load(open("result.json"))
vts = [n for n in data["nodes"] if n["type"] == "temp_query"]
for vt in vts:
    print(vt["name"])
```

### 4.2. Кто читает конкретную ВТ

```python
def dependents(vt_name):
    vt_id = next(n["id"] for n in data["nodes"] if n["name"] == vt_name)
    return [e["to_name"] for e in data["edges"] if e["from"] == vt_id]

print(dependents("ВТ_258НПО"))
```

### 4.3. От каких таблиц зависит ВТ

```python
def dependencies(vt_name):
    node = next(n for n in data["nodes"] if n["name"] == vt_name)
    return node.get("own_in_tables", [])

print(dependencies("ВТ_258НПО"))
```

### 4.4. Построение полного дерева

```python
from collections import defaultdict

children = defaultdict(list)
for e in data["edges"]:
    children[e["from_name"]].append(e["to_name"])

def tree(name, depth=0):
    print("  " * depth + name)
    for child in children.get(name, []):
        tree(child, depth + 1)

tree("ВТ_258НПО")
```

## 5. Декомпозиция на компоненты

Для больших запросов (258 НПО: 55+ ВТ) рекомендуется:

1. Сгруппировать ВТ по логическим слоям (контекст, выборка, расчёты, сборка)
2. Для каждого слоя создать YAML-описание:
   - входные ВТ
   - выходные ВТ
   - графы отчёта, которые покрывает слой
3. Построить матрицу трассировки «графа → компоненты»

Пример структуры слоя:

```yaml
component_id: C12
name: Остатки/взносы/ИД (основные)
virtual_tables:
  - ВТ_Корректировки
  - ВТ_Суммы_ПР
  - ВТ_Суммы_ПР_С_Обязательствами
  - ВТ_Суммы
report_fields: [20, 26, 27, 33]  # Нач. остаток, Взносы, ИД, Кон. остаток
```

## 6. Интеграция с artifact inventory (MEM05)

Типы артефактов, которые генерируются на основе анализа:

| Код | Тип | Содержание |
|-----|-----|------------|
| `ADD05` | Implementation Detail | SQL-структура запроса, слои, зависимости |
| `INT02` | Query Interface | Интерфейс между 1С-регистрами и отчётом |
| `DAT-1C-{Регистр}` | Data Model | Ссылки на справочники, регистры, перечисления |

Каждый компонент C1–C16 получает код `P-NPO-31.ADD{NN}` (для отчёта 258).

## 7. Ограничения и known issues

- **Временные таблицы без `ПОМЕСТИТЬ`** — анализатор не распознаёт inline CTE (`WITH`)
- **Динамический SQL** — не поддерживается
- **Внешние источники данных** (`ВнешниеИсточникиДанных`) — распознаются как обычные таблицы
- **Функции 1С** (`ЕСТЬNULL`, `РАЗНОСТЬДАТ` и т.п.) — игнорируются при построении графа
- **Огромные запросы** (>500 KB) — обработка занимает 10–30 секунд
