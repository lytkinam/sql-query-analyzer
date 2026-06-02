# Форматы структуры запроса

Файлы для восстановления каркаса 1С-запроса: дерево узлов, граф зависимостей, карты источников и объединений.

---

## Каталог ВТ — `tempqueries_catalog.csv`

**Назначение:** оглавление всего запроса. Первый файл, который открывают для навигации.

**Структура (колонки):**
`id, name, type, parentid, maxparentid, children_count, ownintables_count, isstub, isunionpart, union_parts`

**Пример:**
```csv
id,name,type,parentid,maxparentid,children_count,ownintables_count,isstub,isunionpart,union_parts
132,ВТ_ПенсионныеСчета,tempquery,,132,1,3,false,false,
293,ВТ_ИтогПоДоговорам,tempquery,,293,3,0,false,false,"294;295;296"
```

---

## Реестр родителей — `edges_parent.csv`

**Назначение:** восстановление дерева вложенности. Основа для построения иерархического представления.

**Структура:**
```csv
parent_id,child_id,parent_name,child_name,depth,relation
132,133,ВТ_ПенсионныеСчета,1,1,parent_child
293,294,ВТ_ИтогПоДоговорам,1,1,union_part
293,295,ВТ_ИтогПоДоговорам,2,1,union_part
```

**Поля:**
| Поле | Описание |
|---|---|
| `parent_id` | ID родительского узла |
| `child_id` | ID дочернего узла |
| `depth` | Уровень вложенности от корня |
| `relation` | `parent_child` или `union_part` |

---

## Реестр ссылок — `edges_refs.csv`

**Назначение:** граф зависимостей между ВТ. Показывает, какая ВТ использует данные из какой другой ВТ.

**Структура:**
```csv
from_id,to_id,fromname,toname,relation
123,132,ВТ_Итог,ВТ_ПенсионныеСчета,ref
123,134,ВТ_Итог,ВТ_ДоговорыНПО,ref
```

**Поля:**
| Поле | Описание |
|---|---|
| `from_id` | Узел, который ссылается |
| `to_id` | Узел, на который ссылаются |
| `fromname` / `toname` | Имена узлов |
| `relation` | Тип связи: `ref` (ссылка) |

---

## Источники по узлам — `sources_map.csv`

**Назначение:** список реальных физических таблиц и регистров, используемых каждым узлом.

**Структура:**
```csv
node_id,node_name,source_name,source_kind,ordinal
132,ВТ_ПенсионныеСчета,РегистрНакопления.ПенсионныеСчета,AccumulationRegister,1
132,ВТ_ПенсионныеСчета,Справочник.Контрагенты,Catalog,2
```

**Поля:**
| Поле | Описание |
|---|---|
| `node_id` | ID узла |
| `source_name` | Полное имя источника |
| `source_kind` | Тип: `AccumulationRegister`, `Catalog`, `Document`, `InformationRegister`, `TempTable` и др. |
| `ordinal` | Порядковый номер в списке |

---

## Карта объединений — `union_parts.csv`

**Назначение:** выделить все ОБЪЕДИНИТЬ / ОБЪЕДИНИТЬ ВСЕ и их составные части.

**Структура:**
```csv
parent_query_id,parent_name,part_id,part_name,part_number,isunionpart
293,ВТ_ИтогПоДоговорам,294,1,1,true
293,ВТ_ИтогПоДоговорам,295,2,2,true
293,ВТ_ИтогПоДоговорам,296,3,3,true
```

---

## Карта заглушек — `stubs.csv`

**Назначение:** отделить технические/пустые узлы (`isstub=true`) от реальных ВТ с логикой.

**Структура:**
```csv
node_id,node_name,type,isstub,reason
0,,tempquery,true,root_stub
71,,tempquery,true,empty_body
```

---

## Дерево в JSON — `query_tree.json`

**Назначение:** иерархическое представление с вложенными объектами. Удобно для UI-навигации и рендеринга дерева.

**Структура:**
```json
{
  "id": 293,
  "name": "ВТ_ИтогПоДоговорам",
  "type": "tempquery",
  "children": [
    {"id": 294, "name": "1", "type": "subquery", "isunionpart": true, "children": []},
    {"id": 295, "name": "2", "type": "subquery", "isunionpart": true, "children": []},
    {"id": 296, "name": "3", "type": "subquery", "isunionpart": true, "children": []}
  ]
}
```

---

## Граф в JSON — `query_graph.json`

**Назначение:** плоское представление графа с узлами и рёбрами. Универсальный формат для любой визуализации.

**Структура:**
```json
{
  "nodes": [
    {"id": 132, "label": "ВТ_ПенсионныеСчета", "type": "tempquery"}
  ],
  "edges": [
    {"from": 123, "to": 132, "label": "ref"}
  ]
}
```
