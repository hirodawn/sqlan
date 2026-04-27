import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

def create_app(config: dict) -> FastAPI:
    app = FastAPI(title="sqlan")
    app.state.jobs: dict = {}
    app.state.config = config

    from web.routes import create_router, load_cache_job
    cached = load_cache_job()
    if cached:
        app.state.jobs["cached"] = cached
        logger.info("キャッシュジョブを登録しました (cached_at=%s)", cached.get("cached_at"))

    app.include_router(create_router(), prefix="/api")

    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
