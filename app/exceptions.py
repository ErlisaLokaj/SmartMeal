from typing import Any, Mapping, Optional


class ServiceValidationError(Exception):
    """Raised when input data is invalid or a precondition for a service call is not met.

    Attributes:
        message: human-readable message
        details: optional mapping with extra context (field errors, validation info)
        code: optional machine-readable error code
        http_status: suggested HTTP status code for handlers (400)
    """

    http_status = 400

    def __init__(self, message: str = "Invalid input", details: Optional[Mapping[str, Any]] = None, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"message": self.message}
        if self.code:
            payload["code"] = self.code
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message


class NotFoundError(Exception):
    """Raised when a requested resource was not found.

    Attributes are similar to ServiceValidationError. http_status is 404.
    """

    http_status = 404

    def __init__(self, message: str = "Not found", details: Optional[Mapping[str, Any]] = None, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"message": self.message}
        if self.code:
            payload["code"] = self.code
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message


class ConflictError(Exception):
    """Raised when a resource conflict occurs (e.g., duplicate entry).

    Attributes are similar to ServiceValidationError. http_status is 409.
    """

    http_status = 409

    def __init__(self, message: str = "Conflict", details: Optional[Mapping[str, Any]] = None, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"message": self.message}
        if self.code:
            payload["code"] = self.code
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message


class UnauthorizedError(Exception):
    """Raised when authentication or authorization fails.

    Attributes are similar to ServiceValidationError. http_status is 401.
    """

    http_status = 401

    def __init__(self, message: str = "Unauthorized", details: Optional[Mapping[str, Any]] = None, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"message": self.message}
        if self.code:
            payload["code"] = self.code
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message
