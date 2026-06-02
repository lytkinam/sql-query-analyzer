# Итерация 4 — отладочный чеклист

> **Файл итерации:** `exporters/lineage.py`  
> **Тесты:** `tests/test_lineage.py`  
> **Сложность:** 🔴 высокая — требует разбора SELECT-списка

---

## 1. Целевые файлы

По завершении итерации должны генерироваться:

| Файл | Описание |
|---|---|
| `tables/fields.csv` | Реестр полей: `node_id, node_name, field_ordinal, field_alias, expression, source_table, source_field, is_computed` |
| `tables/expressions.csv` | ISNULL, ВЫБОР КОГДА, агрегаты |
| `tables/conditions.csv` | WHERE, JOIN ON |
| `tables/joins.csv` | Карта соединений |
| `lineage/field_lineage.json` | Цепочки по каждому полю финального узла |
| `lineage/lineage_key_fields.json` | Только ключевые поля из `extractor.yaml` |
| `lineage/dependency_matrix.csv` | Матрица: узел X зависит от узла Y |

---

## 2. Запуск тестов

```bash
# только итерация 4
pytest tests/test_lineage.py -v

# отдельные классы
pytest tests/test_lineage.py::TestLineageFilesExist -v
pytest tests/test_lineage.py::TestFields -v
pytest tests/test_lineage.py::TestExpressions -v
pytest tests/test_lineage.py::TestJoins -v
pytest tests/test_lineage.py::TestFieldLineage -v
pytest tests/test_lineage.py::TestDependencyMatrix -v

# все четыре итерации
pytest tests/ -v --tb=short
```

---

## 3. Ручная проверка generate_lineage

```python
import json, tempfile, os
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.lineage import generate_lineage

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

model = normalize(json.loads(analyze_sql_query(sql, detailed=True)))
out = tempfile.mkdtemp()
generate_lineage(model, out)

expected = [
    "tables/fields.csv",
    "tables/expressions.csv",
    "tables/conditions.csv",
    "tables/joins.csv",
    "lineage/field_lineage.json",
    "lineage/lineage_key_fields.json",
    "lineage/dependency_matrix.csv",
]

for fn in expected:
    path = os.path.join(out, fn)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"  [{'OK' if size > 0 else 'MISSING/EMPTY'}] {fn}  ({size} bytes)")
```

---

## 4. Проверка парсера SELECT-списка

Проверяем что парсер правильно разбирает разные формы SELECT-списка:

```python
from exporters.lineage import parse_select_list

cases = [
    # (вход, ожидаемый alias, source_table, source_field, is_computed)
    ("ТабА.Поле",     "ПОЛЕ",   "ТАБА",   "ПОЛЕ",   False),
    ("ТабА.П КАК МойАлиас", "МОЙАЛИАС", "ТАБА", "П",     False),
    ("СУММА(ТабА.Кол) КАК Сумма", "СУММА",  "ТАБА",   "КОЛ",   True),
    ("1 КАК Признак",           "ПРИЗНАК", None,    None,    True),
    ("ТабА.*",               "*",      "ТАБА",   "*",     False),
]

for expr, exp_alias, exp_src_t, exp_src_f, exp_computed in cases:
    fields = parse_select_list(f"ВЫБРАТЬ {expr} ИЗ ТабА")
    f0 = fields[0]
    ok = (
        f0["field_alias"].upper() == exp_alias and
        (f0["source_table"] or "").upper() == (exp_src_t or "") and
        (f0["source_field"] or "").upper() == (exp_src_f or "") and
        f0["is_computed"] == exp_computed
    )
    print(f"  [{'OK' if ok else 'FAIL'}] {expr!r} → alias={f0['field_alias']} src={f0['source_table']}.{f0['source_field']} computed={f0['is_computed']}")
```

---

## 5. Проверка fields.csv

```python
import csv, os

with open(os.path.join(out, "tables", "fields.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"  Итого полей: {len(rows)}")

# проверяем колонки
required_cols = {"node_id", "node_name", "field_ordinal", "field_alias",
                 "expression", "source_table", "source_field", "is_computed"}
assert required_cols <= set(rows[0].keys()), f"Нет колонок: {required_cols - set(rows[0].keys())}"
print("  Колонки: OK")

# field_ordinal должен быть монотонным в рамках узла
from itertools import groupby
for node_id, grp in groupby(rows, key=lambda r: r["node_id"]):
    ords = [int(r["field_ordinal"]) for r in grp]
    assert ords == list(range(len(ords))), f"node {node_id}: ординалы {ords}"
print("  field_ordinal: OK")
```

---

## 6. Проверка field_lineage.json

```python
import json, os

with open(os.path.join(out, "lineage", "field_lineage.json"), encoding="utf-8") as f:
    lineage = json.load(f)

# общая структура
assert "fields" in lineage, "нет ключа 'fields'"
print(f"  Всего полей с lineage: {len(lineage['fields'])}")

# проверяем структуру каждой записи
dangling = []
for entry in lineage["fields"]:
    if "chain" not in entry:
        dangling.append(entry.get("field_alias", "?"))
    if entry.get("chain"):
        # последнее звено цепочки должно быть физическим источником
        last = entry["chain"][-1]
        assert last.get("source_kind") != "TempTable", \
            f"Цепочка заканчивается на ВТ: {entry['field_alias']}"

if dangling:
    print(f"  WARN: {len(dangling)} полей без chain: {dangling[:3]}")
else:
    print("  chain: OK — все поля имеют цепочку")
print("  Физические источники: OK")
```

---

## 7. Проверка dependency_matrix.csv

```python
import csv, os

with open(os.path.join(out, "lineage", "dependency_matrix.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"  Строк в матрице: {len(rows)}")

# проверяем колонки
required = {"from_node_id", "from_node_name", "to_node_id", "to_node_name", "depends_on"}
assert required <= set(rows[0].keys()), f"Нет колонок: {required - set(rows[0].keys())}"

# нет самозависимостей
self_deps = [r for r in rows if r["from_node_id"] == r["to_node_id"]]
if self_deps:
    print(f"  WARN: {len(self_deps)} самозависимостей: {[r['from_node_name'] for r in self_deps[:3]]}")
else:
    print("  Самозависимостей: нет (OK)")
```

---

## 8. Что проверяем по каждому файлу

| Файл | Ключевые проверки |
|---|---|
| `tables/fields.csv` | Колонки, `field_ordinal` монотонен, `node_id` существует в `nodes.csv` |
| `tables/expressions.csv` | `expr_type` ∈ {CASE, ISNULL, AGGREGATE, ARITHMETIC}; `node_id` есть |
| `tables/conditions.csv` | `cond_type` ∈ {WHERE, JOIN_ON}; не пустой `expression` |
| `tables/joins.csv` | `join_type` ∈ {ЛЕВОЕ, ПОЛНОЕ, ВНУТРЕННЕЕ, LEFT, FULL, INNER}; `on_condition` не пуст |
| `lineage/field_lineage.json` | Каждое поле имеет `chain[]`; последний узел — физическая таблица |
| `lineage/lineage_key_fields.json` | Только поля из `extractor.yaml::key_fields`; структура = `field_lineage.json` |
| `lineage/dependency_matrix.csv` | Нет самозависимостей; матрица = подмножество `edges_refs` |

---

## 9. Алгоритм построения lineage (по PLAN.md)

```
1. Взять финальный узел (type=result / последняя ВТ)
2. Для каждого поля: найти выражение в SELECT-списке узла
3. Если expr = алиас.field → найти узел-источник через edges_refs
4. Рекурсивно трассировать вглубь до физической таблицы
5. Записать цепочку как chain[]
```

Проверка алгоритма вручную:

```python
import json, os

with open(os.path.join(out, "lineage", "field_lineage.json"), encoding="utf-8") as f:
    lineage = json.load(f)

# вывести первые 3 цепочки
for entry in lineage["fields"][:3]:
    print(f"  [{entry['field_alias']}]")
    for step in entry.get("chain", []):
        print(f"    → {step.get('node_name', '?')}.{step.get('field', '?')} ({step.get('source_kind', '?')})")
```

---

## 10. Проверка регрессий на итерациях 1-3

```bash
pytest tests/test_normalizer.py -v
pytest tests/test_tables.py -v
pytest tests/test_graph.py -v

# все сразу
pytest tests/ -v --tb=short 2>&1 | tail -30
```

---

## 11. Известные ограничения итерации 4

- **Regex-парсер SELECT** работает на простых случаях. Сложные выражения  
  (`ВЫБОР КОГДА`, вложенные функции) получают `is_computed=True` без распарски.
- **`extractor.yaml`** опционален. Если отсутствует — `lineage_key_fields.json` = `field_lineage.json`.
- **Циклические зависимости** (ВТА читает саму себя) — ограничение рекурсии по `max_depth=20`.
- **`*` в SELECT** (`ТабА.*`) — `source_field="*"`, `is_computed=False`, lineage не строится.
- **Большой пример** (`example_258.sql`) — итоговый `fields.csv` может содержать несколько тысяч строк.

---

## 12. Чеклист перед коммитом

- [ ] `pytest tests/test_lineage.py -v` — все зелёные
- [ ] `pytest tests/ -v` — итерации  1-3 без регрессий
- [ ] Раздел 3: все 7 файлов сгенерированы с ненулевым размером
- [ ] Раздел 4: парсер SELECT прошёл все 5 случаев
- [ ] Раздел 9: первые 3 цепочки выведены и выглядят осмысленно
- [ ] Раздел 7: в `dependency_matrix.csv` нет самозависимостей
- [ ] Большой пример: `generate_lineage(model_258, out)` завершается без исключений
