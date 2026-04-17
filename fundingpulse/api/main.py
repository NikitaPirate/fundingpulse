import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fundingpulse.api.api.v0.router import router as v0_router
from fundingpulse.api.db import dispose_app_db, install_db_resources
from fundingpulse.api.settings import get_cors_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_db_resources(app)
    yield
    await dispose_app_db(app)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions (5xx) - NO DETAILS for security."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": {}}
        },
    )


def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(title="Funding Data API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, **get_cors_settings().to_middleware_kwargs())  # type: ignore[arg-type]
    app.include_router(v0_router)
    app.add_exception_handler(Exception, generic_exception_handler)
    app.get("/health")(healthcheck)
    return app


app = create_app()
