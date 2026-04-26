from analyzer.models import (
    SqlReference, SqlAnalysis, JoinInfo,
    TableInfo, ForeignKey, ColumnCardinality, AnalysisResult,
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
