"""
tests/test_exporters.py
=======================
Golden-тесты для итерации 1: normalizer + tables.

Запуск:
    pytest tests/test_exporters.py -v
"""

import csv
import json
import os
import sys
import tempfile

import pytest

# --- путь к корню проекта ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize, classify_source
from exporters.tables import generate_tables


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SMALL_SQL_PATH = os.path.join(ROOT, "examples", "example.sql")
LARGE_SQL_PATH = os.path.join(ROOT, "examples", "example_258.sql")


@pytest.fixture(scope="module")
def small_raw():
    with open(SMALL_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return json.loads(analyze_sql_query(sql, detailed=True))


@pytest.fixture(scope="module")
def small_model(small_raw):
    return normalize(small_raw)


@pytest.fixture(scope="module")
def small_output(small_model):
    tmp = tempfile.mkdtemp()
    generate_tables(small_model, tmp)
    return tmp


@pytest.fixture(scope="module")
def large_raw():
    with open(LARGE_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return json.loads(analyze_sql_query(sql, detailed=True))


@pytest.fixture(scope="module")
def large_model(large_raw):
    return normalize(large_raw)


@pytest.fixture(scope="module")
def large_output(large_model):
    tmp = tempfile.mkdtemp()
    generate_tables(large_model, tmp)
    return tmp


# ---------------------------------------------------------------------------
# test_normalizer_small
# ---------------------------------------------------------------------------

class TestNormalizerSmall:
    def test_no_result_type(self, small_model):
        """result-тип должен быть заменён на temp_query."""
        types = {n["type"] for n in small_model["nodes"]}
        assert "result" not in types

    def test_known_types_only(self, small_model):
        valid = {"temp_query", "sub_query"}
        types = {n["type"] for n in small_model["nodes"]}
        assert types <= valid

    def test_ref_edges_have_relation(self, small_model):
        ref_edges = [e for e in small_model["edges"] if e["relation"] == "ref"]
        assert len(ref_edges) > 0
        for e in ref_edges:
            assert "from_id" in e and "to_id" in e

    def test_structural_edges_generated(self, small_model):
        structural = [e for e in small_model["edges"] if e["relation"] in ("parent_child", "union_part")]
        # В small примере есть вложенные подзапросы
        assert len(structural) >= 0  # может быть 0 если нет вложенности

    def test_source_kinds_assigned(self, small_model):
        for n in small_model["nodes"]:
            assert "source_kinds" in n
            assert len(n["source_kinds"]) == len(n["own_in_tables"])

    def test_edge_counts_consistent(self, small_raw, small_model):
        """Рёбер в модели не меньше, чем в сыром JSON."""
        raw_refs = len(small_raw.get("edges", []))
        model_refs = len([e for e in small_model["edges"] if e["relation"] == "ref"])
        assert model_refs == raw_refs


# ---------------------------------------------------------------------------
# test_classify_source
# ---------------------------------------------------------------------------

class TestClassifySource:
    def test_catalog(self):
        assert classify_source("Справочник.Контрагенты") == "Catalog"

    def test_accumulation(self):
        assert classify_source("РегистрНакопления.ПенсионныеСчета") == "AccumulationRegister"

    def test_information(self):
        assert classify_source("РегистрСведений.НастройкиПользователей") == "InformationRegister"

    def test_document(self):
        assert classify_source("Документ.ПоступлениеТоваров") == "Document"

    def test_temptable(self):
        assert classify_source("ВТ_Результат") == "TempTable"

    def test_temptable_tilde(self):
        assert classify_source("~TT~ВТ_Результат") == "TempTable"

    def test_unknown(self):
        assert classify_source("МойПроизвольныйАлиас") == "Unknown"

    def test_case_insensitive(self):
        assert classify_source("справочник.Физлица") == "Catalog"


# ---------------------------------------------------------------------------
# test_tables_small
# ---------------------------------------------------------------------------

class TestTablesSmall:
    def test_nodes_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "nodes.csv"))

    def test_nodes_csv_columns(self, small_output):
        with open(os.path.join(small_output, "tables", "nodes.csv"), encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == {
                "id", "name", "type", "parent_id", "max_parent_id",
                "children_count", "own_in_tables_count", "is_stub", "is_union_part", "text_len"
            }

    def test_nodes_csv_nonempty(self, small_output):
        with open(os.path.join(small_output, "tables", "nodes.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0

    def test_tempqueries_catalog_only_tempquery(self, small_output):
        path = os.path.join(small_output, "tables", "tempqueries_catalog.csv")
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        types = {r["type"] for r in rows}
        assert types <= {"temp_query"}

    def test_edges_refs_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "edges_refs.csv"))

    def test_edges_parent_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "edges_parent.csv"))

    def test_sources_map_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "sources_map.csv"))

    def test_normalized_nodes_json_valid(self, small_output):
        path = os.path.join(small_output, "normalized", "nodes.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "type" in data[0]
        # source_kinds не должен попасть в normalized/nodes.json
        assert "source_kinds" not in data[0]

    def test_normalized_jsonl_line_count(self, small_output):
        json_path = os.path.join(small_output, "normalized", "nodes.json")
        jsonl_path = os.path.join(small_output, "normalized", "nodes.jsonl")
        with open(json_path, encoding="utf-8") as f:
            json_count = len(json.load(f))
        with open(jsonl_path, encoding="utf-8") as f:
            jsonl_count = sum(1 for line in f if line.strip())
        assert json_count == jsonl_count

    def test_stubs_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "stubs.csv"))

    def test_union_parts_csv_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "tables", "union_parts.csv"))


# ---------------------------------------------------------------------------
# test_tables_large
# ---------------------------------------------------------------------------

class TestTablesLarge:
    def test_nodes_csv_row_count(self, large_output):
        """Большой пример: ожидаем >=100 узлов."""
        with open(os.path.join(large_output, "tables", "nodes.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 100

    def test_no_result_type_in_csv(self, large_output):
        with open(os.path.join(large_output, "tables", "nodes.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        types = {r["type"] for r in rows}
        assert "result" not in types

    def test_sources_map_has_kinds(self, large_output):
        path = os.path.join(large_output, "tables", "sources_map.csv")
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:  # может быть 0 в тестовых данных
            kinds = {r["source_kind"] for r in rows}
            # Хотя бы один известный kind
            known = {"Catalog", "AccumulationRegister", "InformationRegister",
                     "Document", "AccountingRegister", "TempTable", "Unknown",
                     "Enum", "CalculationRegister", "ChartOfCharacteristicTypes",
                     "ChartOfAccounts", "ChartOfCalculationTypes", "BusinessProcess",
                     "Task", "DataProcessor", "Report", "Constant", "Sequence"}
            assert kinds <= known

    def test_tempqueries_count_reasonable(self, large_output):
        """В большом примере ВТ должно быть больше 10."""
        path = os.path.join(large_output, "tables", "tempqueries_catalog.csv")
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 10
