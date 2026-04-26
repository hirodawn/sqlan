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
