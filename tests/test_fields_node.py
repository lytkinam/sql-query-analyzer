"""
tests/test_fields_node.py
=========================
Тесты итерации 2.1: парсер полей нод (fields_node + table_alias_map).

Запуск:
    pytest tests/test_fields_node.py -v
"""

import pytest
from sql_query_analyzer import analyze_sql_query
from exporters.fields_node import (
    build_fields_and_alias_map,
    parse_table_alias_map,
    _extract_select_block,
    _split_select_list,
    _classify_expr,
    _extract_field_refs,
    _parse_alias_from_expr,
)


# ──────────────────────────────────────────────
# Фикстуры
# ──────────────────────────────────────────────

SIMPLE_SQL = """
ВЫБРАТЬ
    д.Ссылка КАК Договор,
    д.Контрагент КАК Контрагент,
    к.Наименование КАК КонтрагентНаим
ПОМЕСТИТЬ ВТ_Договоры
ИЗ
    Справочник.Договоры КАК д
        ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК к
        ПО д.Контрагент = к.Ссылка
"""

CASE_SQL = """
ВЫБРАТЬ
    о.ПенсионныйСчет КАК ПС,
    ВЫБОР
        КОГДА о.Остаток > 0 ТОГДА о.Остаток
        ИНАЧЕ 0
    КОНЕЦ КАК ОстатокПолож,
    ДОБАВИТЬКДАТЕ(о.ДатаНачала, МЕСЯЦ, 12) КАК ДатаПлюс12
ПОМЕСТИТЬ ВТ_Остатки
ИЗ
    РегистрНакопления.Остатки КАК о
"""

PACKED_SQL = SIMPLE_SQL + ";" + CASE_SQL


@pytest.fixture
def simple_result():
    return build_fields_and_alias_map(
        analyze_sql_query(SIMPLE_SQL, detailed=False)["nodes"]
        if isinstance(analyze_sql_query(SIMPLE_SQL, detailed=False), dict)
        else __import__('json').loads(analyze_sql_query(SIMPLE_SQL, detailed=False))["nodes"]
    )


def _parse(sql: str, detailed: bool = False) -> dict:
    import json
    raw = analyze_sql_query(sql, detailed=detailed)
    nodes = raw["nodes"] if isinstance(raw, dict) else json.loads(raw)["nodes"]
    return build_fields_and_alias_map(nodes)


# ──────────────────────────────────────────────
# 1. _extract_select_block
# ──────────────────────────────────────────────

class TestExtractSelectBlock:
    def test_simple_returns_fields(self):
        block = _extract_select_block(SIMPLE_SQL)
        assert block is not None
        assert "д.Ссылка" in block

    def test_no_select_returns_none(self):
        assert _extract_select_block("ИЗ Справочник.Д КАК д") is None

    def test_stops_before_from(self):
        block = _extract_select_block("ВЫБРАТЬ а.Поле ИЗ Таблица КАК а")
        assert block is not None
        assert "ИЗ" not in block.upper()
        assert "Таблица" not in block

    def test_case_expression_in_select(self):
        block = _extract_select_block(CASE_SQL)
        assert block is not None
        assert "ВЫБОР" in block.upper()


# ──────────────────────────────────────────────
# 2. _split_select_list
# ──────────────────────────────────────────────

class TestSplitSelectList:
    def test_three_simple_fields(self):
        items = _split_select_list("а.Х, б.У, в.З")
        assert len(items) == 3

    def test_case_not_split_by_comma(self):
        expr = "ВЫБОР КОГДА а.Х > 0 ТОГДА а.Х ИНАЧЕ 0 КОНЕЦ КАК Поле"
        items = _split_select_list(expr)
        assert len(items) == 1

    def test_func_with_two_args(self):
        expr = "ДОБАВИТЬКДАТЕ(а.Д, МЕСЯЦ, 12) КАК Дата, а.Х"
        items = _split_select_list(expr)
        assert len(items) == 2

    def test_star(self):
        items = _split_select_list("*")
        assert items == ["*"]


# ──────────────────────────────────────────────
# 3. _parse_alias_from_expr
# ──────────────────────────────────────────────

class TestParseAliasFromExpr:
    @pytest.mark.parametrize("expr, exp_expr, exp_alias", [
        ("д.Ссылка КАК Договор",       "д.Ссылка",            "Договор"),
        ("д.Ссылка AS Contract",        "д.Ссылка",            "Contract"),
        ("д.Контрагент.Наим",           "д.Контрагент.Наим",   "Наим"),
        ("СУММА(х.Сумма) КАК Итого",   "СУММА(х.Сумма)",      "Итого"),
        ("*",                            "*",                   "*"),
    ])
    def test_alias_extraction(self, expr, exp_expr, exp_alias):
        got_expr, got_alias = _parse_alias_from_expr(expr)
        assert got_expr == exp_expr
        assert got_alias == exp_alias


# ──────────────────────────────────────────────
# 4. _classify_expr
# ──────────────────────────────────────────────

class TestClassifyExpr:
    @pytest.mark.parametrize("expr, expected", [
        ("д.Ссылка",                            "field_ref"),
        ("ВЫБОР КОГДА а > 0 ТОГДА 1 КОНЕЦ",    "case_when"),
        ("ДОБАВИТЬКДАТЕ(а.Д, МЕСЯЦ, 12)",       "func_call"),
        ("СУММА(х.Сумма)",                      "aggregate"),
        ("а.Х * б.У",                           "arithmetic"),
        ('"текст"',                             "literal"),
        ("NULL",                                "literal"),
        ("&Параметр",                           "literal"),
        ("*",                                  "star"),
    ])
    def test_types(self, expr, expected):
        assert _classify_expr(expr) == expected


# ──────────────────────────────────────────────
# 5. parse_table_alias_map
# ──────────────────────────────────────────────

class TestParseTableAliasMap:
    def test_simple_join(self):
        result = parse_table_alias_map(SIMPLE_SQL, {"ВТ_ДОГОВОРЫ"})
        aliases = {r["alias"].upper() for r in result}
        assert "Д" in aliases
        assert "К" in aliases

    def test_primary_table_resolved(self):
        result = parse_table_alias_map(SIMPLE_SQL, set())
        by_alias = {r["alias"].upper(): r for r in result}
        assert by_alias["Д"]["primary_table"] == "Справочник.Договоры"
        assert by_alias["К"]["primary_table"] == "Справочник.Контрагенты"

    def test_is_virtual_flag(self):
        sql = "ВЫБРАТЬ а.Х ИЗ ВТ_Тест КАК а"
        result = parse_table_alias_map(sql, {"ВТ_ТЕСТ"})
        assert result[0]["is_virtual"] is True

    def test_is_not_virtual_physical_table(self):
        result = parse_table_alias_map(SIMPLE_SQL, set())
        for r in result:
            assert r["is_virtual"] is False

    def test_no_duplicate_aliases(self):
        result = parse_table_alias_map(SIMPLE_SQL, set())
        aliases = [r["alias"].upper() for r in result]
        assert len(aliases) == len(set(aliases))


# ──────────────────────────────────────────────
# 6. _extract_field_refs
# ──────────────────────────────────────────────

class TestExtractFieldRefs:
    def test_simple_ref(self):
        alias_map = [{"alias": "д", "primary_table": "Справочник.Договоры", "is_virtual": False}]
        refs = _extract_field_refs("д.Ссылка", alias_map)
        assert len(refs) == 1
        assert refs[0]["alias_table"] == "д"
        assert refs[0]["field"] == "Ссылка"
        assert refs[0]["primary_table"] == "Справочник.Договоры"

    def test_no_duplicate_refs(self):
        alias_map = [{"alias": "о", "primary_table": "Рег.Ост", "is_virtual": False}]
        refs = _extract_field_refs("о.Х + о.Х", alias_map)
        fields = [r["field"] for r in refs]
        assert fields.count("Х") == 1

    def test_unknown_alias_fallback(self):
        refs = _extract_field_refs("неизв.Поле", [])
        assert refs[0]["primary_table"] == "неизв"

    def test_value_keyword_skipped(self):
        expr = 'ЗНАЧЕНИЕ(Перечисление.Виды.Тип)'
        refs = _extract_field_refs(expr, [])
        # ЗНАЧЕНИЕ скрыто в __STRx__, dot внутри не должен парситься
        assert refs == []

    def test_multiple_tables(self):
        alias_map = [
            {"alias": "а", "primary_table": "Т1", "is_virtual": True},
            {"alias": "б", "primary_table": "Т2", "is_virtual": False},
        ]
        refs = _extract_field_refs("а.Х + б.У", alias_map)
        tables = {r["alias_table"] for r in refs}
        assert tables == {"а", "б"}


# ──────────────────────────────────────────────
# 7. build_fields_and_alias_map — интеграционные
# ──────────────────────────────────────────────

class TestBuildIntegration:
    def test_keys_present(self):
        result = _parse(SIMPLE_SQL)
        assert "fields_node" in result
        assert "table_alias_map" in result

    def test_node_ids_are_strings(self):
        result = _parse(SIMPLE_SQL)
        for k in result["fields_node"]:
            assert isinstance(k, str)

    def test_simple_fields_count(self):
        result = _parse(SIMPLE_SQL)
        # Главная нода ВТ_Договоры: 3 SELECT-поля + 1 JOIN-таблица + 1 JOIN-ON
        fields_by_name = {
            nid: records
            for nid, records in result["fields_node"].items()
            if any(r["alias"] == "Договор" for r in records)
        }
        assert len(fields_by_name) >= 1
        records = next(iter(fields_by_name.values()))
        assert len(records) == 5  # 3 SELECT + 1 join_table + 1 join_on_condition

    def test_field_record_structure(self):
        result = _parse(SIMPLE_SQL)
        for nid, records in result["fields_node"].items():
            for rec in records:
                assert "alias" in rec
                assert "expression_raw" in rec
                assert "expr_type" in rec
                assert "field_refs" in rec
                assert rec["expr_type"] in (
                    "field_ref", "case_when", "func_call",
                    "aggregate", "arithmetic", "literal", "star",
                    "where_condition", "join_on_condition", "join_table",
                )

    def test_alias_map_structure(self):
        result = _parse(SIMPLE_SQL)
        for nid, entries in result["table_alias_map"].items():
            for e in entries:
                assert "alias" in e
                assert "primary_table" in e
                assert isinstance(e["is_virtual"], bool)

    def test_case_field_classified(self):
        result = _parse(CASE_SQL)
        case_fields = [
            rec
            for records in result["fields_node"].values()
            for rec in records
            if rec["alias"] == "ОстатокПолож"
        ]
        assert case_fields, "Поле ОстатокПолож не найдено"
        assert case_fields[0]["expr_type"] == "case_when"

    def test_func_call_classified(self):
        result = _parse(CASE_SQL)
        func_fields = [
            rec
            for records in result["fields_node"].values()
            for rec in records
            if rec["alias"] == "ДатаПлюс12"
        ]
        assert func_fields, "Поле ДатаПлюс12 не найдено"
        assert func_fields[0]["expr_type"] == "func_call"

    def test_func_field_refs_contain_source(self):
        result = _parse(CASE_SQL)
        func_fields = [
            rec
            for records in result["fields_node"].values()
            for rec in records
            if rec["alias"] == "ДатаПлюс12"
        ]
        refs = func_fields[0]["field_refs"]
        tables = {r["alias_table"] for r in refs}
        assert "о" in tables

    def test_virtual_table_flagged(self):
        sql = """
            ВЫБРАТЬ а.Х
            ПОМЕСТИТЬ ВТ_Итог
            ИЗ ВТ_Источник КАК а
            ;
            ВЫБРАТЬ б.Х ИЗ ВТ_Итог КАК б
        """
        result = _parse(sql)
        for nid, entries in result["table_alias_map"].items():
            for e in entries:
                if e["primary_table"].upper() == "ВТ_ИТОГ":
                    assert e["is_virtual"] is True

    def test_packed_query_all_nodes_have_fields(self):
        result = _parse(PACKED_SQL)
        for nid, records in result["fields_node"].items():
            # Каждая запись — валидный список (может быть пустым для union-part)
            assert isinstance(records, list)


UNION_SQL = """
ВЫБРАТЬ
    а.Х КАК Поле1,
    а.У КАК Поле2
ПОМЕСТИТЬ ВТ_Результат
ИЗ
    Таблица1 КАК а

ОБЪЕДИНИТЬ ВСЕ

ВЫБРАТЬ
    б.Х,
    ВЫБОР КОГДА б.У > 0 ТОГДА б.У ИНАЧЕ 0 КОНЕЦ
ИЗ
    Таблица2 КАК б
"""


WHERE_SQL = """
ВЫБРАТЬ
    д.Ссылка КАК Договор,
    к.Наименование КАК КонтрагентНаим
ПОМЕСТИТЬ ВТ_Договоры
ИЗ
    Справочник.Договоры КАК д
        ВНУТРЕННЕЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК к
        ПО д.Контрагент = к.Ссылка
ГДЕ
    д.Дата > &ДатаНачала
    И к.ПометкаУдаления = ЛОЖЬ
"""


class TestWhereAndJoinFields:
    def test_where_pseudo_field_exists(self):
        result = _parse(WHERE_SQL)
        records = next(iter(result["fields_node"].values()))
        where_recs = [r for r in records if r["alias"] == "ГДЕ_УСЛОВИЕ"]
        assert len(where_recs) == 1
        assert where_recs[0]["expr_type"] == "where_condition"

    def test_where_field_refs(self):
        result = _parse(WHERE_SQL)
        records = next(iter(result["fields_node"].values()))
        where_rec = next(r for r in records if r["alias"] == "ГДЕ_УСЛОВИЕ")
        tables = {ref["alias_table"] for ref in where_rec["field_refs"]}
        assert "д" in tables
        assert "к" in tables

    def test_join_table_pseudo_field(self):
        result = _parse(WHERE_SQL)
        records = next(iter(result["fields_node"].values()))
        join_recs = [r for r in records if r["expr_type"] == "join_table"]
        assert len(join_recs) == 1
        assert join_recs[0]["alias"] == "ВНУТРЕННЕЕ_СОЕДИНЕНИЕ_к"
        assert join_recs[0]["expression_raw"] == "Справочник.Контрагенты"

    def test_join_on_pseudo_field(self):
        result = _parse(WHERE_SQL)
        records = next(iter(result["fields_node"].values()))
        on_recs = [r for r in records if r["expr_type"] == "join_on_condition"]
        assert len(on_recs) == 1
        assert on_recs[0]["alias"] == "ВНУТРЕННЕЕ_СОЕДИНЕНИЕ_к_УСЛОВИЕ"
        assert on_recs[0]["expression_raw"] == "ПО д.Контрагент = к.Ссылка"

    def test_join_on_field_refs(self):
        result = _parse(WHERE_SQL)
        records = next(iter(result["fields_node"].values()))
        on_rec = next(r for r in records if r["expr_type"] == "join_on_condition")
        tables = {ref["alias_table"] for ref in on_rec["field_refs"]}
        assert "д" in tables
        assert "к" in tables


class TestUnion:
    def test_union_field_refs_merged(self):
        """field_refs из всех частей UNION объединяются, alias'ы из первой."""
        result = _parse(UNION_SQL)
        vt_records = None
        for nid, records in result["fields_node"].items():
            if any(r["alias"] == "Поле2" for r in records):
                vt_records = records
                break
        assert vt_records, "Нода с Поле2 не найдена"

        rec = next(r for r in vt_records if r["alias"] == "Поле2")
        # expr_type из первой части (field_ref)
        assert rec["expr_type"] == "field_ref"
        # field_refs объединены из обеих частей
        tables = {ref["alias_table"] for ref in rec["field_refs"]}
        assert "а" in tables, "Первая часть UNION потерялась"
        assert "б" in tables, "Вторая часть UNION не подтянулась"

    def test_union_alias_from_first_part(self):
        result = _parse(UNION_SQL)
        vt_records = None
        for nid, records in result["fields_node"].items():
            if any(r["alias"] == "Поле1" for r in records):
                vt_records = records
                break
        assert vt_records
        rec = next(r for r in vt_records if r["alias"] == "Поле1")
        assert rec["expr_type"] == "field_ref"
        tables = {ref["alias_table"] for ref in rec["field_refs"]}
        assert "а" in tables
        assert "б" in tables


class TestGenerateFieldsNode:
    def test_files_created(self, tmp_path):
        from exporters.fields_node import generate_fields_node
        result = _parse(SIMPLE_SQL)
        model = {"nodes": []}
        # reconstruct minimal model from result
        # we need a model with nodes that have id and text
        import json
        from sql_query_analyzer import analyze_sql_query
        raw = analyze_sql_query(SIMPLE_SQL, detailed=False)
        nodes = raw["nodes"] if isinstance(raw, dict) else json.loads(raw)["nodes"]
        model = {"nodes": nodes}
        generate_fields_node(model, str(tmp_path))

        assert (tmp_path / "fields_node" / "fields_node.json").exists()
        assert (tmp_path / "fields_node" / "table_alias_map.json").exists()
        assert (tmp_path / "fields_node" / "fields_node.csv").exists()
        assert (tmp_path / "fields_node" / "table_alias_map.csv").exists()

    def test_csv_content(self, tmp_path):
        from exporters.fields_node import generate_fields_node
        import json
        from sql_query_analyzer import analyze_sql_query
        raw = analyze_sql_query(SIMPLE_SQL, detailed=False)
        nodes = raw["nodes"] if isinstance(raw, dict) else json.loads(raw)["nodes"]
        model = {"nodes": nodes}
        generate_fields_node(model, str(tmp_path))

        import csv
        with open(tmp_path / "fields_node" / "fields_node.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) > 0
        assert "node_id" in rows[0]
        assert "alias" in rows[0]
        assert "expr_type" in rows[0]
