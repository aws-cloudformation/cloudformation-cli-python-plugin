from typing import Any, Generic

from .interface import HandlerErrorCode, ProgressEvent, T


class _HandlerError(Exception, Generic[T]):
    def __init__(self, *args: Any):
        self._error_code = HandlerErrorCode[type(self).__name__]
        super().__init__(*args)

    def to_progress_event(self) -> ProgressEvent[T]:
        return ProgressEvent.failed(self._error_code, str(self))


class NotUpdatable(_HandlerError[T]):
    pass


class InvalidRequest(_HandlerError[T]):
    pass


class AccessDenied(_HandlerError[T]):
    pass


class InvalidCredentials(_HandlerError[T]):
    pass


class AlreadyExists(_HandlerError[T]):
    def __init__(self, type_name: str, identifier: str):
        super().__init__(
            f"Resource of type '{type_name}' with identifier "
            f"'{identifier}' already exists."
        )


class NotFound(_HandlerError[T]):
    def __init__(self, type_name: str, identifier: str):
        super().__init__(
            f"Resource of type '{type_name}' with identifier "
            f"'{identifier}' was not found."
        )


class ResourceConflict(_HandlerError[T]):
    pass


class Throttling(_HandlerError[T]):
    pass


class ServiceLimitExceeded(_HandlerError[T]):
    pass


class NotStabilized(_HandlerError[T]):
    pass


class GeneralServiceException(_HandlerError[T]):
    pass


class ServiceInternalError(_HandlerError[T]):
    pass


class NetworkFailure(_HandlerError[T]):
    pass


class InternalFailure(_HandlerError[T]):
    pass
