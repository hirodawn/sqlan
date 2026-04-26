from pathlib import Path
from analyzer.sql_parser.parser import SqlFileParser
from analyzer.models import SqlAnalysis

def test_extract_read_tables_from_simple_select():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/select_employee.sql").read_text()
    result = parser.parse("select_employee.sql", raw)
    assert "employee" in result.read_tables
    assert result.write_tables == []

def test_extract_tables_from_join():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/select_with_join.sql").read_text()
    result = parser.parse("select_with_join.sql", raw)
    assert "employee" in result.read_tables
    assert "department" in result.read_tables

def test_extract_join_info():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/select_with_join.sql").read_text()
    result = parser.parse("select_with_join.sql", raw)
    assert len(result.joins) == 1
    join = result.joins[0]
    tables_in_join = {join.left_table, join.right_table}
    # sqlglotはエイリアスをそのまま保持するため left_table="e", right_table="d" になる
    assert tables_in_join == {"e", "d"}
    assert "department_id" in (join.left_column, join.right_column)

def test_extract_write_tables_from_update():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/update_employee.sql").read_text()
    result = parser.parse("update_employee.sql", raw)
    assert "employee" in result.write_tables
    assert result.read_tables == []

def test_invalid_sql_returns_result_without_raising():
    # sqlglotはWARNモードで構文エラーを例外に変えないため parse_error は None のまま返る
    parser = SqlFileParser()
    result = parser.parse("bad.sql", "THIS IS NOT VALID SQL !!!")
    assert isinstance(result, SqlAnalysis)
    assert result.sql_file == "bad.sql"
