from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.database import get_db
from app.services.server_lifecycle_service import record_shutdown, record_startup

from app.api.health import router as health_router
from app.api.device import router as device_router
from app.api.agent import router as agent_router
from app.exceptions.handlers import register_exception_handlers
from app.api.application import router as application_router
from app.api.session import router as session_router
from app.api.idle import router as idle_router
from app.api.activity import router as activity_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router
from app.api.roles import router as roles_router
from app.api.enrollment_key import router as enrollment_key_router
from app.api.device_page import router as device_page_router

import app.models


def _drive_lifecycle_db_write(app: FastAPI, writer) -> None:
    """
    Resolve one DB session/generator for lifecycle recording the exact
    same way FastAPI resolves `Depends(get_db)` for a request --
    through `app.dependency_overrides` -- rather than calling
    SessionLocal() directly.

    This matters specifically for tests: `lifespan` is not a per-request
    handler, so it never goes through FastAPI's normal dependency
    injection, and a naive `SessionLocal()` call here would always hit
    the real production database (bound at import time via
    app.core.database.engine/SessionLocal), even when a test has
    overridden `get_db` to use an isolated in-memory database (see
    tests/conftest.py's `client` fixture, which triggers this very
    lifespan on TestClient entry/exit). Resolving through
    `app.dependency_overrides` means a test's override is honored here
    too, so lifecycle-event writes during tests land in that same
    in-memory database and never touch the real one. Outside of tests,
    where no override is registered, this falls back to the real
    `get_db` unchanged.
    """
    override = app.dependency_overrides.get(get_db, get_db)
    gen = override()
    db = next(gen)
    try:
        writer(db)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 3, Item 2 -- durable, best-effort record of this process's
    # own start/stop. record_startup()/record_shutdown() never raise
    # (see server_lifecycle_service._safe_record) so a DB hiccup at
    # exactly this moment can never prevent the app from actually
    # starting or shutting down -- it only means that boundary is
    # missing evidence, which the outage-evidence derivation already
    # treats correctly (absence of a row is never read as "available").
    _drive_lifecycle_db_write(app, record_startup)

    yield

    _drive_lifecycle_db_write(app, record_shutdown)


app = FastAPI(
    title="IX Endpoint Server",
    version="1.0.0",
    lifespan=lifespan,
)

# Register global exception handlers
register_exception_handlers(app)

# Register API routers
app.include_router(health_router)
app.include_router(device_router)
app.include_router(agent_router)
app.include_router(application_router)
app.include_router(session_router)
app.include_router(idle_router)
app.include_router(activity_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(enrollment_key_router)
app.include_router(device_page_router)

# Serve local static assets (CSS/JS) -- no external CDN dependency for
# anything besides Bootstrap, which was already the existing convention.
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    # Static shell -- unauthenticated by design. All real data is fetched
    # client-side from role-checked, bearer-token-protected JSON APIs; the
    # page itself redirects to /login if no valid token is present.
    return FileResponse("templates/index.html")


@app.get("/login")
def login_page():
    return FileResponse("templates/login.html")
