class LoggerError(Exception):
    """Base exception for logger processing failures."""


class LoggerBusyError(LoggerError):
    """Raised when a logger processing run is already active."""


class LoggerImportError(LoggerError):
    """Raised when an individual logger file cannot be imported."""

