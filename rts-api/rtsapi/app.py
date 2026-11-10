"""FastAPI application.

Endpoints that touch the database are plain `def` functions: FastAPI runs them in a thread
pool, so a slow query can never block the event loop (which serves the websockets).
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rtsapi import __version__
from rtsapi.config import Settings, settings as default_settings
from rtsapi.core import Core
from rtsapi.errors import ApiException

logger = logging.getLogger(__name__)


class ReceiveTimeMiddleware:
    """Stores the earliest receive time of a request (used for the worker clock comparison)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope.setdefault("state", {})["received_at"] = time.time()
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        core = Core(settings)
        app.state.core = core
        await core.start()
        logger.info("RTS API %s ready (database %s)", __version__, settings.db_path)
        try:
            yield
        finally:
            await core.stop()

    app = FastAPI(
        title="RTS Network API",
        version=__version__,
        summary="Control a network of robotic total stations and collect their measurements.",
        lifespan=lifespan,
    )

    @app.exception_handler(ApiException)
    async def api_exception_handler(request: Request, exc: ApiException):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content={"message": details or "Invalid request", "errors": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error in %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"message": f"Internal error: {exc!r}"})

    from rtsapi.routers import devices, events, external, jobs, rts, sessions, status, sync, system, worker

    for module in (system, sessions, devices, rts, jobs, status, events, worker, external, sync):
        app.include_router(module.router)
    app.add_middleware(ReceiveTimeMiddleware)
    return app
