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

    def _fallback_extract(self, sql: str) -> list[str]:
        tables = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        tables += re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
        return list(dict.fromkeys(tables))
