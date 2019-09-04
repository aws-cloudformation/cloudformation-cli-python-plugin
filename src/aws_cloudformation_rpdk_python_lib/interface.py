import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Generic, List, Mapping, Optional, Type, TypeVar

LOG = logging.getLogger(__name__)

T = TypeVar("T")  # pylint: disable=invalid-name


class _AutoName(Enum):
    @staticmethod
    def _generate_next_value_(
        name: str, _start: int, _count: int, _last_values: List[str]
    ) -> str:
        return name


class Action(str, _AutoName):
    CREATE = auto()
    READ = auto()
    UPDATE = auto()
    DELETE = auto()
    LIST = auto()


class OperationStatus(str, _AutoName):
    IN_PROGRESS = auto()
    SUCCESS = auto()
    FAILED = auto()


class HandlerErrorCode(str, _AutoName):
    NotUpdatable = auto()
    InvalidRequest = auto()
    AccessDenied = auto()
    InvalidCredentials = auto()
    AlreadyExists = auto()
    NotFound = auto()
    ResourceConflict = auto()
    Throttling = auto()
    ServiceLimitExceeded = auto()
    NotStabilized = auto()
    GeneralServiceException = auto()
    ServiceInternalError = auto()
    NetworkFailure = auto()
    InternalFailure = auto()


@dataclass
class ProgressEvent(Generic[T]):
    status: OperationStatus
    errorCode: Optional[HandlerErrorCode] = None
    message: str = ""
    callbackContext: Mapping[str, Any] = field(default_factory=dict)
    callbackDelaySeconds: int = 0
    resourceModel: Optional[T] = None
    resourceModels: Optional[List[T]] = None

    def to_json(self) -> Mapping[str, Any]:
        return self.__dict__

    @classmethod
    def failed(
        cls: Type["ProgressEvent[T]"], error_code: HandlerErrorCode, message: str
    ) -> "ProgressEvent[T]":
        return cls(status=OperationStatus.FAILED, errorCode=error_code, message=message)


@dataclass
class ResourceHandlerRequest(Generic[T]):
    clientRequestToken: str
    desiredResourceState: Optional[T]
    previousResourceState: Optional[T]
    logicalResourceIdentifier: Optional[str]
