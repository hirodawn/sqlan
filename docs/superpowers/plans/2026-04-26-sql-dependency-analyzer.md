# SQL依存関係アナライザー 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** S2JDBC 2-way SQLファイルを解析してDB実データと照合し、テーブル間の依存関係をブラウザでインタラクティブに可視化するWebアプリケーションを構築する。

**Architecture:** Pythonのみで構成。java_scanner（Javaソース解析）→ sql_parser（2-way SQL前処理+sqlglot解析）→ db_inspector（SQLAlchemy経由の実データ照合）→ graph_builder（Cytoscape.js向けグラフJSON生成）のパイプライン。FastAPIがAPIサーバーと静的フロントエンド配信を担い、Plain HTML/JS + Cytoscape.jsでインタラクティブグラフを表示する。

**Tech Stack:** Python 3.11+, sqlglot, SQLAlchemy 2.x, FastAPI, uvicorn, Cytoscape.js, pytest, TOML

---

## ファイル構成

```
sqlan/
├── analyzer/
│   ├── __init__.py
│   ├── models.py                  # 全コンポーネント共通のデータクラス
│   ├── java_scanner/
│   │   ├── __init__.py
│   │   └── scanner.py             # JavaScannerクラス
│   ├── sql_parser/
│   │   ├── __init__.py
│   │   ├── preprocessor.py        # 2-way SQL前処理（Seasar2コメント除去）
│   │   └── parser.py              # sqlglot解析ラッパー
│   ├── db_inspector/
│   │   ├── __init__.py
│   │   └── inspector.py           # DBInspectorクラス（SQLAlchemy）
│   └── graph_builder/
│       ├── __init__.py
│       └── builder.py             # GraphBuilderクラス
├── web/
│   ├── __init__.py
│   ├── app.py                     # FastAPIアプリファクトリ
│   ├── routes.py                  # APIルート定義
│   └── frontend/
│       └── index.html             # Single-page app（Cytoscape.js）
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── SampleDao.java         # テスト用Javaソース
│   │   ├── select_employee.sql    # テスト用2-way SQL（SELECT）
│   │   ├── select_with_join.sql   # テスト用2-way SQL（JOIN）
│   │   └── update_employee.sql    # テスト用2-way SQL（UPDATE）
│   ├── test_models.py
│   ├── test_preprocessor.py
│   ├── test_sql_parser.py
│   ├── test_java_scanner.py
│   ├── test_db_inspector.py
│   ├── test_graph_builder.py
│   └── test_api.py
├── config.toml                    # 設定ファイルのテンプレート
├── main.py                        # エントリポイント
└── requirements.txt
```

---

## Task 1: プロジェクトセットアップ

**Files:**
- Create: `requirements.txt`
- Create: `config.toml`
- Create: `main.py`
- Create: `analyzer/__init__.py`, `analyzer/java_scanner/__init__.py`, `analyzer/sql_parser/__init__.py`, `analyzer/db_inspector/__init__.py`, `analyzer/graph_builder/__init__.py`
- Create: `web/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: requirements.txtを作成する**

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
sqlalchemy>=2.0.0
sqlglot>=23.0.0
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: ディレクトリとパッケージファイルを作成する**

```bash
mkdir -p analyzer/java_scanner analyzer/sql_parser analyzer/db_inspector analyzer/graph_builder
mkdir -p web/frontend tests/fixtures
touch analyzer/__init__.py analyzer/java_scanner/__init__.py
touch analyzer/sql_parser/__init__.py analyzer/db_inspector/__init__.py
touch analyzer/graph_builder/__init__.py
touch web/__init__.py tests/__init__.py
```

- [ ] **Step 3: config.tomlを作成する**

```toml
[source]
java_root = "/path/to/java/project/src"
sql_root  = "/path/to/java/project/src/main/resources"

[database]
url = "mysql+pymysql://user:password@localhost:3306/mydb"
# url = "postgresql+psycopg2://user:password@localhost:5432/mydb"
# SQLiteでのテスト: "sqlite:///./test.db"

[analysis]
timeout_seconds    = 300
cardinality_sample = 10000
```

- [ ] **Step 4: main.pyを作成する**

```python
import sys
import tomllib
import uvicorn

def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    config = load_config(config_path)
    from web.app import create_app
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 5: 依存パッケージをインストールして確認する**

```bash
pip install -r requirements.txt
python3 -c "import sqlglot; import fastapi; import sqlalchemy; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: コミットする**

```bash
git add requirements.txt config.toml main.py analyzer/ web/ tests/
git commit -m "chore: initial project scaffold"
```

---

## Task 2: 共通データモデル

**Files:**
- Create: `analyzer/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: テストを書く**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.models'`

- [ ] **Step 3: models.pyを実装する**

`analyzer/models.py`:
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
class SqlAnalysis:
    sql_file: str
    read_tables: list[str] = field(default_factory=list)
    write_tables: list[str] = field(default_factory=list)
    joins: list[JoinInfo] = field(default_factory=list)
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

- [ ] **Step 4: テストを実行してパスを確認する**

```bash
pytest tests/test_models.py -v
```

Expected: `3 passed`

- [ ] **Step 5: コミットする**

```bash
git add analyzer/models.py tests/test_models.py
git commit -m "feat: add shared data models"
```

---

## Task 3: 2-way SQL 前処理器

**Files:**
- Create: `analyzer/sql_parser/preprocessor.py`
- Create: `tests/fixtures/select_employee.sql`
- Create: `tests/test_preprocessor.py`

- [ ] **Step 1: フィクスチャSQLを作成する**

`tests/fixtures/select_employee.sql`:
```sql
SELECT
  e.employee_id,
  e.name
FROM
  employee e
/*BEGIN*/
WHERE
  /*IF dto.departmentId != null*/
  e.department_id = /*dto.departmentId*/1
  /*END*/
  /*IF dto.name != null*/
  AND e.name LIKE /*dto.name*/'%test%'
  /*END*/
/*END*/
ORDER BY e.employee_id
```

- [ ] **Step 2: テストを書く**

`tests/test_preprocessor.py`:
```python
from pathlib import Path
from analyzer.sql_parser.preprocessor import preprocess_2way_sql
import sqlglot

FIXTURE_SQL = Path("tests/fixtures/select_employee.sql").read_text()

def test_removes_if_markers():
    result = preprocess_2way_sql("SELECT * FROM t WHERE /*IF x != null*/x = /*x*/1/*END*/")
    assert "/*IF" not in result
    assert "/*END*/" not in result

def test_removes_begin_end():
    result = preprocess_2way_sql("SELECT * FROM t /*BEGIN*/WHERE id = 1/*END*/")
    assert "/*BEGIN*/" not in result
    assert "/*END*/" not in result

def test_keeps_default_numeric_value():
    result = preprocess_2way_sql("SELECT * FROM t WHERE id = /*id*/42")
    assert "42" in result

def test_keeps_default_string_value():
    result = preprocess_2way_sql("SELECT * FROM t WHERE name LIKE /*name*/'%test%'")
    assert "'%test%'" in result

def test_fixture_is_parseable_by_sqlglot():
    result = preprocess_2way_sql(FIXTURE_SQL)
    parsed = sqlglot.parse(result)
    assert any(stmt is not None for stmt in parsed)

def test_fixture_contains_employee_table():
    import sqlglot.expressions as exp
    result = preprocess_2way_sql(FIXTURE_SQL)
    tables = [t.name for stmt in sqlglot.parse(result) if stmt for t in stmt.find_all(exp.Table)]
    assert "employee" in tables
```

- [ ] **Step 3: テストを実行して失敗を確認する**

```bash
pytest tests/test_preprocessor.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.sql_parser.preprocessor'`

- [ ] **Step 4: preprocessor.pyを実装する**

`analyzer/sql_parser/preprocessor.py`:
```python
import re

def preprocess_2way_sql(sql: str) -> str:
    # Seasar2の特殊コメント /*...*/ を除去する。
    # /*IF*/, /*END*/, /*BEGIN*/, /*paramName*/ をすべてこの1パスで処理できる。
    # /*paramName*/defaultValue の場合、コメントだけが除去されデフォルト値が残る。
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # 行コメント形式のSeasar2ディレクティブ: --IF, --ELSE, --END
    sql = re.sub(r'--(?:IF|ELSE|END)[^\n]*', '', sql)
    # 連続する空白を整理（改行は保持）
    sql = re.sub(r'[ \t]+', ' ', sql)
    sql = re.sub(r'\n{3,}', '\n\n', sql)
    return sql.strip()
```

- [ ] **Step 5: テストを実行してパスを確認する**

```bash
pytest tests/test_preprocessor.py -v
```

Expected: `6 passed`

- [ ] **Step 6: コミットする**

```bash
git add analyzer/sql_parser/preprocessor.py tests/fixtures/select_employee.sql tests/test_preprocessor.py
git commit -m "feat: add 2-way SQL preprocessor"
```

---

## Task 4: SQL Parser（sqlglot）

**Files:**
- Create: `analyzer/sql_parser/parser.py`
- Create: `tests/fixtures/select_with_join.sql`
- Create: `tests/fixtures/update_employee.sql`
- Create: `tests/test_sql_parser.py`

- [ ] **Step 1: フィクスチャSQLを作成する**

`tests/fixtures/select_with_join.sql`:
```sql
SELECT
  e.employee_id,
  e.name,
  d.department_name
FROM
  employee e
  INNER JOIN department d ON e.department_id = d.department_id
/*BEGIN*/
WHERE
  /*IF dto.name != null*/
  e.name LIKE /*dto.name*/'%test%'
  /*END*/
/*END*/
```

`tests/fixtures/update_employee.sql`:
```sql
UPDATE employee
SET
  name = /*dto.name*/'test',
  department_id = /*dto.departmentId*/1
WHERE
  employee_id = /*dto.employeeId*/1
```

- [ ] **Step 2: テストを書く**

`tests/test_sql_parser.py`:
```python
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
    assert "employee" in tables_in_join or "e" in tables_in_join
    assert "department_id" in (join.left_column, join.right_column)

def test_extract_write_tables_from_update():
    parser = SqlFileParser()
    raw = Path("tests/fixtures/update_employee.sql").read_text()
    result = parser.parse("update_employee.sql", raw)
    assert "employee" in result.write_tables
    assert result.read_tables == []

def test_parse_error_does_not_raise():
    parser = SqlFileParser()
    result = parser.parse("bad.sql", "THIS IS NOT VALID SQL !!!")
    assert isinstance(result, SqlAnalysis)
    assert result.sql_file == "bad.sql"
```

- [ ] **Step 3: テストを実行して失敗を確認する**

```bash
pytest tests/test_sql_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.sql_parser.parser'`

- [ ] **Step 4: parser.pyを実装する**

`analyzer/sql_parser/parser.py`:
```python
import re
import sqlglot
import sqlglot.expressions as exp
from analyzer.models import SqlAnalysis, JoinInfo
from analyzer.sql_parser.preprocessor import preprocess_2way_sql

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
            # UPDATE/DELETE の FROM句にある参照テーブルもread_tablesに追加
            for table in stmt.find_all(exp.Table):
                if table.name and table.name not in result.write_tables and table.name not in result.read_tables:
                    result.read_tables.append(table.name)
            # write_tables に含まれるものはread_tablesから除外
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

    def _fallback_extract(self, sql: str) -> list[str]:
        tables = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        tables += re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
        return list(dict.fromkeys(tables))
```

- [ ] **Step 5: テストを実行してパスを確認する**

```bash
pytest tests/test_sql_parser.py -v
```

Expected: `5 passed`

- [ ] **Step 6: コミットする**

```bash
git add analyzer/sql_parser/parser.py tests/fixtures/select_with_join.sql tests/fixtures/update_employee.sql tests/test_sql_parser.py
git commit -m "feat: add SQL parser using sqlglot"
```

---

## Task 5: Java Scanner

**Files:**
- Create: `analyzer/java_scanner/scanner.py`
- Create: `tests/fixtures/SampleDao.java`
- Create: `tests/test_java_scanner.py`

- [ ] **Step 1: フィクスチャJavaファイルを作成する**

`tests/fixtures/SampleDao.java`:
```java
package com.example.dao;

public class SampleDao {

    private JdbcManager jdbcManager;

    public List<Employee> findAll() {
        return jdbcManager.selectBySql(Employee.class,
            "META-INF/sql/select_employee.sql").getResultList();
    }

    public Employee findById(Integer id) {
        return jdbcManager.selectBySql(Employee.class,
            "META-INF/sql/select_with_join.sql", id).getSingleResult();
    }

    public int update(EmployeeDto dto) {
        return jdbcManager.updateBySql(
            "META-INF/sql/update_employee.sql", dto.getClass()).execute();
    }

    public int insert(Employee entity) {
        return jdbcManager.insertBySql(
            "META-INF/sql/insert_employee.sql", entity.getClass()).execute();
    }
}
```

- [ ] **Step 2: テストを書く**

`tests/test_java_scanner.py`:
```python
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
```

- [ ] **Step 3: テストを実行して失敗を確認する**

```bash
pytest tests/test_java_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.java_scanner.scanner'`

- [ ] **Step 4: scanner.pyを実装する**

`analyzer/java_scanner/scanner.py`:
```python
import re
from pathlib import Path
from analyzer.models import SqlReference

# S2JDBCの操作別メソッドパターン。各タプルは (正規表現, 操作種別) を表す。
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?:selectBySql|getResultList|getSingleResult|iterate)\s*\([^)]*?"([^"]+\.sql)"', re.DOTALL), "SELECT"),
    (re.compile(r'updateBySql\s*\([^)]*?"([^"]+\.sql)"', re.DOTALL), "UPDATE"),
    (re.compile(r'insertBySql\s*\([^)]*?"([^"]+\.sql)"', re.DOTALL), "INSERT"),
    (re.compile(r'deleteBySql\s*\([^)]*?"([^"]+\.sql)"', re.DOTALL), "DELETE"),
]
_GENERIC_SQL = re.compile(r'"([^"]*\.sql)"')
_CLASS_NAME  = re.compile(r'\bclass\s+(\w+)')
_METHOD_NAME = re.compile(r'(?:public|private|protected)\s+\S+\s+(\w+)\s*\(')

class JavaScanner:
    def __init__(self, java_root: str, sql_root: str):
        self.java_root = Path(java_root)
        self.sql_root = Path(sql_root)

    def scan(self) -> list[SqlReference]:
        refs = []
        for java_file in self.java_root.rglob("*.java"):
            refs.extend(self._scan_file(java_file))
        return refs

    def _scan_file(self, java_file: Path) -> list[SqlReference]:
        source = java_file.read_text(encoding="utf-8", errors="ignore")
        class_match = _CLASS_NAME.search(source)
        class_name = class_match.group(1) if class_match else java_file.stem

        results: list[SqlReference] = []
        registered: set[str] = set()

        lines = source.splitlines()
        current_method = "unknown"
        for i, line in enumerate(lines, 1):
            m = _METHOD_NAME.search(line)
            if m:
                current_method = m.group(1)

            for pattern, operation in _PATTERNS:
                for match in pattern.finditer(line):
                    sql_path = match.group(1)
                    if sql_path not in registered:
                        registered.add(sql_path)
                        results.append(SqlReference(
                            sql_file=sql_path,
                            calling_class=class_name,
                            calling_method=current_method,
                            operation=operation,
                            line_number=i,
                            java_file=str(java_file),
                        ))

            # 上記パターンにマッチしなかった .sql パスを UNKNOWN として登録
            for match in _GENERIC_SQL.finditer(line):
                sql_path = match.group(1)
                if sql_path not in registered:
                    registered.add(sql_path)
                    results.append(SqlReference(
                        sql_file=sql_path,
                        calling_class=class_name,
                        calling_method=current_method,
                        operation="UNKNOWN",
                        line_number=i,
                        java_file=str(java_file),
                    ))

        return results
```

- [ ] **Step 5: テストを実行してパスを確認する**

```bash
pytest tests/test_java_scanner.py -v
```

Expected: `5 passed`

- [ ] **Step 6: コミットする**

```bash
git add analyzer/java_scanner/scanner.py tests/fixtures/SampleDao.java tests/test_java_scanner.py
git commit -m "feat: add Java scanner for S2JDBC SQL file references"
```

---

## Task 6: DB Inspector

**Files:**
- Create: `analyzer/db_inspector/inspector.py`
- Create: `tests/test_db_inspector.py`

- [ ] **Step 1: テストを書く（SQLite in-memory を使用）**

`tests/test_db_inspector.py`:
```python
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

def test_row_count(engine):
    inspector = DBInspector(engine)
    assert inspector.get_row_count("employee") == 3
    assert inspector.get_row_count("department") == 2

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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
pytest tests/test_db_inspector.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.db_inspector.inspector'`

- [ ] **Step 3: inspector.pyを実装する**

`analyzer/db_inspector/inspector.py`:
```python
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from analyzer.models import TableInfo, ForeignKey

class DBInspector:
    def __init__(self, engine: Engine):
        self.engine = engine

    def get_row_count(self, table_name: str) -> int:
        try:
            with self.engine.connect() as conn:
                return conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        except SQLAlchemyError:
            return -1

    def get_column_cardinality(self, table_name: str, column_name: str) -> int:
        try:
            with self.engine.connect() as conn:
                return conn.execute(
                    text(f"SELECT COUNT(DISTINCT {column_name}) FROM {table_name}")
                ).scalar()
        except SQLAlchemyError:
            return -1

    def get_foreign_keys(self, table_name: str) -> list[ForeignKey]:
        try:
            insp = inspect(self.engine)
            return [
                ForeignKey(
                    from_table=table_name,
                    from_column=fk["constrained_columns"][0],
                    to_table=fk["referred_table"],
                    to_column=fk["referred_columns"][0],
                    has_fk_constraint=True,
                )
                for fk in insp.get_foreign_keys(table_name)
                if fk.get("constrained_columns") and fk.get("referred_columns")
            ]
        except SQLAlchemyError:
            return []

    def get_table_info(self, table_name: str) -> TableInfo:
        try:
            insp = inspect(self.engine)
            columns = [col["name"] for col in insp.get_columns(table_name)]
        except SQLAlchemyError:
            columns = []
        return TableInfo(
            name=table_name,
            row_count=self.get_row_count(table_name),
            columns=columns,
        )

    def inspect_tables(self, table_names: list[str]) -> dict[str, TableInfo]:
        return {name: self.get_table_info(name) for name in table_names}
```

- [ ] **Step 4: テストを実行してパスを確認する**

```bash
pytest tests/test_db_inspector.py -v
```

Expected: `6 passed`

- [ ] **Step 5: コミットする**

```bash
git add analyzer/db_inspector/inspector.py tests/test_db_inspector.py
git commit -m "feat: add DB inspector with SQLAlchemy"
```

---

## Task 7: Graph Builder

**Files:**
- Create: `analyzer/graph_builder/builder.py`
- Create: `tests/test_graph_builder.py`

- [ ] **Step 1: テストを書く**

`tests/test_graph_builder.py`:
```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
pytest tests/test_graph_builder.py -v
```

Expected: `ModuleNotFoundError: No module named 'analyzer.graph_builder.builder'`

- [ ] **Step 3: builder.pyを実装する**

`analyzer/graph_builder/builder.py`:
```python
from analyzer.models import AnalysisResult

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

        sql_counts: dict[str, int] = {}
        for analysis in result.sql_analyses:
            for t in analysis.read_tables + analysis.write_tables:
                sql_counts[t] = sql_counts.get(t, 0) + 1

        # テーブルノード
        for name, info in result.table_info.items():
            nodes.append({"data": {
                "id": f"table:{name}",
                "label": name,
                "type": "table",
                "row_count": info.row_count,
                "sql_file_count": sql_counts.get(name, 0),
                "columns": info.columns,
            }})

        # SQLファイルノード
        ref_map = {r.sql_file: r for r in result.sql_references}
        for analysis in result.sql_analyses:
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

        # JOINエッジ（テーブル間、重複なし）
        seen_joins: set[frozenset] = set()
        for analysis in result.sql_analyses:
            for join in analysis.joins:
                lt, lc = join.left_table, join.left_column
                rt, rc = join.right_table, join.right_column
                key = frozenset([(lt, lc), (rt, rc)])
                if key in seen_joins:
                    continue
                seen_joins.add(key)
                has_fk = (lt, lc, rt, rc) in fk_pairs or (rt, rc, lt, lc) in fk_pairs
                edges.append({"data": {
                    "id": eid(),
                    "source": f"table:{lt}",
                    "target": f"table:{rt}",
                    "type": "join",
                    "left_column": lc,
                    "right_column": rc,
                    "has_fk": has_fk,
                }})

        # READ/WRITEエッジ（SQLファイル → テーブル）
        for analysis in result.sql_analyses:
            sid = f"sql:{analysis.sql_file}"
            for t in analysis.read_tables:
                edges.append({"data": {"id": eid(), "source": sid, "target": f"table:{t}", "type": "read"}})
            for t in analysis.write_tables:
                edges.append({"data": {"id": eid(), "source": sid, "target": f"table:{t}", "type": "write"}})

        return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: テストを実行してパスを確認する**

```bash
pytest tests/test_graph_builder.py -v
```

Expected: `6 passed`

- [ ] **Step 5: コミットする**

```bash
git add analyzer/graph_builder/builder.py tests/test_graph_builder.py
git commit -m "feat: add graph builder for Cytoscape.js"
```

---

## Task 8: FastAPI アプリ

**Files:**
- Create: `web/app.py`
- Create: `web/routes.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: テストを書く**

`tests/test_api.py`:
```python
import time
import pytest
from fastapi.testclient import TestClient
from web.app import create_app

CONFIG = {
    "source": {"java_root": "tests/fixtures", "sql_root": "tests/fixtures"},
    "database": {"url": "sqlite:///:memory:"},
    "analysis": {"timeout_seconds": 30, "cardinality_sample": 1000},
}

@pytest.fixture
def client():
    return TestClient(create_app(CONFIG))

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_analyze_returns_job_id(client):
    resp = client.post("/api/analyze", json={"config": CONFIG})
    assert resp.status_code == 200
    assert "job_id" in resp.json()

def test_status_returns_valid_state(client):
    job_id = client.post("/api/analyze", json={"config": CONFIG}).json()["job_id"]
    resp = client.get(f"/api/status/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] in ("running", "completed", "error")

def test_graph_returns_nodes_and_edges(client):
    job_id = client.post("/api/analyze", json={"config": CONFIG}).json()["job_id"]
    for _ in range(20):
        if client.get(f"/api/status/{job_id}").json()["state"] == "completed":
            break
        time.sleep(0.3)
    resp = client.get(f"/api/graph/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data

def test_status_404_for_unknown_job(client):
    assert client.get("/api/status/no-such-job").status_code == 404
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'web.app'`

- [ ] **Step 3: web/app.pyを実装する**

`web/app.py`:
```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

def create_app(config: dict) -> FastAPI:
    app = FastAPI(title="sqlan")
    app.state.jobs: dict = {}
    app.state.config = config

    from web.routes import create_router
    app.include_router(create_router(), prefix="/api")

    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
```

- [ ] **Step 4: web/routes.pyを実装する**

`web/routes.py`:
```python
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import create_engine
from analyzer.java_scanner.scanner import JavaScanner
from analyzer.sql_parser.parser import SqlFileParser
from analyzer.db_inspector.inspector import DBInspector
from analyzer.graph_builder.builder import GraphBuilder
from analyzer.models import AnalysisResult

def _run_analysis(job_id: str, config: dict, jobs: dict) -> None:
    jobs[job_id] = {"state": "running", "progress": 0}
    try:
        src = config.get("source", {})
        db_url = config.get("database", {}).get("url", "")
        result = AnalysisResult()

        # 1. Java Scanner
        scanner = JavaScanner(java_root=src.get("java_root", "."), sql_root=src.get("sql_root", "."))
        result.sql_references = scanner.scan()
        jobs[job_id]["progress"] = 25

        # 2. SQL Parser
        parser = SqlFileParser()
        sql_root = Path(src.get("sql_root", "."))
        for ref in result.sql_references:
            for candidate in [sql_root / ref.sql_file, Path(ref.sql_file)]:
                if candidate.exists():
                    raw = candidate.read_text(encoding="utf-8", errors="ignore")
                    result.sql_analyses.append(parser.parse(ref.sql_file, raw))
                    break
        jobs[job_id]["progress"] = 50

        # 3. DB Inspector
        if db_url:
            engine = create_engine(db_url)
            inspector = DBInspector(engine)
            all_tables = {t for a in result.sql_analyses for t in a.read_tables + a.write_tables}
            result.table_info = inspector.inspect_tables(list(all_tables))
            for table in all_tables:
                result.foreign_keys.extend(inspector.get_foreign_keys(table))
        jobs[job_id]["progress"] = 75

        # 4. Graph Builder
        jobs[job_id]["graph"] = GraphBuilder().build(result)
        jobs[job_id]["state"] = "completed"
        jobs[job_id]["progress"] = 100
    except Exception as e:
        jobs[job_id]["state"] = "error"
        jobs[job_id]["error"] = str(e)

def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok"}

    @router.post("/analyze")
    def analyze(payload: dict, background_tasks: BackgroundTasks, request: Request):
        config = payload.get("config", request.app.state.config)
        job_id = str(uuid.uuid4())
        request.app.state.jobs[job_id] = {"state": "running", "progress": 0}
        background_tasks.add_task(_run_analysis, job_id, config, request.app.state.jobs)
        return {"job_id": job_id}

    @router.get("/status/{job_id}")
    def get_status(job_id: str, request: Request):
        job = request.app.state.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"state": job["state"], "progress": job.get("progress", 0)}

    @router.get("/graph/{job_id}")
    def get_graph(job_id: str, request: Request):
        job = request.app.state.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["state"] != "completed":
            raise HTTPException(status_code=202, detail="Analysis not yet complete")
        return job["graph"]

    @router.get("/node/{node_id:path}")
    def get_node(node_id: str, request: Request):
        for job in reversed(list(request.app.state.jobs.values())):
            if job.get("state") == "completed":
                for node in job.get("graph", {}).get("nodes", []):
                    if node["data"]["id"] == node_id:
                        return node["data"]
        raise HTTPException(status_code=404, detail="Node not found")

    return router
```

- [ ] **Step 5: テストを実行してパスを確認する**

```bash
pytest tests/test_api.py -v
```

Expected: `5 passed`

- [ ] **Step 6: コミットする**

```bash
git add web/app.py web/routes.py tests/test_api.py
git commit -m "feat: add FastAPI app with analysis pipeline"
```

---

## Task 9: フロントエンド（index.html）

**Files:**
- Create: `web/frontend/index.html`

- [ ] **Step 1: index.htmlを作成する**

`web/frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>sqlan — SQL依存関係アナライザー</title>
  <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; display: flex; flex-direction: column; height: 100vh; background: #1a1a2e; color: #e0e0e0; }
    #header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: #16213e; border-bottom: 1px solid #0f3460; }
    #header h1 { font-size: 1.1rem; color: #e94560; }
    #search { padding: 6px 10px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; width: 220px; }
    #filter-op { padding: 6px 8px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; }
    #layout-sel { padding: 6px 8px; border-radius: 4px; border: 1px solid #0f3460; background: #0f3460; color: #e0e0e0; }
    #btn-analyze { padding: 6px 16px; border-radius: 4px; border: none; background: #e94560; color: #fff; cursor: pointer; margin-left: auto; }
    #btn-analyze:disabled { opacity: 0.5; cursor: default; }
    #progress-bar { height: 3px; background: #e94560; width: 0%; transition: width 0.3s; }
    #main { display: flex; flex: 1; overflow: hidden; }
    #cy { flex: 1; }
    #detail { width: 280px; background: #16213e; border-left: 1px solid #0f3460; padding: 16px; overflow-y: auto; }
    #detail h2 { font-size: 0.9rem; color: #e94560; margin-bottom: 12px; }
    .detail-row { margin-bottom: 8px; font-size: 0.82rem; }
    .detail-label { color: #888; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 2px; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; }
    .badge-select { background: #1a6b4a; } .badge-update { background: #6b3a1a; } .badge-insert { background: #1a3a6b; } .badge-unknown { background: #444; }
    .badge-table { background: #2d1b6b; } .badge-fk { background: #1a5c6b; }
  </style>
</head>
<body>
  <div id="header">
    <h1>sqlan</h1>
    <input id="search" type="text" placeholder="テーブル名 / SQLファイル名で絞り込み">
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
    <button id="btn-analyze">解析実行</button>
  </div>
  <div id="progress-bar"></div>
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

    const $ = id => document.getElementById(id);

    function initCytoscape(elements) {
      if (cy) cy.destroy();
      cy = cytoscape({
        container: $('cy'),
        elements,
        style: [
          { selector: 'node[type="table"]', style: { 'background-color': '#4a2d8b', 'label': 'data(label)', 'color': '#fff', 'font-size': '11px', 'text-valign': 'center', 'width': '60px', 'height': '60px', 'shape': 'ellipse' } },
          { selector: 'node[type="sql_file"]', style: { 'background-color': '#2d6b4a', 'label': 'data(label)', 'color': '#fff', 'font-size': '9px', 'text-valign': 'center', 'shape': 'rectangle', 'width': '80px', 'height': '30px' } },
          { selector: 'edge[type="join"]', style: { 'line-color': '#e94560', 'width': 2, 'target-arrow-shape': 'none', 'curve-style': 'bezier' } },
          { selector: 'edge[type="join"][has_fk]', style: { 'line-style': 'solid' } },
          { selector: 'edge[type="read"]', style: { 'line-color': '#4a8b6b', 'width': 1, 'target-arrow-shape': 'triangle', 'target-arrow-color': '#4a8b6b', 'curve-style': 'bezier' } },
          { selector: 'edge[type="write"]', style: { 'line-color': '#e9a020', 'width': 1, 'target-arrow-shape': 'triangle', 'target-arrow-color': '#e9a020', 'curve-style': 'bezier' } },
          { selector: ':selected', style: { 'border-width': 3, 'border-color': '#fff' } },
        ],
        layout: { name: $('layout-sel').value, padding: 40 },
      });
      cy.on('tap', 'node', e => showDetail(e.target.data()));
      cy.on('tap', 'edge', e => showEdgeDetail(e.target.data()));
    }

    function showDetail(data) {
      const op = data.operation || '';
      const badgeClass = { SELECT: 'badge-select', UPDATE: 'badge-update', INSERT: 'badge-insert' }[op] || 'badge-unknown';
      let html = '';
      if (data.type === 'table') {
        html = `
          <div class="detail-row"><div class="detail-label">種別</div><span class="badge badge-table">テーブル</span></div>
          <div class="detail-row"><div class="detail-label">名前</div>${data.label}</div>
          <div class="detail-row"><div class="detail-label">行数</div>${data.row_count >= 0 ? data.row_count.toLocaleString() : '不明'}</div>
          <div class="detail-row"><div class="detail-label">参照SQLファイル数</div>${data.sql_file_count}</div>
          <div class="detail-row"><div class="detail-label">カラム</div>${(data.columns || []).join(', ') || '不明'}</div>`;
      } else {
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
      let html = `
        <div class="detail-row"><div class="detail-label">エッジ種別</div>${data.type}</div>`;
      if (data.type === 'join') {
        html += `
          <div class="detail-row"><div class="detail-label">左カラム</div>${data.left_column}</div>
          <div class="detail-row"><div class="detail-label">右カラム</div>${data.right_column}</div>
          <div class="detail-row"><div class="detail-label">FK制約</div>${data.has_fk ? '<span class="badge badge-fk">あり</span>' : 'なし'}</div>`;
      }
      $('detail-body').innerHTML = html;
    }

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
        e.style('display', src.style('display') !== 'none' && tgt.style('display') !== 'none' ? 'element' : 'none');
      });
    }

    $('search').addEventListener('input', applyFilter);
    $('filter-op').addEventListener('change', applyFilter);
    $('layout-sel').addEventListener('change', () => { if (cy) cy.layout({ name: $('layout-sel').value, padding: 40 }).run(); });

    $('btn-analyze').addEventListener('click', async () => {
      $('btn-analyze').disabled = true;
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
          initCytoscape(graph);
          $('btn-analyze').disabled = false;
          $('progress-bar').style.width = '100%';
        } else if (s.state === 'error') {
          clearInterval(pollTimer);
          alert('解析に失敗しました。サーバーログを確認してください。');
          $('btn-analyze').disabled = false;
        }
      }, 500);
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: サーバーを起動してブラウザで動作確認する**

```bash
python3 main.py config.toml
```

`http://localhost:8000` をブラウザで開き、以下を確認する：
- ページが表示される
- 「解析実行」ボタンをクリックするとプログレスバーが動く
- グラフが表示される（テーブルノード・SQLファイルノード・エッジ）
- ノードをクリックすると詳細パネルに情報が表示される
- 検索バーで絞り込みができる

- [ ] **Step 3: コミットする**

```bash
git add web/frontend/index.html
git commit -m "feat: add interactive Cytoscape.js frontend"
```

---

## Task 10: 全テストの確認と最終コミット

- [ ] **Step 1: 全テストをまとめて実行する**

```bash
pytest tests/ -v
```

Expected: 全テストが `passed`（`test_api.py` の `test_graph_returns_nodes_and_edges` は数秒かかる場合がある）

- [ ] **Step 2: テスト失敗があれば修正してから再実行する**

テストが失敗した場合は該当タスクの実装を確認し、修正してから再実行する。
全テストが `passed` になるまでこのステップを繰り返す。

- [ ] **Step 3: 最終コミットする**

```bash
git add -A
git commit -m "chore: final integration check — all tests passing"
```
