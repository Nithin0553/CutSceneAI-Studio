class DialogueError(RuntimeError):
    """Base error for Dialogue Engine operations."""


class DialogueInputError(DialogueError):
    """Raised when a dialogue request is incomplete or internally inconsistent."""


class DialogueAudioError(DialogueError):
    """Raised when supplied or generated audio is not a supported WAV file."""


class DialogueConfigurationError(DialogueError):
    """Raised when a configured provider cannot be initialized."""


class DialogueProviderError(DialogueError):
    def __init__(self, message: str, *, retryable: bool, request_id: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.request_id = request_id


class DialogueOutputError(DialogueError):
    """Raised when a provider returns unusable audio."""
