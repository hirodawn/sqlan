import pytest
from pathlib import Path
from analyzer.java_scanner.scanner import JavaScanner

FIXTURE = str(Path("tests/fixtures"))

@pytest.fixture(scope="module")
def refs():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    return scanner.scan()

def test_finds_select_references(refs):
    sql_files = [r.sql_file for r in refs]
    assert any("select_employee.sql" in f for f in sql_files)

def test_finds_update_references(refs):
    sql_files = [r.sql_file for r in refs]
    assert any("update_employee.sql" in f for f in sql_files)

def test_detects_select_operation(refs):
    select_refs = [r for r in refs if "select_employee" in r.sql_file]
    assert len(select_refs) > 0
    assert all(r.operation == "SELECT" for r in select_refs)

def test_detects_update_operation(refs):
    update_refs = [r for r in refs if "update_employee" in r.sql_file]
    assert len(update_refs) > 0
    assert all(r.operation == "UPDATE" for r in update_refs)

def test_detects_insert_operation(refs):
    insert_refs = [r for r in refs if "insert_employee" in r.sql_file]
    assert len(insert_refs) > 0
    assert all(r.operation == "INSERT" for r in insert_refs)

def test_detects_unknown_operation(refs):
    unknown_refs = [r for r in refs if "custom_audit" in r.sql_file]
    assert len(unknown_refs) > 0
    assert all(r.operation == "UNKNOWN" for r in unknown_refs)

def test_records_calling_class(refs):
    assert any(r.calling_class == "SampleDao" for r in refs)
