class TokenLensError(Exception):
    """Base exception for all TokenLens SDK errors."""


class AuthError(TokenLensError):
    """API key is missing, malformed, or rejected by the backend."""


class LoggingError(TokenLensError):
    """A log request to the TokenLens backend failed."""
