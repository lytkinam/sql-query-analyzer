# Итерация 4 — отладочный чеклист

> **Файл итерации:** `exporters/lineage.py`  
> **Тесты:** `tests/test_lineage.py`  
> **Спецификация:** `docs/output-formats/04-lineage-fields.md`  
> **Сложность:** 🔴 высокая — требует разбора SELECT-списка

---

## 1. Целевые файлы

| Файл | Описание |
|---|---|
| `tables/fields.csv` | Реестр полей: `node_id, node_name, field_ordinal, field_alias, expression, source_table, source_field, is_computed` |
| `tables/expressions.csv` | Сложные выражения: `node_id, node_name, expr_type, expr_text, output_alias, line` |
| `tables/conditions.csv` | WHERE/JOIN ON: `node_id, node_name, condition_type, expression, involved_tables, involves_parameter` |
| `tables/joins.csv` | Карта соединений: `node_id, node_name, join_type, left_source, left_alias, right_source, right_alias, on_expression` |
| `lineage/field_lineage.json` | Список `[]` — цепочки для каждого поля финального узла |
| `lineage/lineage_key_fields.json` | Объект-обёртка `{generated_at, source_file, key_fields[]}` — ключевые поля из `extractor.yaml` |
| `lineage/field_mapping.csv` | Прямое сопоставление: `output_field, final_node_id, intermediate_node_id, input_field, rule_type, transform_desc` |
| `lineage/dependency_matrix.csv` | Матрица (pivot): строки=зависимые узлы, столбцы=ID узлов, значения 0/1 |

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
    "lineage/field_mapping.csv",
    "lineage/dependency_matrix.csv",
]

for fn in expected:
    path = os.path.join(out, fn)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"  [{'OK' if size > 0 else 'MISSING/EMPTY'}] {fn}  ({size} bytes)")
```

---

## 4. Проверка парсера SELECT-списка

Функция `parse_select_list(node_text: str) -> list[dict]` принимает полный текст узла (`node["text"]`).

```python
from exporters.lineage import parse_select_list

# Тесты: (вход, ожидаемый alias, source_table, source_field, is_computed)
cases = [
    # Простая ссылка
    ("ВЫБРАТЬ ТабА.Поле ИЗ ТабА",
     "ПОЛЕ", "ТАБА", "ПОЛЕ", False),

    # KAK-алиас
    ("ВЫБРАТЬ ТабА.П КАК МойАлиас ИЗ ТабА",
     "МОЙАЛИАС", "ТАБА", "П", False),

    # Агрегат
    ("ВЫБРАТЬ СУММА(ТабА.Кол) КАК Сумма ИЗ ТабА",
     "СУММА", "ТАБА", "КОЛ", True),

    # Литерал
    ("ВЫБРАТЬ 1 КАК Признак ИЗ ТабА",
     "ПРИЗНАК", None, None, True),

    # Звёздочка
    ("ВЫБРАТЬ ТабА.* ИЗ ТабА",
     "*", "ТАБА", "*", False),

    # ВЫБОР КОГДА (ключевой сложный случай)
    ("ВЫБРАТЬ ВЫБОР КОГДА ТабА.П = 1 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ КАК Признак ИЗ ТабА",
     "ПРИЗНАК", None, None, True),

    # ISNULL
    ("ВЫБРАТЬ ЕСТЬНУЛЛ(ТабА.Сумма, 0) КАК Сумма ИЗ ТабА",
     "СУММА", "ТАБА", "СУММА", True),
]

for sql, exp_alias, exp_src_t, exp_src_f, exp_computed in cases:
    fields = parse_select_list(sql)
    f0 = fields[0]
    ok = (
        f0["field_alias"].upper() == exp_alias and
        (f0["source_table"] or "").upper() == (exp_src_t or "") and
        (f0["source_field"] or "").upper() == (exp_src_f or "") and
        f0["is_computed"] == exp_computed
    )
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {sql[:50]!r}...")
    if not ok:
        print(f"         got: alias={f0['field_alias']} src={f0['source_table']}.{f0['source_field']} computed={f0['is_computed']}")
        print(f"         exp: alias={exp_alias} src={exp_src_t}.{exp_src_f} computed={exp_computed}")
```

---

## 5. Проверка fields.csv

```python
import csv, os
from itertools import groupby

with open(os.path.join(out, "tables", "fields.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"  Итого полей: {len(rows)}")

required_cols = {"node_id", "node_name", "field_ordinal", "field_alias",
                 "expression", "source_table", "source_field", "is_computed"}
assert required_cols <= set(rows[0].keys()), f"Нет колонок: {required_cols - set(rows[0].keys())}"
print("  Колонки: OK")

# field_ordinal монотонен в рамках узла
for node_id, grp in groupby(rows, key=lambda r: r["node_id"]):
    ords = [int(r["field_ordinal"]) for r in grp]
    assert ords == list(range(len(ords))), f"node {node_id}: ординалы {ords}"
print("  field_ordinal: OK")

# is_computed — только 'true'/'false'
for r in rows:
    assert r["is_computed"] in ("true", "false"), f"is_computed='{r['is_computed']}' (ожидается true/false)"
print("  is_computed: OK")
```

---

## 6. Проверка field_lineage.json

> Структура по спецификации: корень — **список** `[]`.
> Финальное звено chain идентифицируется по `node_id == null` (физическая таблица).

```python
import json, os

with open(os.path.join(out, "lineage", "field_lineage.json"), encoding="utf-8") as f:
    lineage = json.load(f)

# корень ДОЛЖЕН быть списком
assert isinstance(lineage, list), f"Ожидается list, получено {type(lineage)}"
print(f"  Всего полей с lineage: {len(lineage)}")

dangling = []
for entry in lineage:
    # обязательные поля
    assert "output_field" in entry, f"Нет output_field: {entry}"
    assert "chain" in entry, f"Нет chain: {entry['output_field']}"
    assert "depth" in entry, f"Нет depth: {entry['output_field']}"

    chain = entry["chain"]
    if not chain:
        dangling.append(entry["output_field"])
        continue

    # последнее звено — физическая таблица: node_id == null
    last = chain[-1]
    assert last.get("node_id") is None, \
        f"Цепочка '{entry['output_field']}' не дошла до физической таблицы, последний node_id={last.get('node_id')}"
    assert last.get("source_table"), \
        f"Цепочка '{entry['output_field']}': в финальном звене нет source_table"

if dangling:
    print(f"  WARN: {len(dangling)} полей без chain: {dangling[:3]}")
else:
    print("  chain: OK — все поля имеют цепочку")
print("  Финальные звенья (node_id=null): OK")
```

---

## 7. Проверка dependency_matrix.csv

> Структура по спецификации: **pivot-матрица**.  
> Первая колонка `node_id`, остальные колонки — ID узлов, значения 0 или 1.

```python
import csv, os

with open(os.path.join(out, "lineage", "dependency_matrix.csv"), encoding="utf-8") as f:
    reader = csv.reader(f)
    headers = next(reader)
    rows = list(reader)

# первая колонка = node_id
assert headers[0] == "node_id", f"Первая колонка должна быть 'node_id', получено '{headers[0]}'"

# остальные заголовки — числовые ID
for h in headers[1:]:
    assert h.isdigit(), f"Заголовок колонки должен быть числовым ID, получено '{h}'"
print(f"  Заголовки (узлы): {headers[1:]}")

# значения — только 0 или 1
col_ids = headers[1:]
for row in rows:
    row_id = row[0]
    for i, val in enumerate(row[1:]):
        assert val in ("0", "1"), f"node {row_id} → col {col_ids[i]}: значение '{val}' (ожидается 0/1)"

# нет самозависимостей: диагональ = 0
for row in rows:
    row_id = row[0]
    if row_id in col_ids:
        idx = col_ids.index(row_id)
        assert row[1 + idx] == "0", f"node {row_id}: самозависимость в матрице"
print("  Матрица: OK (0/1, без самозависимостей)")
```

---

## 8. Проверка lineage_key_fields.json

> Структура по спецификации: объект-обёртка `{generated_at, source_file, key_fields[{field, description, chain, branching, notes}]}`.

```python
import json, os

with open(os.path.join(out, "lineage", "lineage_key_fields.json"), encoding="utf-8") as f:
    kf = json.load(f)

assert isinstance(kf, dict), f"Ожидается dict, получено {type(kf)}"
assert "generated_at" in kf, "Нет 'generated_at'"
assert "key_fields" in kf, "Нет 'key_fields'"
assert isinstance(kf["key_fields"], list), "'key_fields' должен быть списком"

for entry in kf["key_fields"]:
    assert "field" in entry, f"Нет 'field': {entry}"
    assert "chain" in entry, f"Нет 'chain': {entry['field']}"
    assert "branching" in entry, f"Нет 'branching': {entry['field']}"
    assert isinstance(entry["branching"], bool), \
        f"'branching' должен быть bool: {entry['field']}"

print(f"  key_fields: {len(kf['key_fields'])} полей")
print("  Структура: OK")
```

---

## 9. Проверка fields.csv

```python
import csv, os

with open(os.path.join(out, "tables", "fields.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"  Итого полей: {len(rows)}")

required_cols = {"node_id", "node_name", "field_ordinal", "field_alias",
                 "expression", "source_table", "source_field", "is_computed"}
assert required_cols <= set(rows[0].keys()), f"Нет колонок: {required_cols - set(rows[0].keys())}"
print("  Колонки: OK")

from itertools import groupby
for node_id, grp in groupby(rows, key=lambda r: r["node_id"]):
    ords = [int(r["field_ordinal"]) for r in grp]
    assert ords == list(range(len(ords))), f"node {node_id}: ординалы {ords}"
print("  field_ordinal: OK")
```

---

## 10. Алгоритм построения lineage (по PLAN.md)

```
1. Взять финальный узел (type=result / последняя ВТ)

2. Для каждого поля: найти выражение в SELECT-списке узла через parse_select_list(node["text"])

2.5 Построить alias_map: алиас_таблицы → имя_ВТ
    (алиас берётся из FROM/JOIN, имя_ВТ — из own_in_tables узла)
    Пример: "ПС" → "ВТ_ПенсионныеСчета"

3. Если expr = алиас.фиелд → разрешить через alias_map → имя_ВТ
    → найти узел-источник в edges_refs (где from_name == имя_ВТ)

4. Рекурсивно трассировать вглубь до физической таблицы
   (ограничение рекурсии: max_depth=20)

5. Записать цепочку как chain[]
   - Промежуточные звенья: {node_id, node_name, alias, expr}
   - Финальное звено: {node_id: null, node_name: null, source_table, source_field}
```

Вывести первые 3 цепочки вручную:

```python
for entry in lineage[:3]:
    print(f"  [{entry['output_field']}] depth={entry['depth']}")
    for step in entry["chain"]:
        nid = step.get("node_id")
        if nid is None:
            print(f"    → ФИЗ. ИСТ.: {step.get('source_table')}.{step.get('source_field')}")
        else:
            print(f"    → [{nid}] {step.get('node_name')}: {step.get('expr')}")
```

---

## 11. Что проверяем по каждому файлу

| Файл | Ключевые проверки |
|---|---|
| `tables/fields.csv` | Колонки, `field_ordinal` монотонен, `is_computed` = true/false |
| `tables/expressions.csv` | `expr_type` ∈ {ISNULL, CASE, AGGREGATE, SUBSTRING, CAST, FUNCTION, ARITHMETIC, PARAMETER}; `node_id` есть |
| `tables/conditions.csv` | `condition_type` ∈ {WHERE, JOIN_ON}; `expression` не пуста |
| `tables/joins.csv` | `join_type` ∈ {INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL JOIN, CROSS JOIN}; `on_expression` не пуст |
| `lineage/field_lineage.json` | Корень = `list[]`; `chain[-1].node_id == null`; `chain[-1].source_table` заполнен |
| `lineage/lineage_key_fields.json` | Объект `{generated_at, key_fields[]}`; каждый элемент имеет `branching: bool` |
| `lineage/field_mapping.csv` | Колонки: `output_field, final_node_id, intermediate_node_id, input_field, rule_type, transform_desc` |
| `lineage/dependency_matrix.csv` | pivot-матрица; заголовки[1:] = числа; значения 0/1; диагональ = 0 |

---

## 12. Проверка регрессий на итерациях 1-3

```bash
pytest tests/test_normalizer.py -v
pytest tests/test_tables.py -v
pytest tests/test_graph.py -v

# все сразу
pytest tests/ -v --tb=short 2>&1 | tail -30
```

---

## 13. Известные ограничения итерации 4

- **Regex-парсер SELECT** работает на простых случаях. `ВЫБОР КОГДА` и вложенные функции → `is_computed=True` без распарски выражения.
- **`*` в SELECT** (`ТабА.*`) — `source_field="*"`, `is_computed=False`, lineage не строится.
- **alias_map** строится regex-парсингом FROM/JOIN. Если у таблицы нет явного алиаса — имя таблицы используется как алиас.
- **Циклические зависимости** — ограничение рекурсии `max_depth=20`.
- **`extractor.yaml`** опционален. Если отсутствует — `lineage_key_fields.json` включает все поля.
- **Большой пример** (`example_258.sql`) — итоговый `fields.csv` может содержать несколько тысяч строк.

---

## 14. Чеклист перед коммитом

- [ ] `pytest tests/test_lineage.py -v` — все зелёные
- [ ] `pytest tests/ -v` — итерации 1-3 без регрессий
- [ ] Раздел 3: все **8** файлов сгенерированы с ненулевым размером
- [ ] Раздел 4: парсер SELECT прошёл все 7 случаев (включая ВЫБОР КОГДА и ЕСТьНУЛЛ)
- [ ] Раздел 6: `field_lineage.json` — корень `list[]`, `chain[-1].node_id == null`
- [ ] Раздел 7: `dependency_matrix.csv` — pivot-матрица, заголовки числовые, диагональ = 0
- [ ] Раздел 8: `lineage_key_fields.json` — объект с `generated_at` + `key_fields[]`, `branching: bool`
- [ ] Раздел 10: первые 3 цепочки выглядят осмысленно
- [ ] Большой пример: `generate_lineage(model_258, out)` завершается без исключений
