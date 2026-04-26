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

        # Scan entire source with each pattern (handles multi-line calls)
        for pattern, operation in _PATTERNS:
            for match in pattern.finditer(source):
                sql_path = match.group(1)
                if sql_path not in registered:
                    registered.add(sql_path)
                    # Determine line number from match position
                    line_number = source[:match.start()].count('\n') + 1
                    # Determine calling method by scanning lines up to match
                    calling_method = self._find_method_at(source, match.start())
                    results.append(SqlReference(
                        sql_file=sql_path,
                        calling_class=class_name,
                        calling_method=calling_method,
                        operation=operation,
                        line_number=line_number,
                        java_file=str(java_file),
                    ))

        # Register any remaining .sql paths not matched by specific patterns as UNKNOWN
        for match in _GENERIC_SQL.finditer(source):
            sql_path = match.group(1)
            if sql_path not in registered:
                registered.add(sql_path)
                line_number = source[:match.start()].count('\n') + 1
                calling_method = self._find_method_at(source, match.start())
                results.append(SqlReference(
                    sql_file=sql_path,
                    calling_class=class_name,
                    calling_method=calling_method,
                    operation="UNKNOWN",
                    line_number=line_number,
                    java_file=str(java_file),
                ))

        return results

    def _find_method_at(self, source: str, pos: int) -> str:
        """Find the most recent method declaration before pos."""
        prefix = source[:pos]
        method = "unknown"
        for m in _METHOD_NAME.finditer(prefix):
            method = m.group(1)
        return method
