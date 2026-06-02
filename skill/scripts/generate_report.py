#!/usr/bin/env python3
"""
generate_report.py
==================
Генерация Markdown-отчёта из JSON-результата sql-query-analyzer.

Использование:
    python generate_report.py <result.json> [опции]

Опции:
    -o, --output <файл>     Путь для сохранения отчёта (по умолчанию: report.md)
    -t, --title <заголовок>  Заголовок отчёта
    -h, --help              Показать эту справку

Примеры:
    python generate_report.py 258_result.json -o 258_structure.md -t "Отчёт 258 НПО"
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict


def generate_report(data: dict, title: str) -> str:
    """Генерирует Markdown-отчёт из данных анализа."""

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    drops = data.get("drop_queries", [])

    vts = [n for n in nodes if n.get("type") == "temp_query"]
    subs = [n for n in nodes if n.get("type") == "sub_query"]
    stubs = [n for n in nodes if n.get("is_stub")]
    unions = [n for n in nodes if n.get("is_union_part")]

    # Build trees
    children = defaultdict(list)
    parents = defaultdict(list)
    for e in edges:
        children[e["from_name"]].append(e["to_name"])
        parents[e["to_name"]].append(e["from_name"])

    roots = [n for n in nodes if not parents[n["name"]]]

    # Metadata extraction
    meta_counter = Counter()
    for n in nodes:
        for t in n.get("own_in_tables", []):
            parts = t.split(".")
            if len(parts) >= 2:
                meta_counter[parts[0]] += 1

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Дата генерации:** {__import__('datetime').datetime.now().isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Общая статистика")
    lines.append("")
    lines.append("| Показатель | Значение |")
    lines.append("|------------|----------|")
    lines.append(f"| Всего узлов | {len(nodes)} |")
    lines.append(f"| Временных таблиц (ВТ) | {len(vts)} |")
    lines.append(f"| Подзапросов / Union-частей | {len(subs)} |")
    lines.append(f"| Рёбер зависимостей | {len(edges)} |")
    lines.append(f"| Stub-таблиц | {len(stubs)} |")
    lines.append(f"| Union-частей | {len(unions)} |")
    lines.append(f"| DROP-запросов | {len(drops)} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 2. Корневые узлы")
    lines.append("")
    for r in roots:
        lines.append(f"- **{r['name']}** (`{r['type']}`)")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 3. Stub-таблицы")
    lines.append("")
    if stubs:
        for s in stubs:
            lines.append(f"- `{s['name']}`")
    else:
        lines.append("Нет stub-таблиц.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 4. Временные таблицы")
    lines.append("")
    for vt in sorted(vts, key=lambda x: x["id"]):
        cons = children.get(vt["name"], [])
        deps = vt.get("own_in_tables", [])
        stub_mark = " ⚠️ stub" if vt.get("is_stub") else ""
        lines.append(f"### {vt['name']}{stub_mark}")
        lines.append(f"- **ID:** {vt['id']}")
        if deps:
            lines.append(f"- **Читает:** {', '.join(deps[:10])}" + (f" ... (+{len(deps)-10})" if len(deps) > 10 else ""))
        if cons:
            lines.append(f"- **Потребители:** {', '.join(cons[:10])}" + (f" ... (+{len(cons)-10})" if len(cons) > 10 else ""))
        lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 5. Используемые 1С-метаданные (top-30)")
    lines.append("")
    lines.append("| Тип метаданных | Количество ссылок |")
    lines.append("|----------------|-------------------|")
    for m, c in meta_counter.most_common(30):
        lines.append(f"| {m} | {c} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 6. Граф зависимостей (дерево от корней)")
    lines.append("")

    def print_tree(name, depth=0, visited=None):
        if visited is None:
            visited = set()
        if name in visited:
            lines.append("  " * depth + f"- `{name}` *(цикл)*")
            return
        visited.add(name)
        lines.append("  " * depth + f"- `{name}`")
        for child in sorted(children.get(name, [])):
            print_tree(child, depth + 1, visited.copy())

    for r in roots[:10]:
        print_tree(r["name"])
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Отчёт сгенерирован скриптом `generate_report.py` из skill `sql-query-analyzer`.*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Генерация Markdown-отчёта из JSON-результата sql-query-analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python generate_report.py result.json -o report.md -t "Анализ запроса"
        """,
    )
    parser.add_argument("json_file", help="Путь к JSON-файлу с результатом анализа")
    parser.add_argument(
        "-o", "--output", default="report.md", help="Путь для сохранения отчёта (default: report.md)"
    )
    parser.add_argument(
        "-t", "--title", default="Структура запроса", help="Заголовок отчёта"
    )

    args = parser.parse_args()

    if not os.path.exists(args.json_file):
        print(f"[ERROR] Файл не найден: {args.json_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[INFO] Загружен JSON: {args.json_file}")
    print(f"[INFO] Узлов: {len(data.get('nodes', []))}, Рёбер: {len(data.get('edges', []))}")

    report_md = generate_report(data, args.title)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[OK] Отчёт сохранён: {args.output}")


if __name__ == "__main__":
    main()
