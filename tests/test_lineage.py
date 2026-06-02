"""
tests/test_lineage.py
=====================
Тесты итерации 4 — exporters/lineage.py.

Структура:
  TestLineageFilesExist   — все 8 файлов сгенерированы и непусты
  TestFields              — fields.csv: колонки, ordinal, is_computed
  TestExpressions         — expressions.csv: типы, заполненность
  TestConditions          — conditions.csv: типы условий
  TestJoins               — joins.csv: типы JOIN
  TestFieldLineage        — field_lineage.json: список, chain, final_node_id
  TestFieldMapping        — field_mapping.csv: колонки, заполненность
  TestDependencyMatrix    — dependency_matrix.csv: pivot, 0/1, диагональ
  TestParseSelectList     — parse_select_list: unit-тесты парсера
  TestKeyFields           — lineage_key_fields.json: структура, branching bool

ЗАМЕЧАНИЕ:
  Тесты используют общую фикстуру conftest.py (small.sql → model → output_dir).
  generate_tables(model, output_dir) вызывается В conftest ДО generate_lineage.

ВОЗМОЖНЫЕ ОШИБКИ при запуске:
  - ImportError: нет exporters.lineage → файл не создан
  - FileNotFoundError tables/fields.csv → generate_lineage не вызван
  - AssertionError «Ожидается list» → field_lineage.json вернул dict
  - AssertionError «final_node_id» → поле пропущено в entry
  - AssertionError «branching должен быть bool» → записан как str "true"
  - AssertionError headers[0] != node_id → неверный первый столбец матрицы
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
import pytest

from exporters.lineage import (
    generate_lineage,
    parse_select_list,
)


# ---------------------------------------------------------------------------
# Фикстура: маленький пример (small.sql)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def lineage_output(small_model):
    """
    Генерирует lineage-файлы для small.sql.
    Зависит от фикстуры small_model из conftest.py,
    которая уже вызвала generate_tables(model, out).

    ВОЗМОЖНАЯ ОШИБКА:
        Если conftest.py не вызывает generate_tables перед generate_lineage,
        ref_index будет пустым и chain'ы не построятся.
    """
    out = small_model["output_dir"]
    model = small_model["model"]
    generate_lineage(model, out)
    return out


# ---------------------------------------------------------------------------
# TestLineageFilesExist
# ---------------------------------------------------------------------------

class TestLineageFilesExist:
    EXPECTED_FILES = [
        "tables/fields.csv",
        "tables/expressions.csv",
        "tables/conditions.csv",
        "tables/joins.csv",
        "lineage/field_lineage.json",
        "lineage/lineage_key_fields.json",
        "lineage/field_mapping.csv",
        "lineage/dependency_matrix.csv",
    ]

    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_file_exists_and_nonempty(self, lineage_output, rel_path):
        path = os.path.join(lineage_output, rel_path)
        assert os.path.exists(path), f"Файл не создан: {rel_path}"
        assert os.path.getsize(path) > 0, f"Файл пустой: {rel_path}"


# ---------------------------------------------------------------------------
# TestFields
# ---------------------------------------------------------------------------

class TestFields:
    REQUIRED_COLS = {
        "node_id", "node_name", "field_ordinal", "field_alias",
        "expression", "source_table", "source_field", "is_computed",
    }

    @pytest.fixture(scope="class")
    def rows(self, lineage_output):
        with open(os.path.join(lineage_output, "tables", "fields.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_columns_present(self, rows):
        assert rows, "fields.csv пуст"
        missing = self.REQUIRED_COLS - set(rows[0].keys())
        assert not missing, f"Отсутствуют колонки: {missing}"

    def test_ordinal_monotone(self, rows):
        """field_ordinal монотонно возрастает (0-based) в рамках каждого узла."""
        from itertools import groupby
        for node_id, grp in groupby(rows, key=lambda r: r["node_id"]):
            ords = [int(r["field_ordinal"]) for r in grp]
            assert ords == list(range(len(ords))), (
                f"node {node_id}: нарушен порядок ordinal: {ords}"
            )

    def test_is_computed_values(self, rows):
        """is_computed должен быть строго 'true' или 'false'."""
        for r in rows:
            assert r["is_computed"] in ("true", "false"), (
                f"node {r['node_id']} поле {r['field_alias']}: "
                f"is_computed='{r['is_computed']}'"
            )


# ---------------------------------------------------------------------------
# TestExpressions
# ---------------------------------------------------------------------------

class TestExpressions:
    VALID_TYPES = {"ISNULL", "CASE", "AGGREGATE", "SUBSTRING", "CAST",
                   "FUNCTION", "ARITHMETIC", "PARAMETER"}

    @pytest.fixture(scope="class")
    def rows(self, lineage_output):
        with open(os.path.join(lineage_output, "tables", "expressions.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_columns_present(self, rows):
        required = {"node_id", "node_name", "expr_type", "expr_text", "output_alias", "line"}
        if rows:
            missing = required - set(rows[0].keys())
            assert not missing, f"Отсутствуют колонки: {missing}"

    def test_expr_type_valid(self, rows):
        for r in rows:
            assert r["expr_type"] in self.VALID_TYPES, (
                f"Неизвестный expr_type='{r['expr_type']}' в узле {r['node_id']}"
            )

    def test_expr_text_nonempty(self, rows):
        for r in rows:
            assert r["expr_text"].strip(), (
                f"Пустой expr_text в узле {r['node_id']} поле {r['output_alias']}"
            )


# ---------------------------------------------------------------------------
# TestConditions
# ---------------------------------------------------------------------------

class TestConditions:
    VALID_TYPES = {"WHERE", "JOIN_ON"}

    @pytest.fixture(scope="class")
    def rows(self, lineage_output):
        with open(os.path.join(lineage_output, "tables", "conditions.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_condition_type_valid(self, rows):
        for r in rows:
            assert r["condition_type"] in self.VALID_TYPES, (
                f"Неизвестный condition_type='{r['condition_type']}'"
            )

    def test_expression_nonempty(self, rows):
        for r in rows:
            assert r["expression"].strip(), (
                f"Пустой expression в условии {r['condition_type']} узла {r['node_id']}"
            )


# ---------------------------------------------------------------------------
# TestJoins
# ---------------------------------------------------------------------------

class TestJoins:
    VALID_JOIN_TYPES = {"INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"}

    @pytest.fixture(scope="class")
    def rows(self, lineage_output):
        with open(os.path.join(lineage_output, "tables", "joins.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_join_type_valid(self, rows):
        for r in rows:
            assert r["join_type"] in self.VALID_JOIN_TYPES, (
                f"Неизвестный join_type='{r['join_type']}' в узле {r['node_id']}"
            )

    def test_on_expression_nonempty(self, rows):
        for r in rows:
            if r["join_type"] != "CROSS JOIN":
                assert r["on_expression"].strip(), (
                    f"Пустой on_expression для {r['join_type']} узла {r['node_id']}"
                )


# ---------------------------------------------------------------------------
# TestFieldLineage
# ---------------------------------------------------------------------------

class TestFieldLineage:

    @pytest.fixture(scope="class")
    def lineage(self, lineage_output):
        with open(os.path.join(lineage_output, "lineage", "field_lineage.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_root_is_list(self, lineage):
        """ВОЗМОЖНАЯ ОШИБКА: корень должен быть list[], не dict."""
        assert isinstance(lineage, list), (
            f"field_lineage.json: ожидается list, получено {type(lineage).__name__}"
        )

    def test_required_fields_present(self, lineage):
        for entry in lineage:
            assert "output_field"  in entry, f"Нет output_field:  {entry}"
            assert "final_node_id" in entry, f"Нет final_node_id: {entry['output_field']}"
            assert "chain"         in entry, f"Нет chain:         {entry['output_field']}"
            assert "depth"         in entry, f"Нет depth:         {entry['output_field']}"

    def test_chain_ends_at_physical_table(self, lineage):
        """
        Последнее звено chain должно иметь node_id == null
        и заполненный source_table.

        ВОЗМОЖНАЯ ОШИБКА: chain обрывается на ВТ вместо физической таблицы.
        """
        dangling = []
        for entry in lineage:
            chain = entry["chain"]
            if not chain:
                dangling.append(entry["output_field"])
                continue
            last = chain[-1]
            assert last.get("node_id") is None, (
                f"Поле '{entry['output_field']}': chain не дошёл до физической таблицы, "
                f"последний node_id={last.get('node_id')}"
            )
            assert last.get("source_table"), (
                f"Поле '{entry['output_field']}': финальное звено без source_table"
            )
        if dangling:
            pytest.xfail(f"{len(dangling)} полей без chain (вычисляемые): {dangling[:3]}")

    def test_depth_matches_chain_length(self, lineage):
        for entry in lineage:
            assert entry["depth"] == len(entry["chain"]), (
                f"Поле '{entry['output_field']}': depth={entry['depth']} "
                f"не совпадает с len(chain)={len(entry['chain'])}"
            )


# ---------------------------------------------------------------------------
# TestFieldMapping
# ---------------------------------------------------------------------------

class TestFieldMapping:
    REQUIRED_COLS = {
        "output_field", "final_node_id", "intermediate_node_id",
        "input_field", "rule_type", "transform_desc",
    }

    @pytest.fixture(scope="class")
    def rows(self, lineage_output):
        with open(os.path.join(lineage_output, "lineage", "field_mapping.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_columns_present(self, rows):
        assert rows, "field_mapping.csv пуст"
        missing = self.REQUIRED_COLS - set(rows[0].keys())
        assert not missing, f"Отсутствуют колонки: {missing}"

    def test_output_field_nonempty(self, rows):
        for r in rows:
            assert r["output_field"].strip(), "output_field пуст"


# ---------------------------------------------------------------------------
# TestDependencyMatrix
# ---------------------------------------------------------------------------

class TestDependencyMatrix:

    @pytest.fixture(scope="class")
    def matrix_data(self, lineage_output):
        with open(os.path.join(lineage_output, "lineage", "dependency_matrix.csv"),
                  encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
        return headers, rows

    def test_first_column_is_node_id(self, matrix_data):
        headers, _ = matrix_data
        assert headers[0] == "node_id", (
            f"Первая колонка должна быть 'node_id', получено '{headers[0]}'"
        )

    def test_column_headers_are_numeric(self, matrix_data):
        """ВОЗМОЖНАЯ ОШИБКА: заголовки столбцов должны быть числовыми ID."""
        headers, _ = matrix_data
        for h in headers[1:]:
            assert h.isdigit(), (
                f"Заголовок столбца должен быть числовым ID, получено '{h}'"
            )

    def test_values_are_zero_or_one(self, matrix_data):
        headers, rows = matrix_data
        col_ids = headers[1:]
        for row in rows:
            row_id = row[0]
            for i, val in enumerate(row[1:]):
                assert val in ("0", "1"), (
                    f"node {row_id} → col {col_ids[i]}: значение '{val}' (ожидается 0/1)"
                )

    def test_no_self_dependency(self, matrix_data):
        """
        ВОЗМОЖНАЯ ОШИБКА: матрица НЕ квадратная — диагональ проверяется
        только если row_id присутствует в col_ids.
        """
        headers, rows = matrix_data
        col_ids = headers[1:]
        for row in rows:
            row_id = row[0]
            if row_id in col_ids:
                idx = col_ids.index(row_id)
                assert row[1 + idx] == "0", (
                    f"node {row_id}: самозависимость в матрице (диагональ != 0)"
                )


# ---------------------------------------------------------------------------
# TestKeyFields
# ---------------------------------------------------------------------------

class TestKeyFields:

    @pytest.fixture(scope="class")
    def kf(self, lineage_output):
        with open(os.path.join(lineage_output, "lineage", "lineage_key_fields.json"),
                  encoding="utf-8") as f:
            return json.load(f)

    def test_root_is_dict(self, kf):
        assert isinstance(kf, dict), (
            f"lineage_key_fields.json: ожидается dict, получено {type(kf).__name__}"
        )

    def test_required_top_level_keys(self, kf):
        assert "generated_at" in kf, "Нет 'generated_at'"
        assert "key_fields"   in kf, "Нет 'key_fields'"

    def test_key_fields_is_list(self, kf):
        assert isinstance(kf["key_fields"], list), "'key_fields' должен быть списком"

    def test_entry_structure(self, kf):
        for entry in kf["key_fields"]:
            assert "field"     in entry, f"Нет 'field': {entry}"
            assert "chain"     in entry, f"Нет 'chain': {entry.get('field')}"
            assert "branching" in entry, f"Нет 'branching': {entry.get('field')}"

    def test_branching_is_bool(self, kf):
        """ВОЗМОЖНАЯ ОШИБКА: branching записывается как str 'true'/'false'."""
        for entry in kf["key_fields"]:
            assert isinstance(entry["branching"], bool), (
                f"'branching' должен быть bool (не str): поле '{entry.get('field')}', "
                f"значение {entry['branching']!r}"
            )


# ---------------------------------------------------------------------------
# TestParseSelectList — unit-тесты парсера
# ---------------------------------------------------------------------------

class TestParseSelectList:
    """
    Проверяет parse_select_list на конкретных случаях.
    source_table — это АЛИАС таблицы (не полное имя ВТ).
    """

    cases = [
        # (sql, exp_alias, exp_source_table, exp_source_field, exp_computed)
        (
            "ВЫБРАТЬ ТабА.Поле ИЗ ТабА",
            "Поле", "ТабА", "Поле", False,
        ),
        (
            "ВЫБРАТЬ ТабА.П КАК МойАлиас ИЗ ТабА",
            "МойАлиас", "ТабА", "П", False,
        ),
        (
            "ВЫБРАТЬ СУММА(ТабА.Кол) КАК Сумма ИЗ ТабА",
            "Сумма", "ТабА", "Кол", True,
        ),
        (
            "ВЫБРАТЬ 1 КАК Признак ИЗ ТабА",
            "Признак", None, None, True,
        ),
        (
            "ВЫБРАТЬ ТабА.* ИЗ ТабА",
            "*", "ТабА", "*", False,
        ),
        (
            "ВЫБРАТЬ ВЫБОР КОГДА ТабА.П = 1 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ КАК Признак ИЗ ТабА",
            "Признак", None, None, True,
        ),
        (
            # ВОЗМОЖНАЯ ОШИБКА: source_table здесь — алиас "Д", НЕ полное имя таблицы
            "ВЫБРАТЬ ЕСТЬНУЛЛ(Д.Сумма, 0) КАК СуммаВзносов ИЗ Д",
            "СуммаВзносов", "Д", "Сумма", True,
        ),
    ]

    @pytest.mark.parametrize("sql,exp_alias,exp_src_t,exp_src_f,exp_computed", cases)
    def test_parse_field(
        self, sql, exp_alias, exp_src_t, exp_src_f, exp_computed
    ):
        fields = parse_select_list(sql)
        assert fields, f"parse_select_list вернул пустой список для: {sql!r}"
        f0 = fields[0]
        assert f0["field_alias"] == exp_alias, (
            f"alias: ожидается {exp_alias!r}, получено {f0['field_alias']!r}\nSQL: {sql}"
        )
        assert f0["source_table"] == exp_src_t, (
            f"source_table: ожидается {exp_src_t!r}, получено {f0['source_table']!r}\nSQL: {sql}"
        )
        assert f0["source_field"] == exp_src_f, (
            f"source_field: ожидается {exp_src_f!r}, получено {f0['source_field']!r}\nSQL: {sql}"
        )
        assert f0["is_computed"] == exp_computed, (
            f"is_computed: ожидается {exp_computed!r}, получено {f0['is_computed']!r}\nSQL: {sql}"
        )
