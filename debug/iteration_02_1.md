# Итерация 2.1 — Разбор полей нод (`fields_node`)

## Цель

Для каждой ноды (подзапроса/ВТ) разобрать SELECT-список:
выяснить **список используемых таблиц и полей** с резолвингом
псевдонима таблицы в первичную таблицу.

Это основа для корректной трассировки lineage в итерации 4:
без `fields_node` цепочка поля обрывается на ВТ вместо физической таблицы.

---

## Новые файлы

| Файл | Назначение |
|------|------------|
| `exporters/fields_node.py` | Парсер полей нод |
| `tests/test_fields_node.py` | 30+ тестов |

---

## Структура результата

### `table_alias_map[node_id]`

Парсится из FROM/JOIN. Нужен для резолвинга псевдонима → первичная таблица.

```json
[
  {
    "alias":         "д",
    "primary_table": "Справочник.Договоры",
    "is_virtual":    false
  },
  {
    "alias":         "ВТ_Остатки",
    "primary_table": "ВТ_Остатки",
    "is_virtual":    true
  }
]
```

`is_virtual: true` → ВТ → нужна рекурсия при трассировке.  
`is_virtual: false` → физическая таблица 1С → терминал, стоп.

### `fields_node[node_id]`

```json
[
  {
    "alias":          "ДатаОкончанияВыплат24",
    "expression_raw": "ВЫБОР КОГДА ... КОНЕЦ",
    "expr_type":      "case_when",
    "field_refs": [
      {
        "alias_table":   "ВТ_ОстаткиВыплат",
        "field":         "Остаток",
        "primary_table": "ВТ_ОстаткиВыплат"
      },
      {
        "alias_table":   "ВТ_ПоследниеВыплаты",
        "field":         "ПоследняяВыплата",
        "primary_table": "ВТ_ПоследниеВыплаты"
      }
    ]
  }
]
```

---

## Типы `expr_type`

| Тип | Терминал? | Пример |
|-----|-----------|--------|
| `field_ref` | нет (→ рекурсия) | `д.Ссылка` |
| `case_when` | нет | `ВЫБОР КОГДА ... КОНЕЦ` |
| `func_call` | нет | `ДОБАВИТЬКДАТЕ(а.Д, МЕСЯЦ, 12)` |
| `aggregate` | нет | `СУММА(х.Сумма)` |
| `arithmetic`| нет | `а.Х * б.У` |
| `literal`   | **да** | `"-"`, `NULL`, `&Параметр`, `ЗНАЧЕНИЕ(...)` |
| `star`      | **да** | `*` |

---

## Правило трассировки через `field_refs`

```
trace(node_id, alias):
  rec = fields_node[node_id][alias]
  для каждого ref в rec.field_refs:
    entry = table_alias_map[node_id][ref.alias_table]
    если entry.is_virtual:
      → рекурсия: trace(source_node_id, ref.field)
    иначе:
      → СТОП — физическая таблица найдена
```

---

## Возможные ошибки

### ОШИБКА-1: alias_table не резолвится

**Симптом:** `primary_table == alias_table` (псевдоним не найден в alias_map).  
**Причина:** псевдоним из вложенной ноды или сложный синтаксис СОЕДИНЕНИЯ.  
**Диагностика:**
```python
for nid, records in result["fields_node"].items():
    am = {e["alias"].upper(): e for e in result["table_alias_map"][nid]}
    for rec in records:
        for ref in rec["field_refs"]:
            if ref["alias_table"].upper() not in am:
                print(f"node {nid} | поле {rec['alias']} | неизвестный псевдоним {ref['alias_table']}")
```

### ОШИБКА-2: SELECT-блок не извлечён (`fields_node[nid] == []`)

**Симптом:** список полей пустой при непустой ноде.  
**Причина:** нестандартный синтаксис ВЫБРАТЬ ПЕРВЫЕ N или РАЗЛИЧНЫЕ.  
**Диагностика:**
```python
import json
from sql_query_analyzer import analyze_sql_query
from exporters.fields_node import _extract_select_block

nodes = analyze_sql_query(sql)["nodes"]
for n in nodes:
    block = _extract_select_block(n["text"])
    if block is None and n["type"] != "sub_query":
        print(f"node {n['id']} ({n['name']}): SELECT-блок не найден")
        print(n["text"][:200])
```

### ОШИБКА-3: CASE внутри функции двойной вложенности

**Симптом:** `expr_type == "func_call"` но `field_refs` пустой.  
**Причина:** вложенный ВЫБОР как аргумент функции — `_extract_field_refs` ищет
`слово.слово` по плоскому тексту, скобки уже схлопнуты.  
**Диагностика:**
```python
for nid, records in result["fields_node"].items():
    for rec in records:
        if rec["expr_type"] in ("func_call", "aggregate") and not rec["field_refs"]:
            print(f"node {nid} | {rec['alias']} | пустой field_refs: {rec['expression_raw'][:80]}")
```

### ОШИБКА-4: UNION — берётся только первый блок SELECT

**Симптом:** поля второго/третьего SELECT в ОБЪЕДИНИТЬ не попадают в `fields_node`.  
**Причина:** `_extract_select_block` берёт текст до первого ИЗ/FROM, но у UNION
может быть несколько SELECT-блоков.  
**Диагностика:**
```python
import re
for n in nodes:
    if re.search(r'ОБЪЕДИНИТЬ|UNION', n["text"], re.IGNORECASE):
        print(f"node {n['id']} ({n['name']}) содержит UNION — поля только из первого SELECT")
```

### ОШИБКА-5: alias map не видит таблицы из ИТОГИ ПО

**Симптом:** таблица из секции ИТОГИ не попадает в alias_map.  
**Причина:** `parse_table_alias_map` парсит только FROM/JOIN.  
**Обходной путь:** в большинстве запросов 1С ИТОГИ не добавляют новых таблиц.

### ОШИБКА-6: псевдоним == ключевое слово 1С

**Симптом:** псевдоним типа `КАК СУММА` парсится как агрегат.  
**Причина:** `_classify_expr` проверяет начало строки на AGGREGATE_FUNCS.  
**Обходной путь:** псевдонимы-ключевые слова в 1С запрещены компилятором,
поэтому на практике не встречается.

---

## Запуск тестов

```bash
# Все тесты итерации 2.1
pytest tests/test_fields_node.py -v

# Только интеграционные
pytest tests/test_fields_node.py::TestBuildIntegration -v

# Только классификатор типов
pytest tests/test_fields_node.py::TestClassifyExpr -v
```

---

## Чеклист перед коммитом итерации 2.2

- [ ] `pytest tests/test_fields_node.py` — все зелёные
- [ ] Проверить ОШИБКА-1: нет неизвестных псевдонимов в реальном запросе
- [ ] Проверить ОШИБКА-2: все ноды типа `temp_query` / `result` имеют непустой `fields_node`
- [ ] Проверить ОШИБКА-3: нет `func_call` с пустым `field_refs` при ненулевых аргументах
- [ ] Проверить ОШИБКА-4: все ноды с UNION задокументированы
- [ ] `is_virtual` корректно выставлен для всех ВТ в тестовом запросе
