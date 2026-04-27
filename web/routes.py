import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import create_engine
from analyzer.java_scanner.scanner import JavaScanner
from analyzer.sql_parser.parser import SqlFileParser
from analyzer.db_inspector.inspector import DBInspector
from analyzer.graph_builder.builder import GraphBuilder
from analyzer.models import AnalysisResult

logger = logging.getLogger(__name__)

def _run_analysis(job_id: str, config: dict, jobs: dict) -> None:
    try:
        src = config.get("source", {})
        db_url = config.get("database", {}).get("url", "")
        result = AnalysisResult()

        # 1. Java Scanner
        java_root = src.get("java_root", ".")
        sql_root_str = src.get("sql_root", ".")
        logger.info("[1/4] Java Scanner 開始: java_root=%s", java_root)
        scanner = JavaScanner(java_root=java_root, sql_root=sql_root_str)
        result.sql_references = scanner.scan()
        logger.info("[1/4] Java Scanner 完了: %d件のSQL参照を検出", len(result.sql_references))
        for ref in result.sql_references:
            logger.debug("  -> %s [%s] %s#%s", ref.sql_file, ref.operation, ref.calling_class, ref.calling_method)
        jobs[job_id]["progress"] = 25

        # 2. SQL Parser
        logger.info("[2/4] SQL Parser 開始: sql_root=%s", sql_root_str)
        parser = SqlFileParser()
        sql_root = Path(sql_root_str)
        not_found = []
        for ref in result.sql_references:
            resolved = None
            for candidate in [sql_root / ref.sql_file, Path(ref.sql_file)]:
                if candidate.exists():
                    resolved = candidate
                    break
            if resolved:
                raw = resolved.read_text(encoding="utf-8", errors="ignore")
                analysis = parser.parse(ref.sql_file, raw)
                result.sql_analyses.append(analysis)
                logger.debug("  解析: %s → read=%s write=%s joins=%d%s",
                    ref.sql_file, analysis.read_tables, analysis.write_tables,
                    len(analysis.joins),
                    f" [警告: {analysis.parse_error}]" if analysis.parse_error else "")
            else:
                not_found.append(ref.sql_file)
        logger.info("[2/4] SQL Parser 完了: %d件解析, %d件ファイル未発見",
            len(result.sql_analyses), len(not_found))
        if not_found:
            for f in not_found:
                logger.warning("  SQLファイルが見つかりません: %s", f)
        jobs[job_id]["warnings"] = [f"SQLファイルが見つかりません: {f}" for f in not_found]
        jobs[job_id]["progress"] = 50

        # 3. DB Inspector
        if db_url:
            import re as _re
            masked = _re.sub(r'://([^:@]+):([^@]+)@', r'://\1:***@', db_url)
            logger.info("[3/4] DB Inspector 開始: %s", masked)
            engine = create_engine(db_url)
            inspector = DBInspector(engine)
            all_tables = {t for a in result.sql_analyses for t in a.read_tables + a.write_tables}
            logger.info("[3/4] 対象テーブル %d件: %s", len(all_tables), sorted(all_tables))
            result.table_info = inspector.inspect_tables(list(all_tables))
            for name, info in result.table_info.items():
                logger.debug("  テーブル %s: %d行, カラム=%s", name, info.row_count, info.columns)
            for table in all_tables:
                fks = inspector.get_foreign_keys(table)
                result.foreign_keys.extend(fks)
                for fk in fks:
                    logger.debug("  FK: %s.%s -> %s.%s", fk.from_table, fk.from_column, fk.to_table, fk.to_column)
            logger.info("[3/4] DB Inspector 完了: FK %d件", len(result.foreign_keys))
        else:
            logger.info("[3/4] DB Inspector スキップ (url未設定)")
        jobs[job_id]["progress"] = 75

        # 4. Graph Builder
        logger.info("[4/4] Graph Builder 開始")
        graph = GraphBuilder().build(result)
        jobs[job_id]["graph"] = graph
        jobs[job_id]["state"] = "completed"
        jobs[job_id]["progress"] = 100
        logger.info("[4/4] Graph Builder 完了: ノード %d件, エッジ %d件",
            len(graph["nodes"]), len(graph["edges"]))
        logger.info("解析完了 (job=%s)", job_id)
    except Exception as e:
        jobs[job_id]["state"] = "error"
        jobs[job_id]["error"] = str(e)
        logger.exception("Analysis failed for job %s", job_id)

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
        resp = {"state": job["state"], "progress": job.get("progress", 0)}
        if job["state"] == "error":
            resp["error"] = job.get("error", "Unknown error")
        if job.get("warnings"):
            resp["warnings"] = job["warnings"]
        return resp

    @router.get("/graph/{job_id}")
    def get_graph(job_id: str, request: Request):
        job = request.app.state.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["state"] != "completed":
            raise HTTPException(status_code=409, detail="Analysis not yet complete")
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
