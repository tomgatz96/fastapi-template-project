"""
Errors raised when a domain rule is broken.

Services raise these instead of `HTTPException` so that the domain layer
stays independent of the web framework: the same service can be called from
an HTTP route, a background job or a test without dragging FastAPI along.

They are translated into HTTP responses in one place, `app/api/errors.py`.
"""


class DomainError(Exception):
    """Base class for every rule violation the domain can report."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    """The requested entity does not exist."""


class PermissionDeniedError(DomainError):
    """The user is not allowed to perform this action."""


class ConflictError(DomainError):
    """The action contradicts the current state of the data."""


class InvalidRequestError(DomainError):
    """
    The request is well formed but cannot be carried out as asked.

    Distinct from `ConflictError` only in the status code it maps to. It
    exists because several endpoints answer 400 where 409 would arguably be
    the better answer, and a refactor is the wrong moment to change what the
    API returns.
    """
