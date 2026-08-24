"""
The boundary between the domain and HTTP.

Services report broken rules with domain exceptions that carry no status
codes. This module is the one place that decides what each of them means
over HTTP, which keeps controllers free of error-handling boilerplate and
guarantees a consistent response shape.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    ConflictError,
    DomainError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    PermissionDeniedError: 403,
    ConflictError: 409,
    InvalidRequestError: 400,
}

DEFAULT_STATUS = 400


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status_code = STATUS_BY_ERROR.get(type(exc), DEFAULT_STATUS)
        return JSONResponse(status_code=status_code, content={"detail": exc.detail})
