# Итерация 2 — отладочный чеклист

> **Файл итерации:** `exporters/texts.py`  
> **Тесты:** `tests/test_texts.py`

---

## 1. Запуск тестов

```bash
# все тесты итерации 2
pytest tests/test_texts.py -v

# отдельные классы
pytest tests/test_texts.py::TestNormalizeSql -v
pytest tests/test_texts.py::TestTextsSmall -v
pytest tests/test_texts.py::TestTextsLarge -v

# обе итерации сразу
pytest tests/test_exporters.py tests/test_texts.py -v
```

---

## 2. Ручная проверка generate_texts

```python
import json, tempfile, os
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.texts import generate_texts

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

model = normalize(json.loads(analyze_sql_query(sql, detailed=True)))
out = tempfile.mkdtemp()
generate_texts(model, out)

texts_dir = os.path.join(out, "query_texts")

# перечень ожидаемых файлов
fixed = [
    "texts_index.json",
    "normalized_queries.sql",
]
for fn in fixed:
    path = os.path.join(texts_dir, fn)
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    print(f"  [{'OK' if exists else 'MISSING'}] {fn}  ({size} bytes)")

# по одному .sql и .md на каждый узел
for node in model["nodes"][:3]:
    for ext in ("sql", "md"):
        p = os.path.join(texts_dir, f"node_{node['id']}.{ext}")
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] node_{node['id']}.{ext}")
```

---

## 3. Проверка normalize_sql

```python
from exporters.texts import normalize_sql

cases = [
    ("выбрать 1 из Справочник.Номенклатура",  "ВЫБРАТЬ"),   # 1С кючевое слово
    ("select 1 from dual",                      "SELECT"),  # ANSI
    ("ВЫБРАТЬ   1    ИЗ   Т",                 "ВЫБРАТЬ 1 ИЗ Т"),  # пробелы
]

for inp, expected_start in cases:
    result = normalize_sql(inp)
    ok = expected_start in result
    print(f"  [{'OK' if ok else 'FAIL'}] вход={inp[:30]!r} -> {result[:40]!r}")
```

---

## 4. Проверка индекса

```python
import json, os

# out - каталог из предыдущего блока
with open(os.path.join(out, "query_texts", "texts_index.json"), encoding="utf-8") as f:
    index = json.load(f)

print(f"Узлов в индексе: {len(index)}")
print(f"Поля: {list(index[0].keys())}")
print(f"Пример записи: {index[0]}")

# Проверяем уникальность node_id
ids = [e["node_id"] for e in index]
assert len(ids) == len(set(ids)), "FAIL: дубликаты node_id"
print("Уникальность node_id: OK")

# Проверяем, что все .sql файлы доступны
for entry in index:
    path = os.path.join(out, entry["path"])
    if not os.path.exists(path):
        print(f"  MISSING: {entry['path']}")
print("Проверка path: OK")
```

---

## 5. Что проверяем по каждому файлу

| Файл | Ключевые проверки |
|---|---|
| `node_{id}.sql` | начинается с `-- Node ID:`; содержит `-- Name:`, `-- Type:`, `-- Parent:`, `-- OwnInTables:` |
| `node_{id}.md` | начинается с `# `; содержит id узла; есть блок ` ```sql ` |
| `texts_index.json` | валидный JSON-массив; поля: `node_id, name, path, text_len, text_hash, line_count`; `text_hash` начинается с `sha256:` |
| `normalized_queries.sql` | содержит `-- =====`; все ключевые слова в UPPER CASE; ненулевой размер |

---

## 6. Нормализация SQL — проверочные примеры

| Вход | Ожидаемый результат |
|---|---|
| `выбрать 1 из Т` | `ВЫБРАТЬ 1 ИЗ Т` |
| `select 1 from dual` | `SELECT 1 FROM dual` |
| `ВЫБРАТЬ   1    ИЗ   Т` | `ВЫБРАТЬ 1 ИЗ Т` |
| `выбор когда 1=1 тогда 1 иначе 0 конец` | `ВЫБОР КОГДА 1=1 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ` |
| `"" (пустая строка)` | `""` |

---

## 7. Известные ограничения итерации 2

- `normalize_sql` работает на уровне целых ключевых слов; частичные совпадения внутри идентификаторов не затрагиваются (префикс `Из` в именах таблиц не преобразуется в `ИЗ`).
- Файл `normalized_queries.sql` включает `temp_query` и `sub_query` (части UNION); заглушки (`is_stub=true`) отдельно не фильтруются — они попадут с пустым текстом.
- `line_count` в индексе считается по `text.strip().splitlines()`, поэтому будет 0 для узлов без текста (заглушки).

---

## 8. Чеклист перед коммитом

- [ ] `pytest tests/test_texts.py -v` — все зелёные
- [ ] `pytest tests/test_exporters.py tests/test_texts.py -v` — обе итерации не регрессируют
- [ ] Ручная проверка раздела 2 пройдена
- [ ] Ручная проверка раздела 3 пройдена
- [ ] `node_{id}.sql` — начинается с `-- Node ID:` для первых 3 узлов
- [ ] `normalized_queries.sql` содержит `-- =====` и ненулевого размера
- [ ] Индекс содержит хаши формата `sha256:...`
