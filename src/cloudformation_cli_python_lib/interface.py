import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Generic, List, Mapping, MutableMapping, Optional, Type, TypeVar

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


class StandardUnit(str, _AutoName):
    Count = auto()
    Milliseconds = auto()


class MetricTypes(str, _AutoName):
    HandlerException = auto()
    HandlerInvocationCount = auto()
    HandlerInvocationDuration = auto()


class OperationStatus(str, _AutoName):
    PENDING = auto()
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


# pylint: disable=too-many-instance-attributes
@dataclass
class ProgressEvent(Generic[T]):
    # pylint: disable=invalid-name
    status: OperationStatus
    errorCode: Optional[HandlerErrorCode] = None
    message: str = ""
    callbackContext: Optional[Mapping[str, Any]] = None
    callbackDelaySeconds: int = 0
    resourceModel: Optional[T] = None
    resourceModels: Optional[List[T]] = None
    nextToken: Optional[str] = None

    def _serialize(
        self, to_response: bool = False, bearer_token: Optional[str] = None
    ) -> MutableMapping[str, Any]:
        # to match Java serialization, which drops `null` values, and the
        # contract tests currently expect this also
        ser = {k: v for k, v in self.__dict__.items() if v is not None}
        # mutate to what's expected in the response
        if to_response:
            ser["bearerToken"] = bearer_token
            ser["operationStatus"] = ser.pop("status")
            if ser["callbackDelaySeconds"] == 0:
                del ser["callbackDelaySeconds"]
        return ser

    @classmethod
    def failed(
        cls: Type["ProgressEvent[T]"], error_code: HandlerErrorCode, message: str
    ) -> "ProgressEvent[T]":
        return cls(status=OperationStatus.FAILED, errorCode=error_code, message=message)


@dataclass
class ResourceHandlerRequest(Generic[T]):
    # pylint: disable=invalid-name
    clientRequestToken: str
    desiredResourceState: Optional[T]
    previousResourceState: Optional[T]
    logicalResourceIdentifier: Optional[str]
    nextToken: Optional[str]
