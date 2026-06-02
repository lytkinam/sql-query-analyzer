#!/usr/bin/env python3
"""
extract_field.py
================
CLI-скрипт глубокого извлечения информации о поле из артефактов sql-query-analyzer.

Использование:
    python scripts/extract_field.py <output_dir> <field_name> [опции]

Примеры:
    python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а
    python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --json
    python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --sql-only
"""

import argparse
import json
import sys
from pathlib import Path

# Добавляем корень проекта в путь, чтобы импортировать scripts.lib
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.lib.output_reader import OutputReader
from scripts.lib.field_resolver import FieldResolver


def print_human(result: dict):
    print(f"{'=' * 60}")
    print(f"ПОЛЕ: {result['field']}")
    print(f"{'=' * 60}\n")

    lineage = result.get("lineage", {})
    print("--- 1. Lineage (верхний уровень) ---")
    print(f"  final_node_id : {lineage.get('final_node_id')}")
    print(f"  depth         : {lineage.get('depth')}")
    for step in lineage.get("chain", []):
        if step.get("node_id"):
            print(f"    → узел {step['node_id']} ({step.get('node_name')}) : {step.get('expr')}")
        else:
            print(f"    → ВТ-источник: {step.get('source_table')}.{step.get('source_field')}")
    print()

    print("--- 2. Узлы, где поле реально определяется ---")
    for dn in result.get("defining_nodes", []):
        print(f"  [{dn['node_id']:>3}] {dn['node_name']} ({dn['node_type']})")
    print()

    print("--- 3. SQL-фрагменты (строки с полем) ---")
    for snip in result.get("sql_snippets", []):
        if not snip["lines"]:
            continue
        print(f"\n  >> node_{snip['node_id']}.sql  ({len(snip['lines'])} строк)")
        for line in snip["lines"]:
            print(f"     L{line['line_no']:>3}: {line['text']}")
    print()

    upstream = result.get("upstream_fields", [])
    if upstream:
        print("--- 4. Upstream-поля (распакованные ВТ) ---")
        for uf in upstream:
            print(f"    • {uf}")
        print()

    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="Глубокое извлечение информации о поле из артефактов sql-query-analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а
  python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --json > result.json
  python scripts/extract_field.py examples/output_258 ВидОбязательств_гр1а --sql-only
        """,
    )
    parser.add_argument("output_dir", help="Путь к output-директории (например, examples/output_258)")
    parser.add_argument("field_name", help="Имя поля (alias) для анализа")
    parser.add_argument("-j", "--json", action="store_true", help="Вывести результат как JSON")
    parser.add_argument("--sql-only", action="store_true", help="Только SQL-тексты узлов")
    args = parser.parse_args()

    if not Path(args.output_dir).exists():
        print(f"[ERROR] Директория не найдена: {args.output_dir}", file=sys.stderr)
        sys.exit(1)

    reader = OutputReader(args.output_dir)
    resolver = FieldResolver(reader)
    result = resolver.resolve(args.field_name)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.sql_only:
        for snip in result.get("sql_snippets", []):
            if snip.get("sql"):
                print(f"-- ===== node_{snip['node_id']}.sql =====")
                print(snip["sql"])
                print()
    else:
        print_human(result)


if __name__ == "__main__":
    main()
