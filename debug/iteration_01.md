# Итерация 1 — отладочный чеклист

> **Файлы итерации:** `exporters/normalizer.py`, `exporters/tables.py`
> **Тесты:** `tests/test_exporters.py`

---

## 1. Подготовка окружения

```bash
# установить зависимости (если есть requirements.txt)
pip install -r requirements.txt

# убедиться, что анализатор доступен
python -c "from sql_query_analyzer import analyze_sql_query; print('OK')"
```

---

## 2. Запуск тестов

```bash
# все тесты итерации 1
pytest tests/test_exporters.py -v

# только один класс
pytest tests/test_exporters.py::TestNormalizerSmall -v
pytest tests/test_exporters.py::TestClassifySource -v
pytest tests/test_exporters.py::TestTablesSmall -v
pytest tests/test_exporters.py::TestTablesLarge -v
```

---

## 3. Ручная проверка нормализатора

```python
import json
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

raw = json.loads(analyze_sql_query(sql, detailed=True))
model = normalize(raw)

# проверить: нет type="result"
types = {n["type"] for n in model["nodes"]}
assert "result" not in types, f"FAIL: найден result: {types}"
print("types OK:", types)

# проверить: data-flow рёбра имеют relation
refs = [e for e in model["edges"] if e["relation"] == "ref"]
print(f"ref edges: {len(refs)}")

# проверить: структурные рёбра
structural = [e for e in model["edges"] if e["relation"] in ("parent_child", "union_part")]
print(f"structural edges: {len(structural)}")

# проверить: source_kinds заполнены
for n in model["nodes"]:
    assert len(n["source_kinds"]) == len(n["own_in_tables"]), \
        f"FAIL: node {n['id']} — source_kinds/own_in_tables mismatch"
print("source_kinds OK")
```

---

## 4. Ручная проверка generate_tables

```python
import json, tempfile, os
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.tables import generate_tables

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

model = normalize(json.loads(analyze_sql_query(sql, detailed=True)))
out = tempfile.mkdtemp()
generate_tables(model, out)

# ожидаемые файлы
expected = [
    "normalized/nodes.json",
    "normalized/nodes.jsonl",
    "normalized/tempqueries.json",
    "normalized/subqueries.json",
    "tables/nodes.csv",
    "tables/tempqueries_catalog.csv",
    "tables/edges_parent.csv",
    "tables/edges_refs.csv",
    "tables/sources_map.csv",
    "tables/union_parts.csv",
    "tables/stubs.csv",
]

for rel in expected:
    path = os.path.join(out, rel)
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    status = "OK" if exists else "MISSING"
    print(f"  [{status}] {rel}  ({size} bytes)")
```

---

## 5. Что проверяем по каждому файлу

| Файл | Ключевые проверки |
|---|---|
| `nodes.csv` | нет `type=result`; `children_count` ≥ 0; `is_stub` = `true`/`false` |
| `tempqueries_catalog.csv` | только `type=temp_query`; `union_parts` — `;`-разделённый список |
| `edges_parent.csv` | `relation` ∈ {`parent_child`, `union_part`}; `depth` ≥ 1 у дочерних |
| `edges_refs.csv` | `relation = ref`; `from_id ≠ to_id` |
| `sources_map.csv` | `source_kind` ∈ известному набору; `ordinal` начинается с 1 |
| `union_parts.csv` | `is_union_part = true`; `part_number` ≥ 1; `parent_query_id` заполнен |
| `stubs.csv` | `is_stub = true`; `reason` ∈ {`empty_body`, `no_consumers`} |
| `normalized/nodes.json` | валидный JSON-массив; нет поля `source_kinds` (внутреннее) |
| `normalized/nodes.jsonl` | кол-во строк == len(nodes.json) |
| `normalized/tempqueries.json` | все записи `type=temp_query` |
| `normalized/subqueries.json` | все записи `type=sub_query` |

---

## 6. Классификатор источников — проверочные примеры

| Входная строка | Ожидаемый `source_kind` |
|---|---|
| `Справочник.Контрагенты` | `Catalog` |
| `РегистрНакопления.ПенсионныеСчета` | `AccumulationRegister` |
| `РегистрСведений.НастройкиПользователей` | `InformationRegister` |
| `Документ.ПоступлениеТоваров` | `Document` |
| `РегистрБухгалтерии.Хозрасчетный` | `AccountingRegister` |
| `ВТ_Результат` | `TempTable` |
| `~TT~ВТ_Результат` | `TempTable` |
| `МойПроизвольныйАлиас` | `Unknown` |

---

## 7. Известные ограничения итерации 1

- `reason` в `stubs.csv` определяется только по двум правилам (`empty_body` / `no_consumers`); более точная классификация — в следующих итерациях.
- `classify_source` не учитывает суффиксы виртуальных таблиц (`.ОстаткиИОбороты`, `.СрезПоследних` и т.д.) — они попадают в тот же `source_kind`, что и базовый объект. Доработка запланирована.
- Поле `depth` в `edges_parent.csv` вычисляется через BFS от корней (`parent_id=null`); если граф содержит циклы (некорректный ввод) — BFS зависнет.

---

## 8. Чеклист перед коммитом

- [ ] `pytest tests/test_exporters.py -v` — все зелёные
- [ ] Ручная проверка раздела 3 пройдена
- [ ] Ручная проверка раздела 4 пройдена — все файлы созданы и ненулевого размера
- [ ] `edges_refs.csv` содержит хотя бы одну строку на примере с ВТ
- [ ] `tempqueries_catalog.csv` — нет строк с `type != temp_query`
- [ ] `sources_map.csv` — нет строк с пустым `source_kind`
