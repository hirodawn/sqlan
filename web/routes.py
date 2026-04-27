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
            import re as _re
            masked = _re.sub(r'://([^:@]+):([^@]+)@', r'://\1:***@', db_url)
            logger.info("Connecting to DB: %s", masked)
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
