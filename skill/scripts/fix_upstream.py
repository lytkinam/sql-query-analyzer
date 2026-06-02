#!/usr/bin/env python3
"""
fix_upstream.py
===============
Исправление дефектов upstream-файла sql_query_analyzer.py из GitHub.

Проблема: файл в репозитории содержит literal \\n вместо реальных переводов строк,
экранированные кавычки и удвоенные backslash внутри raw strings (артефакт загрузки).

Использование:
    python fix_upstream.py [путь_к_sql_query_analyzer.py]

По умолчанию обрабатывает файл в текущей директории.
Создаёт бэкап с расширением .bak.
"""

import argparse
import os
import shutil
import sys


def fix_file(path: str) -> bool:
    """Исправляет файл и возвращает True в случае успеха."""
    if not os.path.exists(path):
        print(f"[ERROR] Файл не найден: {path}", file=sys.stderr)
        return False

    with open(path, "rb") as f:
        content = f.read()

    # Бэкап
    backup_path = path + ".bak"
    shutil.copy2(path, backup_path)
    print(f"[INFO] Бэкап создан: {backup_path}")

    # Шаг 1: убрать удвоение backslash (JSON-like escaping)
    content = content.replace(b"\\\\", b"\\")
    # Шаг 2: literal \n → newline
    content = content.replace(b"\\n", b"\n")
    # Шаг 3: literal \" → quote
    content = content.replace(b'\\"', b'"')

    with open(path, "wb") as f:
        f.write(content)

    # Проверка синтаксиса
    try:
        import py_compile

        py_compile.compile(path, doraise=True)
        print(f"[OK] Файл исправлен и проверен: {path}")
        return True
    except py_compile.PyCompileError as e:
        print(f"[WARN] Синтаксическая ошибка после исправления: {e}", file=sys.stderr)
        print("[WARN] Возможно, требуется ручная доработка.", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Исправление дефектов upstream-файла sql_query_analyzer.py"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="sql_query_analyzer.py",
        help="Путь к sql_query_analyzer.py (default: ./sql_query_analyzer.py)",
    )
    args = parser.parse_args()

    success = fix_file(args.file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
