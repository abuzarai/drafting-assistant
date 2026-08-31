"""FastAPI app entrypoint."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import require_internal_key
from config import settings
from db.connection import close_pool, init_pool
from routes.draft import router as draft_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Insafdaar Drafting Service",
    lifespan=lifespan,
    docs_url=None if settings.env == "production" else "/docs",
    redoc_url=None if settings.env == "production" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(draft_router, dependencies=[Depends(require_internal_key)])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.env, "service": "drafting-assistant"}
