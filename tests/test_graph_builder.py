from analyzer.models import (
    AnalysisResult, SqlReference, SqlAnalysis, JoinInfo,
    TableInfo, ForeignKey,
)
from analyzer.graph_builder.builder import GraphBuilder

def _make_result() -> AnalysisResult:
    result = AnalysisResult()
    result.sql_references = [
        SqlReference(
            sql_file="META-INF/sql/select_employee.sql",
            calling_class="EmployeeDao",
            calling_method="findAll",
            operation="SELECT",
            line_number=10,
            java_file="EmployeeDao.java",
        )
    ]
    result.sql_analyses = [
        SqlAnalysis(
            sql_file="META-INF/sql/select_employee.sql",
            read_tables=["employee", "department"],
            write_tables=[],
            joins=[JoinInfo(
                left_table="employee", left_column="department_id",
                right_table="department", right_column="department_id",
            )],
        )
    ]
    result.table_info = {
        "employee":   TableInfo(name="employee",   row_count=100, columns=["employee_id", "name", "department_id"]),
        "department": TableInfo(name="department", row_count=5,   columns=["department_id", "department_name"]),
    }
    result.foreign_keys = [
        ForeignKey(from_table="employee", from_column="department_id",
                   to_table="department", to_column="department_id", has_fk_constraint=True)
    ]
    return result

def test_builds_table_nodes():
    graph = GraphBuilder().build(_make_result())
    ids = [n["data"]["id"] for n in graph["nodes"]]
    assert "table:employee" in ids
    assert "table:department" in ids

def test_builds_sql_file_nodes():
    graph = GraphBuilder().build(_make_result())
    ids = [n["data"]["id"] for n in graph["nodes"]]
    assert "sql:META-INF/sql/select_employee.sql" in ids

def test_table_node_has_row_count():
    graph = GraphBuilder().build(_make_result())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    assert node["data"]["row_count"] == 100

def test_builds_join_edge():
    graph = GraphBuilder().build(_make_result())
    join_edges = [e for e in graph["edges"] if e["data"]["type"] == "join"]
    assert len(join_edges) == 1
    e = join_edges[0]
    sources = {e["data"]["source"].removeprefix("table:"), e["data"]["target"].removeprefix("table:")}
    assert "employee" in sources
    assert "department" in sources

def test_join_edge_has_fk_flag():
    graph = GraphBuilder().build(_make_result())
    join_edges = [e for e in graph["edges"] if e["data"]["type"] == "join"]
    assert join_edges[0]["data"]["has_fk"] is True

def test_builds_read_edges():
    graph = GraphBuilder().build(_make_result())
    read_edges = [e for e in graph["edges"] if e["data"]["type"] == "read"]
    assert len(read_edges) >= 1
    assert any(e["data"]["source"] == "sql:META-INF/sql/select_employee.sql" for e in read_edges)
