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

        # S2JDBC SQL files contain a single statement per file; scanning full raw_sql is safe.
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
                # Unqualified column (no table prefix) is assumed to belong to the target table.
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
