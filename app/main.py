from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(
    title="IX Endpoint Server",
    version="1.0.0",
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
