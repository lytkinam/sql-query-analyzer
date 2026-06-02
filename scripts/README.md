# scripts/ — Инструменты для работы с артефактами sql-query-analyzer

## Архитектура

```
scripts/
├── lib/
│   ├── __init__.py
│   ├── output_reader.py      # Чтение CSV/JSON из output-директории
│   └── field_resolver.py     # Глубокое разрешение поля (lineage + "проваливание")
├── extract_field.py          # CLI: извлечь полную карту поля
└── README.md                 # Этот файл
```

**Принцип:** библиотеки (`lib/`) предназначены для импорта ИИ-моделями. CLI-скрипты — тонкие обёртки.

## extract_field.py

Глубокое извлечение информации о поле. Решает проблему "lineage обрывается на границе ВТ".

```bash
# Человекочитаемый вывод
python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а

# JSON для дальнейшей обработки
python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --json

# Только SQL-тексты узлов
python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --sql-only
```

Вывод включает:
1. **Lineage** — цепочка из `field_lineage.json`
2. **Defining nodes** — узлы, где поле реально определяется (с "проваливанием" через UNION)
3. **SQL snippets** — строки SQL с выделением строк, содержащих поле
4. **Upstream fields** — распакованные ссылки вида `ВТ_Х.Поле`

### Пример: ВидОбязательств_гр1а

```
Узел 297 (ВТ_258НПО)        → прямой перенос ВТ_РезультатПредв.ВидОбязательств_гр1а
  └─ Узел 293 (ВТ_РезультатПредв)  → UNION из 3 частей
       ├─ Часть_1 : ВТ_НеТранзитныеВидыНачалоКонец.ВидОбязательств
       ├─ Часть_2 : ВЫБОР ... КОНЕЦ  (вычисляемое)
       └─ Часть_3 : ВТ_ТранзитныеВиды.ВидОбязательств
```

## Использование из Python (для ИИ-моделей)

```python
from scripts.lib.output_reader import OutputReader
from scripts.lib.field_resolver import FieldResolver

reader = OutputReader("examples/output_258")
resolver = FieldResolver(reader)

result = resolver.resolve("ВидОбязательств_гр1а")
print(result["defining_nodes"])
print(result["sql_snippets"])
```

## Расширение

Добавляйте новые модули в `lib/` и CLI-скрипты в корень `scripts/`.  
Библиотеки должны оставаться чистыми (без `print`), возвращая `dict`/`list`.
