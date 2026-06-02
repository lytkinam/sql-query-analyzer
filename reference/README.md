# Reference: original 1C query-scheme script

This directory contains the original JavaScript/HTML script extracted from
1C:Enterprise 8 (`СхемаЗапросаSQL_e5c678.html`) that performs the initial
SQL-query parsing and graph layout.

It was used as the primary reference when building the Python
`sql_query_analyzer.py` reimplementation.

## File

- **`СхемаЗапросаSQL_e5c678.html`** — embedded HTML/JS from the 1C managed
  form.  Contains the tokenizer, sub-query replacer, UNION splitter,
  `getOwnInTables()` extractor, edge builder and canvas renderer.
