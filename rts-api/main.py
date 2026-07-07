import logging

import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from rtsapi.app_state import AppState
from rtsapi.database import engine, models
from rtsapi.global_exception_handling import catch_exceptions_middleware
from rtsapi.routers import device, measurement, root, rts, rts_job, session, target, external_sensor, synchronizer

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(message)s")

models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.app_state = AppState()
    yield

app = FastAPI(
    title="Robotic Total Station API",
    version="1.0.0",
    summary="This API allows you to interact with multiple Robotic Total Station (RTS) and its measurements.",
    lifespan=lifespan
)
app.include_router(measurement.router)
app.include_router(rts_job.router)
app.include_router(target.router)
app.include_router(device.router)
app.include_router(root.router)
app.include_router(rts.router)
app.include_router(session.router)
app.include_router(external_sensor.router)
app.include_router(synchronizer.router)

app.middleware("http")(catch_exceptions_middleware)


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
