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

## Running the original JS parser

The HTML file is meant for a browser (1C managed form with Internet Explorer
internals).  To execute the parser logic **outside 1C** you need Node.js and a
couple of DOM stubs.

### Quick start

```bash
cd reference/

# 1. Fix multiline-string syntax (the original uses CRLF inside "…" which is
#    invalid in standard JS).  A pre-fixed copy is already provided:
node run_fixed_js.js
```

### What the runner does

`run_fixed_js.js`:
1. Sets up minimal DOM stubs (`document.getElementById`, canvas 2-D context).
2. Loads `original_parser_fixed.js` (the extracted JS with CRLF issues fixed).
3. Calls `drawGraph(sqlText, detailed)` — the main entry point of the original
   parser.
4. Prints the list of nodes, edges and drop-queries exactly as the 1C version
   would produce them.

### Manual fix from the original HTML

If you need to regenerate `original_parser_fixed.js` from the raw HTML:

```bash
python3 << 'PYEOF'
with open('СхемаЗапросаSQL_e5c678.html', 'rb') as f:
    data = f.read()

# The original contains three multi-line string literals inside "…"
# which are split by CRLF.  Standard JS engines reject that.
fixes = [
    (b'superUnionTextHTML += "\\r\\n<div id',
     b'superUnionTextHTML += "" +\\r\\n"<div id'),
    (b'superUnionTextHTML += "\\r\\n<div class',
     b'superUnionTextHTML += "" +\\r\\n"<div class'),
    (b'return "\\r\\n<div id',
     b'return "" +\\r\\n"<div id'),
]
for old, new in fixes:
    data = data.replace(old, new)

import re
js = re.search(b'<script type="text/javascript">(.*?)</script>',
               data, re.DOTALL).group(1)
with open('original_parser_fixed.js', 'wb') as f:
    f.write(js)
PYEOF
```

### Entry-point API (original JS)

| Function | Signature | Description |
|---|---|---|
| `drawGraph` | `drawGraph(sql_text, detailed)` | Main parser.  Populates global `nodeArrow`, `edgeArrow`, `dropQueryArrow`. |
| `getOwnInTables` | `getOwnInTables(text)` | Extracts table names from a single query text. |
| `setNodeArrow` | `setNodeArrow()` | Tokenizer / node builder (called by `drawGraph`). |
| `setEdgeArrow` | `setEdgeArrow()` | Dependency edge builder (called by `drawGraph`). |

Globals filled after `drawGraph`:
- `nodeArrow[]` — array of `Node` objects (`id`, `name`, `type`, `text`, `children`, `parent`, `own_in_tables`, `isStub`, `isUnionPart`, …)
- `edgeArrow[]` — array of `Edge` objects (`out_node`, `in_node`)
- `dropQueryArrow[]` — array of table names to drop

### Comparison with Python reimplementation

Use `compare_example.js` (or write your own) to run the same SQL through the
original JS and compare the node/edge counts with `sql_query_analyzer.py`.

Known differences:
- **Empty trailing query** — `sql_text.split(";")` on a string ending with `;`
  creates an empty part.  The original JS turns it into an extra `Результат_N`
  node; the Python version skips empty parts.
- **Edge direction** — both versions build `temp_query → consumer` edges.
  The JS additionally propagates edges from child sub-queries up to their
  parent temp-tables (`setNodeEdgeArrow`).
