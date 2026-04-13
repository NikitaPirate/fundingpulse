import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fundingpulse.api.api.v0.router import router as v0_router
from fundingpulse.api.db import engine
from fundingpulse.api.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application lifecycle."""
    # Startup: engine already initialized in db.py

    yield

    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(title="Funding Data API", lifespan=lifespan)

# CORS middleware
app.add_middleware(CORSMiddleware, **settings.cors.to_middleware_kwargs())  # type: ignore[arg-type]

app.include_router(v0_router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions (5xx) - NO DETAILS for security."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": {}}
        },
    )


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
