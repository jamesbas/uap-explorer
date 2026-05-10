"""FastAPI entry point for UAP Explorer (Phase 1 + 2)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.admin_routes import router as admin_router
from .api.phase3_routes import router as phase3_router
from .api.phase4_routes import router as phase4_router
from .api.routes import router
from .config import settings
from .services.store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="UAP Explorer API",
    description="Source-grounded research portal for government-released UAP records.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(admin_router)
app.include_router(phase4_router)
app.include_router(phase3_router)
