class ApplicationError(Exception):
    """Base class for expected application-level errors."""


class NotFoundError(ApplicationError):
    """A requested resource does not exist (or is not active)."""


class ValidationError(ApplicationError):
    """Input failed validation."""


class RateLimitedError(ApplicationError):
    """The caller exceeded the allowed rate."""
