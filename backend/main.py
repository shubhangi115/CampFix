import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mysql.connector import Error

from . import auth
from .routes import admin, complaints, dashboard


@asynccontextmanager
async def lifespan(_app):
    auth.jwt_secret()
    yield


app = FastAPI(
    title="CampFix API",
    description="Campus complaint submission, tracking, and resolution.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc):
    # Exclude raw request values, which can include passwords.
    errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Error)
async def database_error(_request, exc):
    logging.getLogger(__name__).error("MySQL operation failed (error %s)", exc.errno)
    return JSONResponse(status_code=503, content={"detail": "Database operation failed. Try again."})


app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
