from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import health_router, research_router, documents_router, auth_router
from app.core import logger, settings
import os

# Create FastAPI app
app = FastAPI(
    title="Irium MVP",
    description="Multi-Agent FinTech Research & Document Analysis System",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.observability import metrics, set_current_trace_id
from app.api.routes.observability import router as observability_router

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Correlation-ID") or f"tr-{uuid.uuid4().hex[:12]}"
        set_current_trace_id(trace_id)
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))
            metrics.record_request(request.method, request.url.path, response.status_code, duration_ms)
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_error("http", e.__class__.__name__)
            metrics.record_request(request.method, request.url.path, 500, duration_ms)
            raise

# Observability middleware
app.add_middleware(ObservabilityMiddleware)

from app.api.routes.cache import router as cache_router
from app.api.routes.memory import router as memory_router

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(observability_router, tags=["observability"])
app.include_router(cache_router, tags=["cache"])
app.include_router(memory_router, tags=["memory"])
app.include_router(auth_router, tags=["auth"])
app.include_router(research_router, tags=["research"])
app.include_router(documents_router, tags=["documents"])

from pathlib import Path
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"Static files mounted from: {FRONTEND_DIR}")

    NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}

    @app.get("/", include_in_schema=False)
    @app.get("/landing", include_in_schema=False)
    @app.get("/landing.html", include_in_schema=False)
    async def serve_landing():
        landing_file = FRONTEND_DIR / "landing.html"
        if landing_file.exists():
            return FileResponse(landing_file, headers=NO_CACHE_HEADERS)
        return FileResponse(FRONTEND_DIR / "index.html", headers=NO_CACHE_HEADERS)

    @app.get("/app", include_in_schema=False)
    @app.get("/chat", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    async def serve_chat_app():
        return FileResponse(FRONTEND_DIR / "index.html", headers=NO_CACHE_HEADERS)

    @app.get("/{file_path:path}", include_in_schema=False)
    async def serve_frontend_file(file_path: str):
        target = FRONTEND_DIR / file_path
        if target.is_file():
            return FileResponse(target, headers=NO_CACHE_HEADERS)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
else:
    logger.warning(f"Frontend directory not found at: {FRONTEND_DIR}")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting Irium MVP...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    
    # Database disabled - using localStorage only
    logger.info("Database: Disabled (using localStorage)")
    
    logger.info("Irium MVP started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Irium MVP...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
