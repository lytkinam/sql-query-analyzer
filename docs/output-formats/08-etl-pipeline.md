# Форматы ETL и воспроизводимой обработки

Файлы для управления пайплайном генерации артефактов: схемы, манифесты, логи, валидация.

---

## Pipeline manifest — `pipeline.yaml`

**Назначение:** описание всего пайплайна генерации артефактов. Позволяет воспроизвести полный набор файлов из исходного JSON.

**Структура:**
```yaml
version: 1
source:
  file: 258_npo_analysis.json
  sha256: "abc123..."
  parsed_at: "2026-06-02T12:00:00"

steps:
  - id: normalize
    output:
      - normalized/nodes.json
      - normalized/tempqueries.json
      - normalized/subqueries.json

  - id: tables
    depends_on: [normalize]
    output:
      - tables/nodes.csv
      - tables/edges_parent.csv
      - tables/edges_refs.csv
      - tables/sources_map.csv
      - tables/fields.csv
      - tables/joins.csv
      - tables/conditions.csv

  - id: texts
    depends_on: [normalize]
    output:
      - texts/node_*.sql
      - texts/node_*.md

  - id: lineage
    depends_on: [tables, texts]
    output:
      - lineage/field_lineage.json
      - lineage/lineage_key_fields.json

  - id: graph
    depends_on: [tables]
    output:
      - graph/query_graph.json
      - graph/query_graph.dot
      - graph/query_graph.mmd
      - graph/query_graph.gexf

  - id: reports
    depends_on: [lineage, graph]
    output:
      - reports/overview.md
      - reports/catalog.xlsx

  - id: search
    depends_on: [texts]
    output:
      - search/corpus.jsonl
      - search/chunks.jsonl
      - search/inverted_index.json
```

---

## JSON Schema — `schema.json`

**Назначение:** валидация структуры всех производных JSON-файлов.

**Структура (для `nodes.json`):**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "QueryNodes",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["id", "name", "type", "text", "isstub", "isunionpart"],
    "properties": {
      "id":          {"type": "integer"},
      "name":        {"type": "string"},
      "type":        {"type": "string", "enum": ["tempquery", "subquery"]},
      "text":        {"type": "string"},
      "parentid":    {"type": ["integer", "null"]},
      "maxparentid": {"type": "integer"},
      "childrenids": {"type": "array", "items": {"type": "integer"}},
      "ownintables": {"type": "array", "items": {"type": "string"}},
      "isstub":      {"type": "boolean"},
      "isunionpart": {"type": "boolean"}
    }
  }
}
```

---

## Data dictionary — `dictionary.md`

**Назначение:** описание каждого поля во всех таблицах и JSON-структурах. Устраняет неоднозначность при совместной работе.

**Структура:**
```markdown
## nodes.csv

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| id | int | да | Уникальный ID узла |
| name | string | нет | Имя ВТ или номер части объединения |
| type | enum | да | tempquery или subquery |
| parentid | int\|null | нет | ID родителя, null у корневых ВТ |
...
```

---

## Processing log — `processing.jsonl`

**Назначение:** журнал событий генерации: успехи, предупреждения, ошибки, время обработки.

**Структура:**
```jsonl
{"ts": "2026-06-02T12:00:01", "level": "INFO",  "step": "normalize", "msg": "Processed 296 nodes"}
{"ts": "2026-06-02T12:00:02", "level": "WARN",  "step": "fields",    "msg": "Node 42: text too complex for AST extraction", "node_id": 42}
{"ts": "2026-06-02T12:00:05", "level": "ERROR", "step": "lineage",   "msg": "Field НомерДоговора: chain broken at node 71 (stub)", "node_id": 71}
```

---

## Validation report — `validation.csv`

**Назначение:** контроль целостности: дублирующиеся ID, битые ссылки, пустые обязательные поля, несвязные узлы.

**Структура:**
```csv
check_name,status,affected_ids,count,description
duplicate_ids,PASS,,0,No duplicate node IDs found
broken_parentid,WARN,"71;126",2,parentid references non-existent nodes
empty_name,INFO,"0;16",2,Nodes with empty name (likely stubs)
orphan_nodes,WARN,"42",1,Node has no parent and no children
```

---

## Checksums — `checksums.txt`

**Назначение:** контроль неизменности артефактов. Позволяет обнаружить случайные изменения файлов.

**Структура:**
```
sha256:a1b2c3...  nodes.json
sha256:d4e5f6...  nodes.csv
sha256:789abc...  field_lineage.json
```

---

## Version manifest — `version.json`

**Назначение:** трассировка происхождения всего набора артефактов.

**Структура:**
```json
{
  "generated_at": "2026-06-02T12:00:00",
  "generator": "sql_query_analyzer",
  "generator_version": "0.1.0",
  "source_file": "258_npo_analysis.json",
  "source_sha256": "abc123...",
  "total_nodes": 296,
  "total_tempqueries": 85,
  "total_subqueries": 211,
  "output_files": 42
}
```

---

## Config file — `extractor.yaml`

**Назначение:** конфигурация правил извлечения. Позволяет повторно запустить генерацию с теми же параметрами.

**Структура:**
```yaml
extractor:
  key_fields:
    - НомерДоговора
    - ВидОбязательств
    - ПенсионныйСчет
    - КодСхемы

  skip_stubs: true
  normalize_sql: true
  chunk_size: 512
  chunk_overlap: 64
  embedding_model: intfloat/multilingual-e5-large

  output_dir: ./output
  include_formats:
    - json
    - csv
    - sql
    - lineage
    - graph
    - xlsx
```
