from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.device import DeviceNotFound


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(DeviceNotFound)
    async def device_not_found(
        request: Request,
        exc: DeviceNotFound
    ):
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "Device not found"
            },
        )
