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

        # SQLファイルノード（同一ファイルが複数解析結果に現れても1ノードのみ生成）
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

        # READ/WRITEエッジ（SQLファイル → テーブル、重複なし）
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
