# Итерация 3 — отладочный чеклист

> **Файл итерации:** `exporters/graph.py`  
> **Тесты:** `tests/test_graph.py`

---

## 1. Запуск тестов

```bash
# все тесты итерации 3
pytest tests/test_graph.py -v

# отдельные классы
pytest tests/test_graph.py::TestGraphFilesExist -v
pytest tests/test_graph.py::TestFlatGraph -v
pytest tests/test_graph.py::TestTree -v
pytest tests/test_graph.py::TestMermaid -v
pytest tests/test_graph.py::TestDot -v
pytest tests/test_graph.py::TestGexf -v
pytest tests/test_graph.py::TestGraphml -v
pytest tests/test_graph.py::TestCytoscape -v
pytest tests/test_graph.py::TestD3 -v
pytest tests/test_graph.py::TestGraphLarge -v

# все три итерации сразу
pytest tests/ -v
```

---

## 2. Ручная проверка generate_graph

```python
import json, tempfile, os
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.graph import generate_graph

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

model = normalize(json.loads(analyze_sql_query(sql, detailed=True)))
out = tempfile.mkdtemp()
generate_graph(model, out)

expected = [
    "query_graph.json",
    "query_tree.json",
    "query_graph.mmd",
    "query_graph.dot",
    "query_graph.gexf",
    "query_graph.graphml",
    "cytoscape.json",
    "d3_graph.json",
]

graph_dir = os.path.join(out, "graph")
for fn in expected:
    path = os.path.join(graph_dir, fn)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"  [{'OK' if size > 0 else 'MISSING/EMPTY'}] {fn}  ({size} bytes)")
```

---

## 3. Проверка цветовой схемы DOT

```python
import json, tempfile, os
from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.graph import generate_graph

with open("examples/example.sql", encoding="utf-8") as f:
    sql = f.read()

model = normalize(json.loads(analyze_sql_query(sql, detailed=True)))
out = tempfile.mkdtemp()
generate_graph(model, out)

with open(os.path.join(out, "graph", "query_graph.dot"), encoding="utf-8") as f:
    dot = f.read()

# проверяем цвета
for color in ("lightgreen", "lightblue", "lightyellow", "lightsalmon"):
    count = dot.count(color)
    print(f"  {color}: {count} узлов")
```

---

## 4. Проверка целостности D3-графа

```python
import json, os

# out из предыдущего блока
with open(os.path.join(out, "graph", "d3_graph.json"), encoding="utf-8") as f:
    d3 = json.load(f)

node_ids = {n["id"] for n in d3["nodes"]}
dangling = [
    lnk for lnk in d3["links"]
    if lnk["source"] not in node_ids or lnk["target"] not in node_ids
]
if dangling:
    print(f"FAIL: {len(dangling)} свисающих рёбер: {dangling[:3]}")
else:
    print("D3 целостность: OK")
```

---

## 5. Что проверяем по каждому файлу

| Файл | Ключевые проверки |
|---|---|
| `query_graph.json` | `nodes[]` + `edges[]`; только `ref`-рёбра; поля `id, label, type` / `from, to, label` |
| `query_tree.json` | список корней; каждый узел имеет `children[]`; BFS даёт то же кол-во |
| `query_graph.mmd` | начинается с `graph TD`; `n{id}[...]` для каждого узла; `-->` для каждого ref |
| `query_graph.dot` | `digraph QueryGraph { rankdir=LR; ... }`; цвета lightgreen/lightblue/lightyellow/lightsalmon |
| `query_graph.gexf` | валидный XML; `<gexf>`; кол-во `<node>` == len(nodes) |
| `query_graph.graphml` | валидный XML; `<graphml>`; есть `<key>` для name, type |
| `cytoscape.json` | `elements.nodes[]` + `elements.edges[]`; `data.id` — строка |
| `d3_graph.json` | `nodes[]` + `links[]`; `source`/`target` — числа; `group` ∈ {0,1,2} |

---

## 6. Цветовая схема DOT

| Условие | Цвет |
|---|---|
| `is_stub=true` | `lightyellow` |
| `type=temp_query` + есть исходящие ref | `lightgreen` |
| `type=temp_query` + нет исходящих ref (финальный) | `lightsalmon` |
| `type=sub_query` | `lightblue` |

---

## 7. Известные ограничения итерации 3

- `query_tree.json` строится только по `parent_id`/`children_ids`; если в модели есть циклы — дерево может зациклиться.
- `query_graph.mmd` не содержит стилей узлов (Mermaid ограничен); цвет — только DOT.
- SVG/PNG не генерируются автоматически (требуется `graphviz`): `dot -Tsvg graph/query_graph.dot -o graph/query_graph.svg`
- `ET.indent()` требует Python ≥ 3.9.

---

## 8. Чеклист перед коммитом

- [ ] `pytest tests/test_graph.py -v` — все зелёные
- [ ] `pytest tests/ -v` — все три итерации без регрессий
- [ ] Ручная проверка раздела 2 пройдена — все 8 файлов `OK`
- [ ] Ручная проверка раздела 3 — цвета DOT присутствуют
- [ ] Ручная проверка раздела 4 — D3 целостность OK (нет свисающих рёбер)
- [ ] GEXF и GraphML валидный XML (`ET.parse` не падает)
