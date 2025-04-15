import logging
import uvicorn
from fastapi import FastAPI
from rtsapi.global_exception_handling import catch_exceptions_middleware
from rtsapi.database import engine, models
from rtsapi.routers import root, rts, measurement, rts_job, device, target

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Robotic Total Station API",
    version="0.1.0",
    summary="This API allows you to interact with multiple Robotic Total Station (RTS) and its measurements.",
)
app.include_router(measurement.router)
app.include_router(rts_job.router)
app.include_router(target.router)
app.include_router(device.router)
app.include_router(root.router)
app.include_router(rts.router)

app.middleware("http")(catch_exceptions_middleware)


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
