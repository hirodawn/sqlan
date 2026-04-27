from analyzer.models import (
    SqlReference, SqlAnalysis, JoinInfo,
    TableInfo, ForeignKey, ColumnCardinality, AnalysisResult,
    ColumnUpdate,
)

def test_sql_reference_fields():
    ref = SqlReference(
        sql_file="META-INF/sql/select.sql",
        calling_class="EmployeeDao",
        calling_method="findAll",
        operation="SELECT",
        line_number=42,
        java_file="src/EmployeeDao.java",
    )
    assert ref.operation == "SELECT"
    assert ref.line_number == 42

def test_analysis_result_defaults():
    result = AnalysisResult()
    assert result.sql_references == []
    assert result.sql_analyses == []
    assert result.table_info == {}
    assert result.foreign_keys == []
    assert result.column_cardinalities == []

def test_sql_analysis_defaults():
    a = SqlAnalysis(sql_file="test.sql")
    assert a.read_tables == []
    assert a.write_tables == []
    assert a.joins == []
    assert a.parse_error is None

def test_column_update_defaults():
    cu = ColumnUpdate(sql_file="x.sql", target_table="employee", target_column="name")
    assert cu.source_table is None
    assert cu.source_column is None
    assert cu.placeholder_name is None

def test_column_update_with_placeholder():
    cu = ColumnUpdate(
        sql_file="x.sql",
        target_table="employee",
        target_column="name",
        placeholder_name="dto.name",
    )
    assert cu.placeholder_name == "dto.name"
    assert cu.source_table is None

def test_column_update_with_source():
    cu = ColumnUpdate(
        sql_file="x.sql",
        target_table="employee",
        target_column="name",
        source_table="department",
        source_column="department_name",
    )
    assert cu.source_table == "department"
    assert cu.source_column == "department_name"

def test_sql_analysis_has_column_updates():
    a = SqlAnalysis(sql_file="test.sql")
    assert a.column_updates == []
