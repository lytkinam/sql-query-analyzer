#!/usr/bin/env python3
"""
analyze_1c_query.py
===================
Скрипт анализа 1C/SQL-запроса через sql-query-analyzer.

Использование:
    python analyze_1c_query.py <путь_к_запросу.sql> [опции]

Опции:
    -o, --output <файл>     Путь для сохранения JSON (по умолчанию: result.json)
    -d, --detailed          Детальный режим (разбивка UNION на части)
    -s, --summary           Вывести краткую сводку в консоль
    -h, --help              Показать эту справку

Примеры:
    python analyze_1c_query.py /path/to/258_npo_query.md -o 258_result.json -s
    python analyze_1c_query.py query.sql --detailed --summary
"""

import argparse
import json
import os
import sys

# Добавляем директорию скрипта в путь для импорта sql_query_analyzer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sql_query_analyzer import analyze_sql_query


def print_summary(data: dict):
    """Выводит краткую сводку по результату анализа."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    drops = data.get("drop_queries", [])

    vts = [n for n in nodes if n.get("type") == "temp_query"]
    subs = [n for n in nodes if n.get("type") == "sub_query"]
    stubs = [n for n in nodes if n.get("is_stub")]
    unions = [n for n in nodes if n.get("is_union_part")]

    print("=" * 50)
    print("СВОДКА ПО АНАЛИЗУ ЗАПРОСА")
    print("=" * 50)
    print(f"Всего узлов:           {len(nodes)}")
    print(f"Временных таблиц:      {len(vts)}")
    print(f"Подзапросов:           {len(subs)}")
    print(f"Рёбер зависимостей:    {len(edges)}")
    print(f"Stub-таблиц:           {len(stubs)}")
    print(f"Union-частей:          {len(unions)}")
    print(f"DROP-запросов:         {len(drops)}")
    print("-" * 50)

    if stubs:
        print("Stub-таблицы (не используются):")
        for s in stubs:
            print(f"  - {s['name']}")

    if drops:
        print("Уничтожаемые таблицы:")
        for d in drops:
            print(f"  - {d}")

    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Анализ 1C/SQL-запроса: структура, подзапросы, зависимости ВТ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python analyze_1c_query.py 258_npo_query.md -o result.json -s
  python analyze_1c_query.py query.sql --detailed --summary
        """,
    )
    parser.add_argument("query_file", help="Путь к файлу с SQL/1C-запросом")
    parser.add_argument(
        "-o", "--output", default="result.json", help="Путь для сохранения JSON (default: result.json)"
    )
    parser.add_argument(
        "-d", "--detailed", action="store_true", help="Детальный режим (разбивка UNION)"
    )
    parser.add_argument(
        "-s", "--summary", action="store_true", help="Вывести сводку в консоль"
    )

    args = parser.parse_args()

    if not os.path.exists(args.query_file):
        print(f"[ERROR] Файл не найден: {args.query_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.query_file, "r", encoding="utf-8") as f:
        sql_text = f.read()

    print(f"[INFO] Чтение запроса: {args.query_file} ({len(sql_text)} символов)")
    print(f"[INFO] Режим detailed={args.detailed}")

    try:
        result_json = analyze_sql_query(sql_text, detailed=args.detailed)
    except Exception as e:
        print(f"[ERROR] Ошибка анализа: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result_json)

    print(f"[OK] Результат сохранён: {args.output}")

    if args.summary:
        data = json.loads(result_json)
        print_summary(data)


if __name__ == "__main__":
    main()
