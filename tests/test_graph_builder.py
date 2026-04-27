from analyzer.models import (
    AnalysisResult, SqlReference, SqlAnalysis, JoinInfo,
    TableInfo, ForeignKey, ColumnUpdate,
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


def _make_result_with_copy() -> AnalysisResult:
    result = _make_result()
    result.sql_analyses[0].column_updates = [
        ColumnUpdate(
            sql_file="META-INF/sql/select_employee.sql",
            target_table="employee",
            target_column="name",
            source_table="department",
            source_column="department_name",
        ),
        ColumnUpdate(
            sql_file="META-INF/sql/select_employee.sql",
            target_table="employee",
            target_column="department_id",
            placeholder_name="dto.deptId",
        ),
    ]
    return result


# ── 既存テスト（変更なし）────────────────────────────────────────────────────

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


# ── 新規テスト ──────────────────────────────────────────────────────────────

def test_table_node_columns_are_dicts():
    graph = GraphBuilder().build(_make_result())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    cols = node["data"]["columns"]
    assert len(cols) > 0
    assert isinstance(cols[0], dict)
    assert "name" in cols[0]
    assert "is_join_key" in cols[0]
    assert "is_update_target" in cols[0]
    assert "placeholder_name" in cols[0]
    assert "update_source" in cols[0]

def test_join_key_column_flagged():
    graph = GraphBuilder().build(_make_result())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    dept_col = next(c for c in node["data"]["columns"] if c["name"] == "department_id")
    assert dept_col["is_join_key"] is True

def test_non_join_column_not_flagged():
    graph = GraphBuilder().build(_make_result())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    name_col = next(c for c in node["data"]["columns"] if c["name"] == "name")
    assert name_col["is_join_key"] is False

def test_join_edge_has_label_and_sql_files():
    graph = GraphBuilder().build(_make_result())
    join_edges = [e for e in graph["edges"] if e["data"]["type"] == "join"]
    e = join_edges[0]
    assert "label" in e["data"]
    assert "sql_files" in e["data"]
    assert isinstance(e["data"]["sql_files"], list)

def test_join_edge_label_contains_column_names():
    graph = GraphBuilder().build(_make_result())
    join_edges = [e for e in graph["edges"] if e["data"]["type"] == "join"]
    label = join_edges[0]["data"]["label"]
    assert "department_id" in label

def test_column_copy_edge_generated():
    graph = GraphBuilder().build(_make_result_with_copy())
    copy_edges = [e for e in graph["edges"] if e["data"]["type"] == "column_copy"]
    assert len(copy_edges) == 1
    e = copy_edges[0]
    assert e["data"]["source"] == "table:department"
    assert e["data"]["target"] == "table:employee"
    assert e["data"]["source_column"] == "department_name"
    assert e["data"]["target_column"] == "name"

def test_column_copy_edge_has_sql_files():
    graph = GraphBuilder().build(_make_result_with_copy())
    copy_edges = [e for e in graph["edges"] if e["data"]["type"] == "column_copy"]
    assert len(copy_edges[0]["data"]["sql_files"]) >= 1

def test_placeholder_column_flagged():
    graph = GraphBuilder().build(_make_result_with_copy())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    dept_id_col = next(c for c in node["data"]["columns"] if c["name"] == "department_id")
    assert dept_id_col["is_update_target"] is True
    assert dept_id_col["placeholder_name"] == "dto.deptId"

def test_copy_target_column_flagged():
    graph = GraphBuilder().build(_make_result_with_copy())
    node = next(n for n in graph["nodes"] if n["data"]["id"] == "table:employee")
    name_col = next(c for c in node["data"]["columns"] if c["name"] == "name")
    assert name_col["is_update_target"] is True
    assert name_col["update_source"] == "department.department_name"
