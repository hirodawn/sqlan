from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

def create_app(config: dict) -> FastAPI:
    app = FastAPI(title="sqlan")
    app.state.jobs: dict = {}
    app.state.config = config

    from web.routes import create_router
    app.include_router(create_router(), prefix="/api")

    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
