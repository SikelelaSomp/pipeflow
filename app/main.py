from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="PipeFlow",
    description=(
        "Middleware broker between NSFAS and South Africa's public universities. "
        "Handles bidirectional data flow, validation, routing, and audit trail "
        "for student registration, results, and funding decisions."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "message": "An unexpected error occurred"},
    )