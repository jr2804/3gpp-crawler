"""Custom exceptions for LibreOffice conversion."""


class SofficeNotFoundError(RuntimeError):
    """Raised when the soffice executable cannot be located."""


class UnsupportedConversionError(ValueError):
    """Raised when a requested conversion is unsupported."""


class ConversionError(RuntimeError):
    """Raised when LibreOffice fails to convert a document."""
