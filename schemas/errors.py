"""Shared error types used by translator.py and shown by the dashboard."""


# =============================================================================
# TranslatorError
# =============================================================================

# Raised by translator.py when a backend call fails; its message is safe for the UI.
class TranslatorError(Exception):
    pass
