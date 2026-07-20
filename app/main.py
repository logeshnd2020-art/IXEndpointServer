from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.device import router as device_router
from app.exceptions.handlers import register_exception_handlers
from app.api.application import router as application_router
from app.api.session import router as session_router
from app.api.idle import router as idle_router
from app.api.activity import router as activity_router
from app.api.dashboard import router as dashboard_router

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
app.include_router(application_router)
app.include_router(session_router)
app.include_router(idle_router)
app.include_router(activity_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {
        "product": "IX Endpoint Services",
        "status": "Running",
        "version": "1.0.0",
    }
