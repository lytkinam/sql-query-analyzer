"""
tests/test_texts.py
===================
Тесты итерации 2: exporters/texts.py

Запуск:
    pytest tests/test_texts.py -v
"""

import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sql_query_analyzer import analyze_sql_query
from exporters.normalizer import normalize
from exporters.texts import generate_texts, normalize_sql


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SMALL_SQL_PATH = os.path.join(ROOT, "examples", "example.sql")
LARGE_SQL_PATH = os.path.join(ROOT, "examples", "example_258.sql")


@pytest.fixture(scope="module")
def small_model():
    with open(SMALL_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    raw = json.loads(analyze_sql_query(sql, detailed=True))
    return normalize(raw)


@pytest.fixture(scope="module")
def small_output(small_model):
    tmp = tempfile.mkdtemp()
    generate_texts(small_model, tmp)
    return tmp


@pytest.fixture(scope="module")
def large_model():
    with open(LARGE_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    raw = json.loads(analyze_sql_query(sql, detailed=True))
    return normalize(raw)


@pytest.fixture(scope="module")
def large_output(large_model):
    tmp = tempfile.mkdtemp()
    generate_texts(large_model, tmp)
    return tmp


# ---------------------------------------------------------------------------
# TestNormalizeSql
# ---------------------------------------------------------------------------

class TestNormalizeSql:
    def test_keyword_uppercase_1c(self):
        result = normalize_sql("выбрать 1 из Справочник.Номенклатура")
        assert result.startswith("ВЫБРАТЬ")
        assert " ИЗ " in result

    def test_keyword_uppercase_ansi(self):
        result = normalize_sql("select 1 from dual")
        assert "SELECT" in result
        assert "FROM" in result

    def test_extra_spaces_collapsed(self):
        result = normalize_sql("ВЫБРАТЬ   1    ИЗ   Таблица")
        assert "  " not in result

    def test_empty_lines_collapsed(self):
        result = normalize_sql("ВЫБРАТЬ 1\n\n\n\nИЗ Т")
        assert "\n\n\n" not in result

    def test_empty_string(self):
        assert normalize_sql("") == ""

    def test_strip_result(self):
        result = normalize_sql("  \nВЫБРАТЬ 1  \n")
        assert not result.startswith(" ")
        assert not result.endswith(" ")


# ---------------------------------------------------------------------------
# TestTextsSmall
# ---------------------------------------------------------------------------

class TestTextsSmall:
    def test_query_texts_dir_exists(self, small_output):
        assert os.path.isdir(os.path.join(small_output, "query_texts"))

    def test_texts_index_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "query_texts", "texts_index.json"))

    def test_normalized_queries_exists(self, small_output):
        assert os.path.exists(os.path.join(small_output, "query_texts", "normalized_queries.sql"))

    def test_texts_index_valid_json(self, small_output):
        with open(os.path.join(small_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        assert isinstance(index, list)
        assert len(index) > 0

    def test_texts_index_has_required_fields(self, small_output):
        with open(os.path.join(small_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        required = {"node_id", "name", "path", "text_len", "text_hash", "line_count"}
        for entry in index:
            assert required <= set(entry.keys()), f"Нет полей: {required - set(entry.keys())}"

    def test_texts_index_hash_format(self, small_output):
        with open(os.path.join(small_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        for entry in index:
            assert entry["text_hash"].startswith("sha256:"), f"bad hash: {entry['text_hash']}"

    def test_sql_files_exist_for_all_nodes(self, small_model, small_output):
        for node in small_model["nodes"]:
            path = os.path.join(small_output, "query_texts", f"node_{node['id']}.sql")
            assert os.path.exists(path), f"Отсутствует: {path}"

    def test_md_files_exist_for_all_nodes(self, small_model, small_output):
        for node in small_model["nodes"]:
            path = os.path.join(small_output, "query_texts", f"node_{node['id']}.md")
            assert os.path.exists(path), f"Отсутствует: {path}"

    def test_sql_header_has_node_id(self, small_model, small_output):
        node = small_model["nodes"][0]
        path = os.path.join(small_output, "query_texts", f"node_{node['id']}.sql")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert f"-- Node ID: {node['id']}" in content

    def test_md_has_h1_with_name(self, small_model, small_output):
        node = small_model["nodes"][0]
        path = os.path.join(small_output, "query_texts", f"node_{node['id']}.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert content.startswith("# ")
        assert str(node["id"]) in content

    def test_md_has_sql_code_block(self, small_model, small_output):
        node = small_model["nodes"][0]
        path = os.path.join(small_output, "query_texts", f"node_{node['id']}.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "```sql" in content

    def test_normalized_queries_has_separators(self, small_output):
        with open(os.path.join(small_output, "query_texts", "normalized_queries.sql"), encoding="utf-8") as f:
            content = f.read()
        # Должен содержать хотя бы один разделитель
        assert "-- =====" in content

    def test_index_count_equals_nodes(self, small_model, small_output):
        with open(os.path.join(small_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        assert len(index) == len(small_model["nodes"])

    def test_text_len_matches_file(self, small_model, small_output):
        """text_len в индексе должен соответствовать len(текста узла)."""
        with open(os.path.join(small_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        node_by_id = {n["id"]: n for n in small_model["nodes"]}
        for entry in index:
            node = node_by_id[entry["node_id"]]
            expected_len = len((node.get("text", "") or "").strip())
            assert entry["text_len"] == expected_len, (
                f"node {entry['node_id']}: text_len={entry['text_len']} != {expected_len}"
            )


# ---------------------------------------------------------------------------
# TestTextsLarge
# ---------------------------------------------------------------------------

class TestTextsLarge:
    def test_sql_file_count(self, large_model, large_output):
        sql_files = [
            f for f in os.listdir(os.path.join(large_output, "query_texts"))
            if f.endswith(".sql") and f.startswith("node_")
        ]
        assert len(sql_files) == len(large_model["nodes"])

    def test_md_file_count(self, large_model, large_output):
        md_files = [
            f for f in os.listdir(os.path.join(large_output, "query_texts"))
            if f.endswith(".md") and f.startswith("node_")
        ]
        assert len(md_files) == len(large_model["nodes"])

    def test_no_empty_hashes(self, large_output):
        with open(os.path.join(large_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        for entry in index:
            assert entry["text_hash"] != "sha256:", f"empty hash for node {entry['node_id']}"

    def test_normalized_queries_nonempty(self, large_output):
        path = os.path.join(large_output, "query_texts", "normalized_queries.sql")
        size = os.path.getsize(path)
        assert size > 1000, f"Ожидали >1KB, получили {size} bytes"

    def test_index_unique_ids(self, large_output):
        with open(os.path.join(large_output, "query_texts", "texts_index.json"), encoding="utf-8") as f:
            index = json.load(f)
        ids = [e["node_id"] for e in index]
        assert len(ids) == len(set(ids)), "Дубликаты node_id в индексе"
