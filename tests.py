"""
tests.py — базовые тесты для sql_query_analyzer.
Запуск: python tests.py
"""

import json
from sql_query_analyzer import analyze_sql_query


passed = 0
failed = 0


def check(name, condition, description):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print(f"[FAIL] {name}: {description}")


# Test 1: простой пакетный запрос
SQL1 = """
ВЫБРАТЬ Т.Ссылка ПОМЕСТИТЬ ВТ_1 ИЗ Справочник.Т КАК Т;
ВЫБРАТЬ ВТ_1.Ссылка ИЗ ВТ_1 КАК ВТ_1
"""
d1 = json.loads(analyze_sql_query(SQL1))
check("T1", len(d1["nodes"]) == 2, "2 узла")
check("T1", len(d1["edges"]) == 1, "1 ребро")
check("T1", d1["edges"][0]["from_name"] == "ВТ_1", "ребро из ВТ_1")
check("T1", d1["edges"][0]["to_name"] == "Результат_1", "ребро в Результат_1")

# Test 2: УНИЧТОЖИТЬ
SQL2 = "ВЫБРАТЬ 1; УНИЧТОЖИТЬ ВТ_Х"
d2 = json.loads(analyze_sql_query(SQL2))
check("T2", "ВТ_Х" in d2["drop_queries"], "ВТ_Х в drop_queries")
check("T2", len(d2["nodes"]) == 1, "1 узел")

# Test 3: вложенный подзапрос
SQL3 = """
ВЫБРАТЬ Т.Сумма ИЗ
    (ВЫБРАТЬ Продажи.Сумма КАК Сумма ИЗ Документ.Продажи КАК Продажи) КАК Т
"""
d3 = json.loads(analyze_sql_query(SQL3))
check("T3", any(n["name"] == "Т" for n in d3["nodes"]), "узел Т существует")
check("T3", any(n["type"] == "sub_query" for n in d3["nodes"]), "есть sub_query")

# Test 4: UNION detailed
SQL4 = """
ВЫБРАТЬ А.Х ИЗ Таблица1 КАК А
ОБЪЕДИНИТЬ ВСЕ
ВЫБРАТЬ Б.Х ИЗ Таблица2 КАК Б
"""
d4 = json.loads(analyze_sql_query(SQL4, detailed=True))
check("T4", any(n["is_union_part"] for n in d4["nodes"]), "есть is_union_part=True")
check("T4", sum(1 for n in d4["nodes"] if n["is_union_part"]) == 2, "2 части UNION")

# Test 5: is_stub
SQL5 = "ВЫБРАТЬ 1 ПОМЕСТИТЬ ВТ_Никто ИЗ Справочник.Т КАК Т"
d5 = json.loads(analyze_sql_query(SQL5))
check("T5", any(n["is_stub"] for n in d5["nodes"]), "is_stub для невостребованной ВТ")

print(f"\nИтого: {passed} passed, {failed} failed")
