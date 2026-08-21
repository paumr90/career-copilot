class JDExtractionProviderError(RuntimeError):
    """
    Base error for JD extraction provider failures.
    """


class JDExtractionTimeoutError(
    JDExtractionProviderError
):
    """
    Raised when the external extraction provider
    exceeds the configured timeout.
    """


class JDExtractionConnectionError(
    JDExtractionProviderError
):
    """
    Raised when the external extraction provider
    cannot be reached.
    """


class JDExtractionRateLimitError(
    JDExtractionProviderError
):
    """
    Raised when the external provider rejects the
    request because of rate limiting.
    """


class JDExtractionAPIError(
    JDExtractionProviderError
):
    """
    Raised for other non-success API responses.
    """