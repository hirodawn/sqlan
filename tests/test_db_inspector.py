import pytest
from sqlalchemy import create_engine, text
from analyzer.db_inspector.inspector import DBInspector

@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.connect() as conn:
        conn.execute(text("""
            CREATE TABLE department (
                department_id INTEGER PRIMARY KEY,
                department_name TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE employee (
                employee_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department_id INTEGER,
                FOREIGN KEY (department_id) REFERENCES department(department_id)
            )
        """))
        conn.execute(text("INSERT INTO department VALUES (1, 'Engineering'), (2, 'Sales')"))
        conn.execute(text("INSERT INTO employee VALUES (1, 'Alice', 1), (2, 'Bob', 1), (3, 'Carol', 2)"))
        conn.commit()
    return e

def test_row_count_employee(engine):
    assert DBInspector(engine).get_row_count("employee") == 3

def test_row_count_department(engine):
    assert DBInspector(engine).get_row_count("department") == 2

def test_row_count_nonexistent_returns_minus_one(engine):
    inspector = DBInspector(engine)
    assert inspector.get_row_count("nonexistent") == -1

def test_column_cardinality(engine):
    inspector = DBInspector(engine)
    # department_id に 1と2の2種類の値がある
    assert inspector.get_column_cardinality("employee", "department_id") == 2

def test_get_foreign_keys(engine):
    inspector = DBInspector(engine)
    fks = inspector.get_foreign_keys("employee")
    assert len(fks) == 1
    assert fks[0].from_column == "department_id"
    assert fks[0].to_table == "department"
    assert fks[0].has_fk_constraint is True

def test_get_table_info(engine):
    inspector = DBInspector(engine)
    info = inspector.get_table_info("employee")
    assert info.name == "employee"
    assert info.row_count == 3
    assert "name" in info.columns

def test_inspect_tables(engine):
    inspector = DBInspector(engine)
    result = inspector.inspect_tables(["employee", "department"])
    assert "employee" in result
    assert result["employee"].row_count == 3
    assert result["department"].row_count == 2
