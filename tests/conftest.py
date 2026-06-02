"""
Общие pytest-фикстуры для всех тестовых модулей.
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
from exporters.tables import generate_tables

SMALL_SQL_PATH = os.path.join(ROOT, "examples", "example.sql")
LARGE_SQL_PATH = os.path.join(ROOT, "examples", "example_258.sql")


@pytest.fixture(scope="module")
def small_raw():
    with open(SMALL_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return json.loads(analyze_sql_query(sql, detailed=True))


@pytest.fixture(scope="module")
def small_model(small_raw):
    model = normalize(small_raw)
    tmp = tempfile.mkdtemp()
    generate_tables(model, tmp)
    return {"output_dir": tmp, "model": model}


@pytest.fixture(scope="module")
def large_raw():
    with open(LARGE_SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    return json.loads(analyze_sql_query(sql, detailed=True))


@pytest.fixture(scope="module")
def large_model(large_raw):
    model = normalize(large_raw)
    tmp = tempfile.mkdtemp()
    generate_tables(model, tmp)
    return {"output_dir": tmp, "model": model}
