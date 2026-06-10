from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routes import router
from app.seed import seed_demo_data


settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_demo_data:
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TeamSync API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": str(exc)}})

    app.include_router(router)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def demo_console() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        fallback = STATIC_DIR / "fallback.html"
        return FileResponse(fallback)

    return app


app = create_app()
