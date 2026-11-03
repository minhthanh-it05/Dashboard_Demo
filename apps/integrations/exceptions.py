class IntegrationError(Exception):
    """Base class for every failure raised by an adapter or client."""


class IntegrationDisabled(IntegrationError):
    """The integration is switched off by configuration."""


class IntegrationNotReady(IntegrationError):
    """Live mode was requested but the vendor details it needs are not confirmed yet."""


class TransientError(IntegrationError):
    """A failure worth retrying (timeout, connection error, HTTP 429/5xx)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class RemoteApiError(IntegrationError):
    """The remote system answered with an error that retrying will not fix."""


class ResponseFormatError(IntegrationError):
    """The response did not have the shape the adapter expects."""


class WriteNotAllowed(IntegrationError):
    """A write endpoint was requested; integrations are read-only for now."""
