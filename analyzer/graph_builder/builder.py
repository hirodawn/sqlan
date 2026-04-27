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
                    f"{cu.source_table.lower()}.{cu.source_column.lower()}"
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
                    src_col = cu.source_column.lower()
                    tgt_col = cu.target_column.lower()
                    seen_copy[key] = {
                        "source": f"table:{cu.source_table.lower()}",
                        "target": f"table:{cu.target_table.lower()}",
                        "type": "column_copy",
                        "source_column": src_col,
                        "target_column": tgt_col,
                        "label": f"{src_col} → {tgt_col}",
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
