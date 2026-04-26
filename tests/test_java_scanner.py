from pathlib import Path
from analyzer.java_scanner.scanner import JavaScanner

FIXTURE = str(Path("tests/fixtures"))

def test_finds_select_references():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    refs = scanner.scan()
    sql_files = [r.sql_file for r in refs]
    assert any("select_employee.sql" in f for f in sql_files)

def test_finds_update_references():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    refs = scanner.scan()
    sql_files = [r.sql_file for r in refs]
    assert any("update_employee.sql" in f for f in sql_files)

def test_detects_select_operation():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    refs = scanner.scan()
    select_refs = [r for r in refs if "select_employee" in r.sql_file]
    assert len(select_refs) > 0
    assert select_refs[0].operation == "SELECT"

def test_detects_update_operation():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    refs = scanner.scan()
    update_refs = [r for r in refs if "update_employee" in r.sql_file]
    assert len(update_refs) > 0
    assert update_refs[0].operation == "UPDATE"

def test_records_calling_class():
    scanner = JavaScanner(java_root=FIXTURE, sql_root=FIXTURE)
    refs = scanner.scan()
    assert any(r.calling_class == "SampleDao" for r in refs)
