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

def test_extract_placeholder_column_updates():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/update_employee.sql").read_text()
    result = parser.parse("update_employee.sql", raw)
    ph_updates = [u for u in result.column_updates if u.placeholder_name]
    assert len(ph_updates) >= 1
    col_names = {u.target_column for u in ph_updates}
    assert "name" in col_names

def test_placeholder_name_is_captured():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/update_employee.sql").read_text()
    result = parser.parse("update_employee.sql", raw)
    name_update = next((u for u in result.column_updates if u.target_column == "name"), None)
    assert name_update is not None
    assert name_update.placeholder_name == "dto.name"

def test_extract_column_copy_update():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/update_with_copy.sql").read_text()
    result = parser.parse("update_with_copy.sql", raw)
    copy_updates = [u for u in result.column_updates if u.source_table]
    assert len(copy_updates) >= 1
    u = copy_updates[0]
    assert u.target_table == "employee"
    assert u.source_table == "department"
    assert u.target_column == "name"
    assert u.source_column == "department_name"

def test_column_updates_empty_for_select():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/select_employee.sql").read_text()
    result = parser.parse("select_employee.sql", raw)
    assert result.column_updates == []
