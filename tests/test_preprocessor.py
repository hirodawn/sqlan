from pathlib import Path
from analyzer.sql_parser.preprocessor import preprocess_2way_sql, extract_placeholders
import sqlglot

FIXTURE_SQL = Path("tests/fixtures/select_employee.sql").read_text()

def test_removes_if_markers():
    result = preprocess_2way_sql("SELECT * FROM t WHERE /*IF x != null*/x = /*x*/1/*END*/")
    assert "/*IF" not in result
    assert "/*END*/" not in result

def test_removes_begin_end():
    result = preprocess_2way_sql("SELECT * FROM t /*BEGIN*/WHERE id = 1/*END*/")
    assert "/*BEGIN*/" not in result
    assert "/*END*/" not in result

def test_keeps_default_numeric_value():
    result = preprocess_2way_sql("SELECT * FROM t WHERE id = /*id*/42")
    assert "42" in result

def test_keeps_default_string_value():
    result = preprocess_2way_sql("SELECT * FROM t WHERE name LIKE /*name*/'%test%'")
    assert "'%test%'" in result

def test_fixture_is_parseable_by_sqlglot():
    result = preprocess_2way_sql(FIXTURE_SQL)
    parsed = sqlglot.parse(result)
    assert any(stmt is not None for stmt in parsed)

def test_fixture_contains_employee_table():
    import sqlglot.expressions as exp
    result = preprocess_2way_sql(FIXTURE_SQL)
    tables = [t.name for stmt in sqlglot.parse(result) if stmt for t in stmt.find_all(exp.Table)]
    assert "employee" in tables

def test_extract_placeholders_from_update():
    # tests/fixtures/update_employee.sql contains:
    # SET name = /*dto.name*/'test', department_id = /*dto.departmentId*/1
    raw = Path("tests/fixtures/update_employee.sql").read_text()
    result = extract_placeholders(raw)
    assert result.get("name") == "dto.name"
    assert result.get("department_id") == "dto.departmentId"

def test_extract_placeholders_empty_when_no_placeholders():
    result = extract_placeholders("SELECT * FROM employee WHERE employee_id = 1")
    assert result == {}

def test_extract_placeholders_captures_where_clause_col():
    result = extract_placeholders("SELECT * FROM t WHERE id = /*id*/1")
    assert result.get("id") == "id"
