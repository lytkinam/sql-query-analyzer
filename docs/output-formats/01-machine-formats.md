# Базовые машинно-читаемые форматы

Основные форматы для хранения, передачи и потоковой обработки данных из сводного JSON.

---

## JSON — `nodes.json`

**Назначение:** основной нормализованный обменный формат. Используется как единый источник истины для всех последующих трансформаций.

**Структура:**
```json
[
  {
    "id": 132,
    "name": "ВТ_ПенсионныеСчета",
    "type": "tempquery",
    "text": "ВЫБРАТЬ ...",
    "parentid": null,
    "maxparentid": 132,
    "childrenids": [133],
    "ownintables": ["РегистрНакопления.ПенсионныеСчета"],
    "isstub": false,
    "isunionpart": false
  }
]
```

**Поля:**
| Поле | Тип | Описание |
|---|---|---|
| `id` | int | Уникальный идентификатор узла |
| `name` | string | Имя ВТ или номер части объединения |
| `type` | enum | `tempquery` — ВТ, `subquery` — подзапрос/часть ОБЪЕДИНИТЬ |
| `text` | string | Исходный текст узла на языке 1С |
| `parentid` | int\|null | ID родительского узла (null у корневых) |
| `maxparentid` | int | ID корневой ВТ для данного поддерева |
| `childrenids` | int[] | ID дочерних узлов |
| `ownintables` | string[] | Таблицы, непосредственно используемые узлом |
| `isstub` | bool | Узел является технической заглушкой |
| `isunionpart` | bool | Узел — часть ОБЪЕДИНИТЬ/ОБЪЕДИНИТЬ ВСЕ |

---

## JSON Lines — `nodes.jsonl`

**Назначение:** потоковая обработка, grep/jq, загрузка в AI-пайплайны. Каждая строка — один валидный JSON-объект.

**Структура:** одна строка = один узел из `nodes.json`.

```jsonl
{"id": 132, "name": "ВТ_ПенсионныеСчета", "type": "tempquery", ...}
{"id": 133, "name": "1", "type": "subquery", ...}
```

**Использование:** `cat nodes.jsonl | jq 'select(.type == "tempquery")'`

---

## NDJSON — `edges.ndjson`

**Назначение:** потоковая генерация рёбер графа, логи обработки, инкрементальное обновление.

**Структура:**
```jsonl
{"from": 123, "to": 132, "relation": "ref", "fromname": "ВТ_Итог", "toname": "ВТ_ПенсионныеСчета"}
{"from": 130, "to": 131, "relation": "parent_child", "depth": 1}
```

---

## CSV — `nodes.csv`

**Назначение:** Excel, pandas, SQL-импорт, быстрая фильтрация и аналитика. Длинный `text` сокращается или выносится в отдельный файл.

**Структура (колонки):**
`id, name, type, parentid, maxparentid, children_count, ownintables_count, isstub, isunionpart, text_len`

**Пример:**
```csv
id,name,type,parentid,maxparentid,children_count,ownintables_count,isstub,isunionpart,text_len
132,ВТ_ПенсионныеСчета,tempquery,,132,1,3,false,false,1240
133,1,subquery,132,132,0,0,false,true,18
```

---

## TSV — `nodes.tsv`

**Назначение:** альтернатива CSV если в текстах узлов много запятых и кавычек. Используется в Unix-утилитах (`cut`, `awk`).

**Структура:** идентична CSV, разделитель `\t`.

---

## XML — `nodes.xml`

**Назначение:** формальная схема, XSD-валидация, XPath-запросы, интеграция с системами на основе XML (например, 1С XML-обмен).

**Структура:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<QueryNodes>
  <Node id="132" name="ВТ_ПенсионныеСчета" type="tempquery"
        parentid="" isstub="false" isunionpart="false">
    <OwnInTables>
      <Table>РегистрНакопления.ПенсионныеСчета</Table>
    </OwnInTables>
    <Children>
      <ChildId>133</ChildId>
    </Children>
    <Text><![CDATA[ВЫБРАТЬ ...]]></Text>
  </Node>
</QueryNodes>
```

---

## YAML — `manifest.yaml`

**Назначение:** конфигурация, манифесты, ручная правка человеком. Не для больших данных.

**Структура:**
```yaml
query_id: 258
source_file: 258_npo_analysis.json
total_nodes: 296
tempqueries:
  - id: 132
    name: ВТ_ПенсионныеСчета
    children: [133]
    sources:
      - РегистрНакопления.ПенсионныеСчета
```

---

## Parquet — `nodes.parquet`

**Назначение:** колонночное хранение для больших объёмов. Быстрая аналитика в DuckDB, Apache Arrow, Spark, pandas.

**Структура:** аналогична `nodes.csv`, но в бинарном колонночном формате с типизацией.

**Генерация (Python):**
```python
import pandas as pd
df = pd.read_csv('nodes.csv')
df.to_parquet('nodes.parquet', index=False)
```

---

## SQLite — `analysis.sqlite`

**Назначение:** самый практичный локальный формат для SQL-запросов по всему графу. Позволяет объединять узлы, рёбра, поля и источники в одном файле.

**Таблицы:**
```sql
CREATE TABLE nodes (id, name, type, parentid, maxparentid, isstub, isunionpart, text);
CREATE TABLE edges (from_id, to_id, relation, fromname, toname);
CREATE TABLE sources (node_id, table_name, ordinal);
CREATE TABLE fields (node_id, alias, expression, source_field);
```

**Генерация:**
```python
import sqlite3, json
conn = sqlite3.connect('analysis.sqlite')
# INSERT nodes, edges, sources...
```

---

## DuckDB — `analysis.duckdb`

**Назначение:** аналитическая in-process БД. Быстрее SQLite для аналитических запросов (GROUP BY, оконные функции, JOIN по большим таблицам).

**Использование:**
```python
import duckdb
conn = duckdb.connect('analysis.duckdb')
conn.execute("CREATE TABLE nodes AS SELECT * FROM read_parquet('nodes.parquet')")
```
