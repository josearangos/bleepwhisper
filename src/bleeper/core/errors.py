"""Error types raised by the core; the CLI maps them to exit codes."""


class BleeperError(Exception):
    """Base class for every error the core raises on purpose."""


class InvalidInputError(BleeperError):
    """The user's input or options are invalid (CLI exit code 1)."""


class ProcessingError(BleeperError):
    """Valid input could not be processed (CLI exit code 2)."""
