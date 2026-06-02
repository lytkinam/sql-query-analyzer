# Форматы архивирования и публикации

Файлы для упаковки, передачи и публикации полного набора артефактов анализа.

---

## ZIP — `analysis_bundle.zip`

**Назначение:** самый простой и универсальный способ передачи всего набора артефактов.

**Структура архива:**
```
analysis_bundle.zip
├── README.md
├── version.json
├── normalized/
├── tables/
├── texts/
├── lineage/
├── graph/
├── reports/
└── meta/
```

**Генерация:**
```bash
zip -r analysis_bundle.zip output/ -x "*.pyc" -x "__pycache__/*"
```

---

## TAR.GZ — `analysis_bundle.tar.gz`

**Назначение:** стандартный архив для Linux, CI/CD, Docker-контейнеров.

**Генерация:**
```bash
tar -czf analysis_bundle.tar.gz output/
```

---

## 7Z — `analysis_bundle.7z`

**Назначение:** максимальное сжатие. Особенно эффективно для JSON и CSV с повторяющимися структурами.

**Генерация:**
```bash
7z a -t7z analysis_bundle.7z output/
```

---

## Data Package — `datapackage.json` + файлы

**Назначение:** формализованная поставка набора данных по стандарту [Frictionless Data](https://frictionlessdata.io/). Описывает ресурсы, схемы и метаданные пакета.

**Структура `datapackage.json`:**
```json
{
  "name": "sql-query-analysis-258-npo",
  "title": "Анализ запроса НПО (258)",
  "version": "1.0.0",
  "created": "2026-06-02",
  "resources": [
    {
      "name": "nodes",
      "path": "tables/nodes.csv",
      "mediatype": "text/csv",
      "schema": {
        "fields": [
          {"name": "id", "type": "integer"},
          {"name": "name", "type": "string"},
          {"name": "type", "type": "string"}
        ]
      }
    },
    {
      "name": "field_lineage",
      "path": "lineage/field_lineage.json",
      "mediatype": "application/json"
    }
  ]
}
```

---

## Release folder — `release/`

**Назначение:** стандартизированная структура для публикации версии набора.

**Структура:**
```
release/
├── v1.0.0/
│   ├── README.md
│   ├── CHANGELOG.md
│   ├── version.json
│   ├── checksums.txt
│   ├── analysis_bundle.zip
│   └── datapackage.json
```
