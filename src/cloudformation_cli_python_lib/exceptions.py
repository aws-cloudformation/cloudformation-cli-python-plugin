from typing import Any

from .interface import HandlerErrorCode, ProgressEvent


class _HandlerError(Exception):
    def __init__(self, *args: Any):
        self._error_code = HandlerErrorCode[type(self).__name__]
        super().__init__(*args)

    def to_progress_event(self) -> ProgressEvent:
        return ProgressEvent.failed(self._error_code, str(self))


class NotUpdatable(_HandlerError):
    pass


class InvalidRequest(_HandlerError):
    pass


class AccessDenied(_HandlerError):
    pass


class InvalidCredentials(_HandlerError):
    pass


class AlreadyExists(_HandlerError):
    def __init__(self, type_name: str, identifier: str):
        super().__init__(
            f"Resource of type '{type_name}' with identifier "
            f"'{identifier}' already exists."
        )


class NotFound(_HandlerError):
    def __init__(self, type_name: str, identifier: str):
        super().__init__(
            f"Resource of type '{type_name}' with identifier "
            f"'{identifier}' was not found."
        )


class ResourceConflict(_HandlerError):
    pass


class Throttling(_HandlerError):
    pass


class ServiceLimitExceeded(_HandlerError):
    pass


class NotStabilized(_HandlerError):
    pass


class GeneralServiceException(_HandlerError):
    pass


class ServiceInternalError(_HandlerError):
    pass


class NetworkFailure(_HandlerError):
    pass


class InternalFailure(_HandlerError):
    pass


class InvalidTypeConfiguration(_HandlerError):
    def __init__(self, type_name: str, message: str):
        super().__init__(
            f"Invalid TypeConfiguration provided for type {type_name}."
            f" Reason: {message}"
        )


class HandlerInternalFailure(_HandlerError):
    pass


class NonCompliant(_HandlerError):
    def __init__(self, type_name: str, message: str):
        super().__init__(
            f"Hook of type '{type_name}' returned a Non-Complaint status."
            f" Reason: {message}"
        )


class UnsupportedTarget(_HandlerError):
    def __init__(self, hook_type_name: str, target_type_name: str):
        super().__init__(
            f"Hook of type '{hook_type_name}' received request"
            f" for unsupported target '{target_type_name}'"
        )


class Unknown(_HandlerError):
    pass


class _EncryptionError(Exception):
    pass
