from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.device import DeviceNotFound, DeviceAlreadyExists


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

    @app.exception_handler(DeviceAlreadyExists)
    async def device_already_exists(
        request: Request,
        exc: DeviceAlreadyExists
    ):
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": str(exc) or "Duplicate device"
            },
        )
