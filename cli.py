#!/usr/bin/env python3
"""
cli.py — командная строка для sql_query_analyzer.

Использование:
    python cli.py <файл.sql>
    python cli.py <файл.sql> --detailed
    python cli.py <файл.sql> --detailed --output result.json
    echo "ВЫБРАТЬ 1" | python cli.py -
"""

import sys
import argparse
from sql_query_analyzer import analyze_sql_query


def main():
    parser = argparse.ArgumentParser(
        description="Анализатор SQL/1C-запросов — выводит граф подзапросов в JSON"
    )
    parser.add_argument(
        "input",
        help="Путь к файлу с SQL-запросом, или '-' для чтения из stdin"
    )
    parser.add_argument(
        "--detailed", "-d",
        action="store_true",
        default=False,
        help="Детальный режим: разбивает UNION/ОБЪЕДИНИТЬ на части"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Путь к выходному JSON-файлу (по умолчанию — stdout)"
    )
    args = parser.parse_args()

    if args.input == "-":
        sql_text = sys.stdin.read()
    else:
        with open(args.input, encoding="utf-8") as f:
            sql_text = f.read()

    result = analyze_sql_query(sql_text, detailed=args.detailed)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Сохранено в {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
