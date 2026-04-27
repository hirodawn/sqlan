# Column Dependency Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** テーブル単位のグラフをカラム単位に昇格させ、JOIN結合キー・UPDATEによる値フロー・Javaパラメータ名を可視化する。

**Architecture:** SQLパーサーにUPDATE SET句の解析とS2JDBCプレースホルダ抽出を追加し、GraphBuilderでカラムメタデータ付きノードと`column_copy`エッジを生成。フロントエンドはER図スタイルのノード描画とSQLファイルトグルを実装する。

**Tech Stack:** Python dataclasses, sqlglot AST, Cytoscape.js, cytoscape-node-html-label CDN

---

## ファイル構成

| ファイル | 変更内容 |
|---|---|
| `analyzer/models.py` | `ColumnUpdate` 追加、`SqlAnalysis.column_updates` フィールド追加 |
| `analyzer/sql_parser/preprocessor.py` | `extract_placeholders()` 関数追加 |
| `analyzer/sql_parser/parser.py` | `_collect_table_aliases()`, `_extract_column_updates()` 追加、`parse()` から呼び出し |
| `analyzer/graph_builder/builder.py` | テーブルノードのカラムをdict形式に変更、JOINエッジに`label`/`sql_files`追加、`column_copy`エッジ生成 |
| `tests/fixtures/update_with_copy.sql` | 列コピー用テストSQLフィクスチャ（新規） |
| `tests/test_models.py` | `ColumnUpdate` テスト追加 |
| `tests/test_preprocessor.py` | `extract_placeholders` テスト追加 |
| `tests/test_sql_parser.py` | `column_updates` テスト追加 |
| `tests/test_graph_builder.py` | カラムdict形式・`column_copy`エッジのテスト追加 |
| `web/frontend/index.html` | ERノード描画、SQLトグル、`column_copy`エッジスタイル、詳細パネル更新 |

---

### Task 1: `ColumnUpdate` モデルと `SqlAnalysis.column_updates` フィールド

**Files:**
- Modify: `analyzer/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: テスト記述**

`tests/test_models.py` に以下を追記する（既存の import 行の `SqlAnalysis` の後に `ColumnUpdate` を追加）:

```python
from analyzer.models import (
    SqlReference, SqlAnalysis, JoinInfo,
    TableInfo, ForeignKey, ColumnCardinality, AnalysisResult,
    ColumnUpdate,
)

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
```

- [ ] **Step 2: テスト失敗を確認**

```bash
venv/bin/python -m pytest tests/test_models.py::test_column_update_defaults -v
```

Expected: `ImportError: cannot import name 'ColumnUpdate'`

- [ ] **Step 3: モデル実装**

`analyzer/models.py` を以下のように変更する。`JoinInfo` の直後に `ColumnUpdate` を追加し、`SqlAnalysis` に `column_updates` フィールドを追加する:

```python
from dataclasses import dataclass, field

@dataclass
class SqlReference:
    sql_file: str
    calling_class: str
    calling_method: str
    operation: str  # SELECT, INSERT, UPDATE, DELETE, UNKNOWN
    line_number: int
    java_file: str

@dataclass
class JoinInfo:
    left_table: str
    left_column: str
    right_table: str
    right_column: str

@dataclass
class ColumnUpdate:
    sql_file: str
    target_table: str
    target_column: str
    source_table: str | None = None
    source_column: str | None = None
    placeholder_name: str | None = None

@dataclass
class SqlAnalysis:
    sql_file: str
    read_tables: list[str] = field(default_factory=list)
    write_tables: list[str] = field(default_factory=list)
    joins: list[JoinInfo] = field(default_factory=list)
    column_updates: list[ColumnUpdate] = field(default_factory=list)
    parse_error: str | None = None

@dataclass
class TableInfo:
    name: str
    row_count: int = 0
    columns: list[str] = field(default_factory=list)

@dataclass
class ForeignKey:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    has_fk_constraint: bool = True

@dataclass
class ColumnCardinality:
    table: str
    column: str
    distinct_count: int

@dataclass
class AnalysisResult:
    sql_references: list[SqlReference] = field(default_factory=list)
    sql_analyses: list[SqlAnalysis] = field(default_factory=list)
    table_info: dict[str, TableInfo] = field(default_factory=dict)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    column_cardinalities: list[ColumnCardinality] = field(default_factory=list)
```

- [ ] **Step 4: テスト通過を確認**

```bash
venv/bin/python -m pytest tests/test_models.py -v
```

Expected: 全テスト PASS（新規4件 + 既存3件）

- [ ] **Step 5: コミット**

```bash
git add analyzer/models.py tests/test_models.py
git commit -m "feat: add ColumnUpdate model and SqlAnalysis.column_updates field"
```

---

### Task 2: `extract_placeholders()` — S2JDBCプレースホルダ名の抽出

**Files:**
- Modify: `analyzer/sql_parser/preprocessor.py`
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: テスト記述**

`tests/test_preprocessor.py` の末尾に追記する（import に `extract_placeholders` を追加）:

```python
from analyzer.sql_parser.preprocessor import preprocess_2way_sql, extract_placeholders

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

def test_extract_placeholders_ignores_where_if_no_set():
    result = extract_placeholders("SELECT * FROM t WHERE id = /*id*/1")
    # WHERE clause placeholder is still captured (col name = "id")
    assert result.get("id") == "id"
```

- [ ] **Step 2: テスト失敗を確認**

```bash
venv/bin/python -m pytest tests/test_preprocessor.py::test_extract_placeholders_from_update -v
```

Expected: `ImportError: cannot import name 'extract_placeholders'`

- [ ] **Step 3: 実装**

`analyzer/sql_parser/preprocessor.py` を以下に置き換える:

```python
import re

_PLACEHOLDER_RE = re.compile(r'(\w+)\s*=\s*/\*(\w[\w.]*)\*/', re.IGNORECASE)

def extract_placeholders(sql: str) -> dict[str, str]:
    """
    col = /*paramName*/value 形式のパターンをスキャンし
    {column_name_lower: placeholder_name} を返す。
    同じカラム名が複数回現れた場合は最後のものを採用。
    """
    result = {}
    for m in _PLACEHOLDER_RE.finditer(sql):
        result[m.group(1).lower()] = m.group(2)
    return result

def preprocess_2way_sql(sql: str) -> str:
    # Seasar2の特殊コメント /*...*/ を除去する。
    # /*IF*/, /*END*/, /*BEGIN*/, /*paramName*/ をすべてこの1パスで処理できる。
    # /*paramName*/defaultValue の場合、コメントだけが除去されデフォルト値が残る。
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # 行コメント形式のSeasar2ディレクティブ: --IF, --ELSE, --END（直前の空白も除去）
    sql = re.sub(r'[ \t]*--(?:IF|ELSE|END)[^\n]*', '', sql)
    # 行末の残余スペースを除去
    sql = re.sub(r'[ \t]+$', '', sql, flags=re.MULTILINE)
    # 連続する空白を整理（改行は保持）
    sql = re.sub(r'[ \t]+', ' ', sql)
    sql = re.sub(r'\n{3,}', '\n\n', sql)
    return sql.strip()
```

- [ ] **Step 4: テスト通過を確認**

```bash
venv/bin/python -m pytest tests/test_preprocessor.py -v
```

Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add analyzer/sql_parser/preprocessor.py tests/test_preprocessor.py
git commit -m "feat: add extract_placeholders() for S2JDBC param name extraction"
```

---

### Task 3: `_extract_column_updates()` — UPDATE SET 句の解析

**Files:**
- Create: `tests/fixtures/update_with_copy.sql`
- Modify: `analyzer/sql_parser/parser.py`
- Modify: `tests/test_sql_parser.py`

- [ ] **Step 1: テスト用フィクスチャ作成**

`tests/fixtures/update_with_copy.sql` を作成する:

```sql
UPDATE employee
SET
  name = department.department_name,
  department_id = /*dto.deptId*/1
FROM department
WHERE employee.department_id = department.department_id
  AND employee.employee_id = /*dto.employeeId*/1
```

- [ ] **Step 2: テスト記述**

`tests/test_sql_parser.py` の末尾に追記する:

```python
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
```

- [ ] **Step 3: テスト失敗を確認**

```bash
venv/bin/python -m pytest tests/test_sql_parser.py::test_extract_placeholder_column_updates -v
```

Expected: FAIL（`result.column_updates` が空リスト）

- [ ] **Step 4: パーサー実装**

`analyzer/sql_parser/parser.py` を以下に置き換える:

```python
import re
import sqlglot
import sqlglot.expressions as exp
from analyzer.models import SqlAnalysis, JoinInfo, ColumnUpdate
from analyzer.sql_parser.preprocessor import preprocess_2way_sql, extract_placeholders


def _collect_table_aliases(stmt: exp.Expression) -> dict[str, str]:
    """エイリアス → 実テーブル名 の辞書を返す（すべて小文字）。"""
    aliases: dict[str, str] = {}
    for table in stmt.find_all(exp.Table):
        name = (table.name or "").lower()
        if not name:
            continue
        aliases[name] = name
        alias = (table.alias or "").lower()
        if alias:
            aliases[alias] = name
    return aliases


class SqlFileParser:
    def __init__(self, dialect: str = "mysql"):
        self.dialect = dialect

    def parse(self, sql_file: str, raw_sql: str) -> SqlAnalysis:
        result = SqlAnalysis(sql_file=sql_file)
        try:
            normalized = preprocess_2way_sql(raw_sql)
            statements = sqlglot.parse(
                normalized, dialect=self.dialect,
                error_level=sqlglot.ErrorLevel.WARN,
            )
            for stmt in statements:
                if stmt is None:
                    continue
                self._extract_tables(stmt, result)
                self._extract_joins(stmt, result)
                self._extract_column_updates(stmt, sql_file, raw_sql, result)
        except Exception as e:
            result.parse_error = str(e)
            result.read_tables = self._fallback_extract(raw_sql)
        return result

    def _extract_tables(self, stmt: exp.Expression, result: SqlAnalysis) -> None:
        if isinstance(stmt, (exp.Update, exp.Delete, exp.Insert)):
            target = stmt.find(exp.Table)
            if target and target.name:
                if target.name not in result.write_tables:
                    result.write_tables.append(target.name)
            for table in stmt.find_all(exp.Table):
                if table.name and table.name not in result.write_tables and table.name not in result.read_tables:
                    result.read_tables.append(table.name)
            result.read_tables = [t for t in result.read_tables if t not in result.write_tables]
        else:
            for table in stmt.find_all(exp.Table):
                if table.name and table.name not in result.read_tables:
                    result.read_tables.append(table.name)

    def _extract_joins(self, stmt: exp.Expression, result: SqlAnalysis) -> None:
        for join in stmt.find_all(exp.Join):
            on = join.args.get("on")
            if not on:
                continue
            for eq in on.find_all(exp.EQ):
                left, right = eq.left, eq.right
                if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                    result.joins.append(JoinInfo(
                        left_table=left.table or "",
                        left_column=left.name,
                        right_table=right.table or "",
                        right_column=right.name,
                    ))

    def _extract_column_updates(
        self,
        stmt: exp.Expression,
        sql_file: str,
        raw_sql: str,
        result: SqlAnalysis,
    ) -> None:
        if not isinstance(stmt, exp.Update):
            return

        placeholders = extract_placeholders(raw_sql)
        aliases = _collect_table_aliases(stmt)

        target_expr = stmt.args.get("this")
        if not target_expr:
            return
        target_name = (target_expr.name or "").lower()
        target_alias = (target_expr.alias or "").lower() or target_name

        for eq in (stmt.args.get("expressions") or []):
            if not isinstance(eq, exp.EQ):
                continue
            left, right = eq.left, eq.right
            if not isinstance(left, exp.Column):
                continue

            tgt_col = left.name.lower()

            if isinstance(right, exp.Column):
                src_alias = (right.table or "").lower() or target_alias
                src_table = aliases.get(src_alias, src_alias) or target_name
                src_col = right.name.lower()
                result.column_updates.append(ColumnUpdate(
                    sql_file=sql_file,
                    target_table=target_name,
                    target_column=tgt_col,
                    source_table=src_table,
                    source_column=src_col,
                ))
            elif tgt_col in placeholders:
                result.column_updates.append(ColumnUpdate(
                    sql_file=sql_file,
                    target_table=target_name,
                    target_column=tgt_col,
                    placeholder_name=placeholders[tgt_col],
                ))

    def _fallback_extract(self, sql: str) -> list[str]:
        tables = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        tables += re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
        return list(dict.fromkeys(tables))
```

- [ ] **Step 5: テスト通過を確認**

```bash
venv/bin/python -m pytest tests/test_sql_parser.py -v
```

Expected: 全テスト PASS（新規4件 + 既存5件）

- [ ] **Step 6: コミット**

```bash
git add tests/fixtures/update_with_copy.sql analyzer/sql_parser/parser.py tests/test_sql_parser.py
git commit -m "feat: extract column updates and placeholder names from UPDATE SET clause"
```

---

### Task 4: グラフビルダー — カラムメタデータ・column_copyエッジ・JOINエッジのsql_files

**Files:**
- Modify: `analyzer/graph_builder/builder.py`
- Modify: `tests/test_graph_builder.py`

- [ ] **Step 1: テスト記述**

`tests/test_graph_builder.py` を以下に置き換える（既存テストを保持しつつ新規テストを追加）:

```python
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
```

- [ ] **Step 2: テスト失敗を確認**

```bash
venv/bin/python -m pytest tests/test_graph_builder.py::test_table_node_columns_are_dicts -v
```

Expected: FAIL（columns が list[str] のまま）

- [ ] **Step 3: GraphBuilder 実装**

`analyzer/graph_builder/builder.py` を以下に置き換える:

```python
from analyzer.models import AnalysisResult, ColumnUpdate


class GraphBuilder:
    def build(self, result: AnalysisResult) -> dict:
        nodes: list[dict] = []
        edges: list[dict] = []
        _eid = [0]

        def eid() -> str:
            _eid[0] += 1
            return f"e{_eid[0]}"

        fk_pairs: set[tuple] = {
            (fk.from_table, fk.from_column, fk.to_table, fk.to_column)
            for fk in result.foreign_keys
        }

        # SQLファイル数カウント（テーブルごと）
        sql_counts: dict[str, int] = {}
        for analysis in result.sql_analyses:
            for t in analysis.read_tables + analysis.write_tables:
                sql_counts[t] = sql_counts.get(t, 0) + 1

        # JOINキー集合: {table_name_lower: {col_name_lower, ...}}
        join_keys: dict[str, set[str]] = {}
        for analysis in result.sql_analyses:
            for join in analysis.joins:
                for tbl, col in [(join.left_table, join.left_column),
                                  (join.right_table, join.right_column)]:
                    tbl_l = tbl.lower()
                    join_keys.setdefault(tbl_l, set()).add(col.lower())

        # UPDATEターゲット: {table_name_lower: {col_name_lower: ColumnUpdate}}
        update_targets: dict[str, dict[str, ColumnUpdate]] = {}
        for analysis in result.sql_analyses:
            for cu in analysis.column_updates:
                tbl_l = cu.target_table.lower()
                update_targets.setdefault(tbl_l, {})[cu.target_column.lower()] = cu

        # JOINエッジのsql_files: {frozenset: [sql_file, ...]}
        join_sql_files: dict[frozenset, list[str]] = {}
        for analysis in result.sql_analyses:
            for join in analysis.joins:
                key = frozenset([(join.left_table.lower(), join.left_column.lower()),
                                  (join.right_table.lower(), join.right_column.lower())])
                join_sql_files.setdefault(key, []).append(analysis.sql_file)

        # SQLファイルからテーブルへの参照: {table_name: [sql_file, ...]}
        table_sql_refs: dict[str, list[str]] = {}
        for analysis in result.sql_analyses:
            for t in analysis.read_tables + analysis.write_tables:
                table_sql_refs.setdefault(t, [])
                if analysis.sql_file not in table_sql_refs[t]:
                    table_sql_refs[t].append(analysis.sql_file)

        # 全テーブル名収集（SQL参照 + JOINから）
        all_table_names: set[str] = set(sql_counts.keys())
        for analysis in result.sql_analyses:
            for join in analysis.joins:
                all_table_names.add(join.left_table)
                all_table_names.add(join.right_table)

        # テーブルノード生成
        for name in sorted(all_table_names):
            info = result.table_info.get(name)
            name_l = name.lower()
            col_data = []
            for col_name in (info.columns if info else []):
                col_l = col_name.lower()
                is_join = col_l in join_keys.get(name_l, set())
                cu = update_targets.get(name_l, {}).get(col_l)
                is_update = cu is not None
                placeholder = cu.placeholder_name if cu else None
                update_src = (
                    f"{cu.source_table}.{cu.source_column}"
                    if cu and cu.source_table
                    else None
                )
                col_data.append({
                    "name": col_name,
                    "is_join_key": is_join,
                    "is_update_target": is_update,
                    "placeholder_name": placeholder,
                    "update_source": update_src,
                })
            nodes.append({"data": {
                "id": f"table:{name}",
                "label": name,
                "type": "table",
                "row_count": info.row_count if info else -1,
                "sql_file_count": sql_counts.get(name, 0),
                "columns": col_data,
                "sql_files": table_sql_refs.get(name, []),
            }})

        # SQLファイルノード生成
        ref_map = {r.sql_file: r for r in result.sql_references}
        seen_sql: set[str] = set()
        for analysis in result.sql_analyses:
            if analysis.sql_file in seen_sql:
                continue
            seen_sql.add(analysis.sql_file)
            ref = ref_map.get(analysis.sql_file)
            nodes.append({"data": {
                "id": f"sql:{analysis.sql_file}",
                "label": analysis.sql_file.split("/")[-1],
                "type": "sql_file",
                "operation": ref.operation if ref else "UNKNOWN",
                "calling_class": ref.calling_class if ref else "",
                "calling_method": ref.calling_method if ref else "",
                "sql_file": analysis.sql_file,
            }})

        # JOINエッジ生成
        seen_joins: set[frozenset] = set()
        for analysis in result.sql_analyses:
            for join in analysis.joins:
                lt = join.left_table.lower()
                lc = join.left_column.lower()
                rt = join.right_table.lower()
                rc = join.right_column.lower()
                key = frozenset([(lt, lc), (rt, rc)])
                if key in seen_joins:
                    continue
                seen_joins.add(key)
                has_fk = (lt, lc, rt, rc) in fk_pairs or (rt, rc, lt, lc) in fk_pairs
                edges.append({"data": {
                    "id": eid(),
                    "source": f"table:{join.left_table}",
                    "target": f"table:{join.right_table}",
                    "type": "join",
                    "left_column": lc,
                    "right_column": rc,
                    "label": f"{lc} = {rc}",
                    "has_fk": has_fk,
                    "sql_files": list(set(join_sql_files.get(key, []))),
                }})

        # column_copyエッジ生成（source_tableが存在するColumnUpdateから）
        seen_copy: dict[tuple, dict] = {}
        for analysis in result.sql_analyses:
            for cu in analysis.column_updates:
                if not cu.source_table:
                    continue
                key = (cu.source_table, cu.source_column, cu.target_table, cu.target_column)
                if key not in seen_copy:
                    seen_copy[key] = {
                        "source": f"table:{cu.source_table}",
                        "target": f"table:{cu.target_table}",
                        "type": "column_copy",
                        "source_column": cu.source_column,
                        "target_column": cu.target_column,
                        "label": f"{cu.source_column} → {cu.target_column}",
                        "sql_files": [],
                    }
                if analysis.sql_file not in seen_copy[key]["sql_files"]:
                    seen_copy[key]["sql_files"].append(analysis.sql_file)
        for data in seen_copy.values():
            edges.append({"data": {"id": eid(), **data}})

        # READ/WRITEエッジ生成
        seen_rw: set[tuple[str, str, str]] = set()
        for analysis in result.sql_analyses:
            sid = f"sql:{analysis.sql_file}"
            for t in analysis.read_tables:
                key = (sid, f"table:{t}", "read")
                if key not in seen_rw:
                    seen_rw.add(key)
                    edges.append({"data": {"id": eid(), "source": sid, "target": f"table:{t}", "type": "read"}})
            for t in analysis.write_tables:
                key = (sid, f"table:{t}", "write")
                if key not in seen_rw:
                    seen_rw.add(key)
                    edges.append({"data": {"id": eid(), "source": sid, "target": f"table:{t}", "type": "write"}})

        return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: テスト通過を確認**

```bash
venv/bin/python -m pytest tests/test_graph_builder.py -v
```

Expected: 全テスト PASS（新規10件 + 既存6件）

- [ ] **Step 5: 全テスト確認**

```bash
venv/bin/python -m pytest tests/ -v
```

Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add analyzer/graph_builder/builder.py tests/test_graph_builder.py
git commit -m "feat: enrich graph with column metadata, column_copy edges, and JOIN sql_files"
```

---

### Task 5: フロントエンド — ER図ノード描画・SQLトグル・詳細パネル更新

**Files:**
- Modify: `web/frontend/index.html`

このタスクは自動テストがない（UIはブラウザで確認）。動作確認を各ステップで行う。

- [ ] **Step 1: `index.html` を全面的に書き換える**

`web/frontend/index.html` を以下の内容に置き換える:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>sqlan — SQL依存関係アナライザー</title>
  <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/cytoscape-node-html-label@1.2.2/dist/cytoscape-node-html-label.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; display: flex; flex-direction: column; height: 100vh; background: #1a1a2e; color: #e0e0e0; }
    #header { display: flex; align-items: center; gap: 10px; padding: 8px 14px; background: #16213e; border-bottom: 1px solid #0f3460; flex-wrap: wrap; }
    #header h1 { font-size: 1.1rem; color: #e94560; flex-shrink: 0; }
    #search { padding: 5px 8px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; width: 160px; }
    #filter-op, #layout-sel { padding: 5px 6px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; }
    .hdr-label { font-size: 0.75rem; color: #888; white-space: nowrap; }
    #min-refs { width: 48px; padding: 4px 6px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; text-align: center; }
    #sql-toggle-wrap { display: flex; align-items: center; gap: 6px; }
    #sql-toggle { appearance: none; width: 34px; height: 18px; background: #333; border-radius: 9px; cursor: pointer; position: relative; transition: background 0.2s; flex-shrink: 0; }
    #sql-toggle:checked { background: #2d6b4a; }
    #sql-toggle::after { content: ''; position: absolute; width: 14px; height: 14px; background: #fff; border-radius: 50%; top: 2px; left: 2px; transition: left 0.2s; }
    #sql-toggle:checked::after { left: 18px; }
    #btn-analyze { padding: 5px 14px; border-radius: 4px; border: none; background: #e94560; color: #fff; cursor: pointer; margin-left: auto; flex-shrink: 0; }
    #btn-analyze:disabled { opacity: 0.5; cursor: default; }
    #progress-bar { height: 3px; background: #e94560; width: 0%; transition: width 0.3s; }
    #cache-bar { display: none; align-items: center; gap: 10px; padding: 5px 14px; background: #0d2137; border-bottom: 1px solid #1a4060; font-size: 0.8rem; color: #7aaabb; }
    #btn-load-cache { padding: 3px 10px; border-radius: 3px; border: none; background: #1a5c3a; color: #fff; cursor: pointer; font-size: 0.78rem; }
    #btn-clear-cache { padding: 3px 10px; border-radius: 3px; border: none; background: #3a1a1a; color: #ccc; cursor: pointer; font-size: 0.78rem; }
    #stats-bar { padding: 2px 14px; font-size: 0.72rem; color: #446; background: #12192e; text-align: right; min-height: 16px; }
    #warn-bar { display: none; background: #3a2a00; border-bottom: 1px solid #a06000; padding: 6px 14px; font-size: 0.82rem; color: #f0c040; }
    #warn-bar summary { cursor: pointer; user-select: none; }
    #warn-list { margin-top: 6px; max-height: 160px; overflow-y: auto; padding-left: 16px; }
    #warn-list li { color: #e0c080; font-size: 0.78rem; line-height: 1.6; font-family: monospace; }
    #main { display: flex; flex: 1; overflow: hidden; }
    #cy { flex: 1; }
    #detail { width: 290px; background: #16213e; border-left: 1px solid #0f3460; padding: 14px; overflow-y: auto; }
    #detail h2 { font-size: 0.9rem; color: #e94560; margin-bottom: 12px; }
    .detail-row { margin-bottom: 8px; font-size: 0.82rem; }
    .detail-label { color: #888; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 3px; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; }
    .badge-select { background: #1a6b4a; } .badge-update { background: #6b3a1a; } .badge-insert { background: #1a3a6b; } .badge-unknown { background: #444; }
    .badge-table { background: #2d1b6b; } .badge-fk { background: #1a5c6b; }
    /* ER node styles (rendered via cytoscape-node-html-label) */
    .er-node { font-family: monospace; font-size: 11px; color: #e0e0e0; border-radius: 4px; overflow: hidden; min-width: 120px; }
    .er-header { background: #3a2080; padding: 4px 8px; font-weight: bold; text-align: center; border-bottom: 1px solid #6a4bdb; font-size: 11px; }
    .er-col { padding: 2px 8px; border-bottom: 1px solid #2a1a4a; white-space: nowrap; font-size: 10px; }
    .er-col-join { background: #2a3a00; color: #c8e060; }
    .er-col-update { background: #3a1a00; color: #e0a060; }
    .er-col-normal { color: #aaa; }
    .col-list-item { display: inline-block; padding: 1px 5px; margin: 1px; border-radius: 2px; font-size: 0.75rem; }
    .col-join { background: #2a3a00; color: #c8e060; }
    .col-update { background: #3a1a00; color: #e0a060; }
    .sql-file-ref { color: #2d8b6b; font-size: 0.78rem; background: #0d2018; border-radius: 2px; padding: 2px 5px; margin: 2px 0; display: block; }
  </style>
</head>
<body>
  <div id="header">
    <h1>sqlan</h1>
    <input id="search" type="text" placeholder="テーブル名で絞り込み">
    <select id="filter-op">
      <option value="">すべての操作</option>
      <option value="SELECT">SELECT</option>
      <option value="UPDATE">UPDATE</option>
      <option value="INSERT">INSERT</option>
      <option value="WRITE">WRITE</option>
    </select>
    <select id="layout-sel">
      <option value="cose">force-directed</option>
      <option value="breadthfirst">階層型</option>
      <option value="grid">グリッド</option>
      <option value="circle">円形</option>
    </select>
    <span class="hdr-label">最小参照数</span>
    <input id="min-refs" type="number" min="1" value="1" title="この件数以上のSQLに参照されているテーブルのみ表示">
    <div id="sql-toggle-wrap">
      <input type="checkbox" id="sql-toggle">
      <label for="sql-toggle" class="hdr-label">SQLファイルを表示</label>
    </div>
    <button id="btn-analyze">解析実行</button>
  </div>
  <div id="progress-bar"></div>
  <div id="cache-bar">
    <span>💾</span><span id="cache-info"></span>
    <button id="btn-load-cache">グラフを読み込む</button>
    <button id="btn-clear-cache">キャッシュをクリア</button>
  </div>
  <div id="stats-bar"></div>
  <details id="warn-bar">
    <summary id="warn-summary"></summary>
    <ul id="warn-list"></ul>
  </details>
  <div id="main">
    <div id="cy"></div>
    <div id="detail">
      <h2>詳細</h2>
      <div id="detail-body" style="color:#666;font-size:0.82rem;">ノードをクリックしてください</div>
    </div>
  </div>
  <script>
    let cy = null;
    let currentJobId = null;
    let pollTimer = null;
    let fullElements = null;

    const $ = id => document.getElementById(id);

    // ── ER ノード HTML 生成 ──────────────────────────────────────────────────
    function buildErHtml(data) {
      const cols = data.columns || [];
      const rows = cols.map(c => {
        let cls = 'er-col-normal';
        let suffix = '';
        if (c.is_join_key) cls = 'er-col-join';
        else if (c.is_update_target) cls = 'er-col-update';
        if (c.placeholder_name) suffix = ` <span style="color:#888;font-size:9px;">/*${c.placeholder_name}*/</span>`;
        if (c.update_source) suffix = ` <span style="color:#888;font-size:9px;">← ${c.update_source}</span>`;
        const icon = c.is_join_key ? '▶ ' : c.is_update_target ? '✏ ' : '  ';
        return `<div class="er-col ${cls}">${icon}${c.name}${suffix}</div>`;
      }).join('');
      return `<div class="er-node"><div class="er-header">${data.label}</div>${rows}</div>`;
    }

    function computeNodeSize(data) {
      const cols = data.columns || [];
      const maxLen = Math.max(data.label.length, ...cols.map(c => c.name.length + 3));
      return {
        w: Math.max(130, maxLen * 7 + 32),
        h: 26 + cols.length * 21 + 4,
      };
    }

    // ── Cytoscape 初期化 ─────────────────────────────────────────────────────
    function initCytoscape(elements) {
      if (cy) cy.destroy();

      const tableNodes = elements.filter(e => !e.data.source && e.data.type === 'table');
      const nodeCount = elements.filter(e => !e.data.source).length;
      const isLarge = nodeCount > 150;

      if (isLarge && $('layout-sel').value === 'cose') {
        $('layout-sel').value = 'grid';
      }
      const curveStyle = isLarge ? 'straight' : 'bezier';

      // テーブルノードのサイズを事前計算
      tableNodes.forEach(e => {
        const { w, h } = computeNodeSize(e.data);
        e.data.node_width = w;
        e.data.node_height = h;
      });

      cytoscape.use(cytoscapeNodeHtmlLabel);

      cy = cytoscape({
        container: $('cy'),
        elements,
        hideEdgesOnViewport: isLarge,
        textureOnViewport: isLarge,
        style: [
          { selector: 'node[type="table"]', style: {
            'shape': 'rectangle',
            'background-color': '#2d1b6b',
            'border-color': '#5a3bbb',
            'border-width': 1,
            'label': '',
            'width': 'data(node_width)',
            'height': 'data(node_height)',
          }},
          { selector: 'node[type="sql_file"]', style: {
            'background-color': '#2d6b4a',
            'label': 'data(label)',
            'color': '#fff',
            'font-size': '9px',
            'text-valign': 'center',
            'shape': 'rectangle',
            'width': isLarge ? '14px' : '80px',
            'height': isLarge ? '14px' : '30px',
            'display': $('sql-toggle').checked ? 'element' : 'none',
          }},
          { selector: 'edge[type="join"]', style: {
            'line-color': '#e94560',
            'width': 2,
            'target-arrow-shape': 'none',
            'curve-style': curveStyle,
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#e94560',
            'text-background-color': '#1a1a2e',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
          }},
          { selector: 'edge[type="join"][has_fk]', style: { 'line-style': 'solid' } },
          { selector: 'edge[type="column_copy"]', style: {
            'line-color': '#1ab4b4',
            'width': 2,
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#1ab4b4',
            'curve-style': curveStyle,
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#1ab4b4',
            'text-background-color': '#1a1a2e',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
          }},
          { selector: 'edge[type="read"]', style: {
            'line-color': '#4a8b6b',
            'width': 1,
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#4a8b6b',
            'curve-style': curveStyle,
            'display': $('sql-toggle').checked ? 'element' : 'none',
          }},
          { selector: 'edge[type="write"]', style: {
            'line-color': '#e9a020',
            'width': 1,
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#e9a020',
            'curve-style': curveStyle,
            'display': $('sql-toggle').checked ? 'element' : 'none',
          }},
          { selector: ':selected', style: { 'border-width': 3, 'border-color': '#fff' } },
        ],
        layout: { name: $('layout-sel').value, padding: 40 },
      });

      // ER図HTMLラベルを適用（大規模グラフ時はスキップ）
      if (!isLarge) {
        cy.nodeHtmlLabel([{
          query: 'node[type="table"]',
          halign: 'center',
          valign: 'top',
          halignBox: 'center',
          valignBox: 'top',
          tpl: buildErHtml,
        }]);
      } else {
        // 大規模グラフ: テキストラベルのみ
        cy.style().selector('node[type="table"]').style({ 'label': 'data(label)', 'font-size': '8px', 'color': '#fff', 'text-valign': 'center', 'width': '40px', 'height': '40px' }).update();
      }

      cy.on('tap', 'node', e => showNodeDetail(e.target.data()));
      cy.on('tap', 'edge', e => showEdgeDetail(e.target.data()));
      applySqlFileVisibility();
      updateStats();
    }

    // ── SQLファイル表示切替 ──────────────────────────────────────────────────
    function applySqlFileVisibility() {
      if (!cy) return;
      const show = $('sql-toggle').checked;
      const disp = show ? 'element' : 'none';
      cy.nodes('[type="sql_file"]').style('display', disp);
      cy.edges('[type="read"],[type="write"]').style('display', disp);
    }

    // ── 最小参照数フィルター ────────────────────────────────────────────────
    function applyMinRefs() {
      if (!fullElements) return;
      const min = parseInt($('min-refs').value) || 1;
      const visibleTableIds = new Set(
        fullElements
          .filter(e => !e.data.source && e.data.type === 'table' && (e.data.sql_file_count || 0) >= min)
          .map(e => e.data.id)
      );
      const filtered = fullElements.filter(e => {
        if (!e.data.source) {
          return e.data.type === 'sql_file' || visibleTableIds.has(e.data.id);
        }
        const srcOk = e.data.source.startsWith('sql:') || visibleTableIds.has(e.data.source);
        const tgtOk = e.data.target.startsWith('sql:') || visibleTableIds.has(e.data.target);
        return srcOk && tgtOk;
      });
      initCytoscape(filtered);
      applyFilter();
    }

    // ── 検索・操作フィルター ────────────────────────────────────────────────
    function applyFilter() {
      if (!cy) return;
      const q = $('search').value.toLowerCase();
      const op = $('filter-op').value;
      cy.nodes().forEach(n => {
        const d = n.data();
        const matchQ = !q || d.label.toLowerCase().includes(q);
        const matchOp = !op || d.operation === op || (op === 'WRITE' && ['UPDATE', 'INSERT', 'DELETE'].includes(d.operation));
        n.style('display', matchQ && matchOp ? 'element' : 'none');
      });
      cy.edges().forEach(e => {
        const src = cy.getElementById(e.data('source'));
        const tgt = cy.getElementById(e.data('target'));
        const bothVisible = src.style('display') !== 'none' && tgt.style('display') !== 'none';
        // SQL系エッジはトグルも考慮
        const type = e.data('type');
        const sqlHidden = (type === 'read' || type === 'write') && !$('sql-toggle').checked;
        e.style('display', bothVisible && !sqlHidden ? 'element' : 'none');
      });
      updateStats();
    }

    function updateStats() {
      if (!cy || !fullElements) { $('stats-bar').textContent = ''; return; }
      const totalNodes = fullElements.filter(e => !e.data.source).length;
      $('stats-bar').textContent =
        `表示: ノード ${cy.nodes().length}件 / 全${totalNodes}件、エッジ ${cy.edges().length}件`;
    }

    // ── 詳細パネル ──────────────────────────────────────────────────────────
    function showNodeDetail(data) {
      let html = '';
      if (data.type === 'table') {
        const colHtml = (data.columns || []).map(c => {
          const cls = c.is_join_key ? 'col-join' : c.is_update_target ? 'col-update' : '';
          const icon = c.is_join_key ? '▶ ' : c.is_update_target ? '✏ ' : '';
          let extra = '';
          if (c.placeholder_name) extra = ` <small style="color:#888;">/*${c.placeholder_name}*/</small>`;
          if (c.update_source) extra = ` <small style="color:#888;">← ${c.update_source}</small>`;
          return `<span class="col-list-item ${cls}">${icon}${c.name}${extra}</span>`;
        }).join('');
        const sqlHtml = (data.sql_files || []).map(f =>
          `<span class="sql-file-ref">📄 ${f}</span>`
        ).join('');
        html = `
          <div class="detail-row"><div class="detail-label">種別</div><span class="badge badge-table">テーブル</span></div>
          <div class="detail-row"><div class="detail-label">名前</div>${data.label}</div>
          <div class="detail-row"><div class="detail-label">行数</div>${data.row_count >= 0 ? data.row_count.toLocaleString() : '不明'}</div>
          <div class="detail-row"><div class="detail-label">カラム</div>${colHtml || '不明'}</div>
          <div class="detail-row"><div class="detail-label">参照SQL (${(data.sql_files || []).length}件)</div>${sqlHtml || 'なし'}</div>`;
      } else {
        const op = data.operation || '';
        const badgeClass = { SELECT: 'badge-select', UPDATE: 'badge-update', INSERT: 'badge-insert' }[op] || 'badge-unknown';
        html = `
          <div class="detail-row"><div class="detail-label">種別</div>SQLファイル</div>
          <div class="detail-row"><div class="detail-label">ファイル名</div>${data.label}</div>
          <div class="detail-row"><div class="detail-label">操作</div><span class="badge ${badgeClass}">${op}</span></div>
          <div class="detail-row"><div class="detail-label">呼び出しクラス</div>${data.calling_class || '不明'}</div>
          <div class="detail-row"><div class="detail-label">呼び出しメソッド</div>${data.calling_method || '不明'}</div>
          <div class="detail-row"><div class="detail-label">パス</div><small>${data.sql_file || ''}</small></div>`;
      }
      $('detail-body').innerHTML = html;
    }

    function showEdgeDetail(data) {
      let html = `<div class="detail-row"><div class="detail-label">エッジ種別</div>${data.type}</div>`;
      if (data.type === 'join') {
        html += `
          <div class="detail-row"><div class="detail-label">結合条件</div><code>${data.left_column} = ${data.right_column}</code></div>
          <div class="detail-row"><div class="detail-label">FK制約</div>${data.has_fk ? '<span class="badge badge-fk">あり</span>' : 'なし'}</div>`;
      } else if (data.type === 'column_copy') {
        const src = (data.source || '').replace('table:', '');
        const tgt = (data.target || '').replace('table:', '');
        html += `
          <div class="detail-row"><div class="detail-label">コピー元</div><code>${src}.${data.source_column}</code></div>
          <div class="detail-row"><div class="detail-label">コピー先</div><code>${tgt}.${data.target_column}</code></div>`;
      }
      if (data.sql_files && data.sql_files.length > 0) {
        const sqlHtml = data.sql_files.map(f => `<span class="sql-file-ref">📄 ${f}</span>`).join('');
        html += `<div class="detail-row"><div class="detail-label">SQL ファイル (${data.sql_files.length}件)</div>${sqlHtml}</div>`;
      }
      $('detail-body').innerHTML = html;
    }

    // ── 警告バナー ──────────────────────────────────────────────────────────
    function showWarnings(warnings) {
      const bar = $('warn-bar');
      if (!warnings || warnings.length === 0) { bar.style.display = 'none'; return; }
      $('warn-summary').textContent = `⚠ SQLファイルが見つかりませんでした: ${warnings.length}件（クリックで詳細表示）`;
      $('warn-list').innerHTML = warnings.map(w => `<li>${w.replace(/</g, '&lt;')}</li>`).join('');
      bar.style.display = 'block';
    }

    // ── キャッシュ ──────────────────────────────────────────────────────────
    async function checkCache() {
      try {
        const info = await (await fetch('/api/cache')).json();
        if (!info.exists) return;
        $('cache-info').textContent = `前回の解析結果: ${info.cached_at}`;
        $('cache-bar').style.display = 'flex';
      } catch (_) {}
    }

    $('btn-load-cache').addEventListener('click', async () => {
      $('cache-bar').style.display = 'none';
      $('progress-bar').style.width = '50%';
      const [graph, status] = await Promise.all([
        fetch('/api/graph/cached').then(r => r.json()),
        fetch('/api/status/cached').then(r => r.json()),
      ]);
      fullElements = [...graph.nodes, ...graph.edges];
      showWarnings(status.warnings || []);
      applyMinRefs();
      $('progress-bar').style.width = '100%';
    });

    $('btn-clear-cache').addEventListener('click', async () => {
      await fetch('/api/cache', { method: 'DELETE' });
      $('cache-bar').style.display = 'none';
    });

    // ── イベントリスナー ────────────────────────────────────────────────────
    $('search').addEventListener('input', applyFilter);
    $('filter-op').addEventListener('change', applyFilter);
    $('layout-sel').addEventListener('change', () => {
      if (cy) cy.layout({ name: $('layout-sel').value, padding: 40 }).run();
    });
    $('min-refs').addEventListener('change', applyMinRefs);
    $('sql-toggle').addEventListener('change', applySqlFileVisibility);

    $('btn-analyze').addEventListener('click', async () => {
      $('btn-analyze').disabled = true;
      $('cache-bar').style.display = 'none';
      $('progress-bar').style.width = '10%';
      const resp = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const { job_id } = await resp.json();
      currentJobId = job_id;
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async () => {
        const s = await (await fetch(`/api/status/${job_id}`)).json();
        $('progress-bar').style.width = (s.progress || 0) + '%';
        if (s.state === 'completed') {
          clearInterval(pollTimer);
          const graph = await (await fetch(`/api/graph/${job_id}`)).json();
          fullElements = [...graph.nodes, ...graph.edges];
          showWarnings(s.warnings || []);
          applyMinRefs();
          $('btn-analyze').disabled = false;
          $('progress-bar').style.width = '100%';
        } else if (s.state === 'error') {
          clearInterval(pollTimer);
          alert('解析に失敗しました。\n\n' + (s.error || '詳細不明'));
          $('btn-analyze').disabled = false;
        }
      }, 500);
    });

    checkCache();
  </script>
</body>
</html>
```

- [ ] **Step 2: サーバーを起動して動作確認**

```bash
venv/bin/python main.py config.toml
```

ブラウザで `http://localhost:8000` を開く。

確認事項:
- [ ] ページが正常に表示される（コンソールエラーなし）
- [ ] キャッシュがある場合、キャッシュバーが表示される
- [ ] キャッシュ読み込み後、テーブルノードがER図スタイルで表示される
- [ ] カラム行に ▶（JOIN）と ✏（UPDATE）のマークが見える
- [ ] 水色エッジ（column_copy）が存在する場合に表示される
- [ ] ヘッダーの「SQLファイルを表示」トグルで SQL ノードが現れ/消える
- [ ] テーブルノードをクリックすると詳細パネルにカラム一覧と参照SQL一覧が表示される
- [ ] JOINエッジをクリックすると結合条件と参照SQLが表示される

- [ ] **Step 3: コミット**

```bash
git add web/frontend/index.html
git commit -m "feat: ER-style table nodes, column_copy edge style, SQL file toggle, updated detail panel"
```

---

## 完了確認

- [ ] **全テスト通過**

```bash
venv/bin/python -m pytest tests/ -v
```

Expected: 全テスト PASS（Task 1〜4 で追加されたテストを含む）

- [ ] **リモートへプッシュ**

```bash
git push origin feature/implement
```
