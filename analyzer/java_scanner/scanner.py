import bisect
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
# 1ファイル1クラスを前提とする（ネストクラス・複数クラスは最初のクラスに帰属）
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
        try:
            source = java_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        class_match = _CLASS_NAME.search(source)
        class_name = class_match.group(1) if class_match else java_file.stem

        # 全メソッド宣言を一度だけ収集し、bisect で O(log N) 検索を実現する
        method_positions: list[tuple[int, str]] = []
        for m in _METHOD_NAME.finditer(source):
            method_positions.append((m.start(), m.group(1)))

        def method_at(pos: int) -> str:
            idx = bisect.bisect_right(method_positions, (pos,)) - 1
            if idx < 0:
                return "unknown"
            return method_positions[idx][1]

        results: list[SqlReference] = []
        # registered: Javaソース内の文字列リテラルをそのままキーとして使用する。
        # パス表記の揺れ（バックスラッシュ混在等）は対象プロジェクトでは想定しない。
        registered: set[str] = set()

        # Scan entire source with each pattern (handles multi-line calls)
        for pattern, operation in _PATTERNS:
            for match in pattern.finditer(source):
                sql_path = match.group(1)
                if sql_path not in registered:
                    registered.add(sql_path)
                    # Determine line number from match position
                    line_number = source[:match.start()].count('\n') + 1
                    calling_method = method_at(match.start())
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
                calling_method = method_at(match.start())
                results.append(SqlReference(
                    sql_file=sql_path,
                    calling_class=class_name,
                    calling_method=calling_method,
                    operation="UNKNOWN",
                    line_number=line_number,
                    java_file=str(java_file),
                ))

        return results
