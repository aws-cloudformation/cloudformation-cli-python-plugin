import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Mapping, MutableMapping, Optional, Type

LOG = logging.getLogger(__name__)


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


class BaseResourceModel:
    def _serialize(self) -> Mapping[str, Any]:
        return {
            k: self._serialize_item(v)
            for k, v in self.__dict__.items()
            if v is not None
        }

    def _serialize_item(self, v: Any) -> Any:
        if isinstance(v, list):
            return self._serialize_list(v)
        if isinstance(v, BaseResourceModel):
            return v._serialize()  # pylint: disable=protected-access
        return v

    def _serialize_list(self, src_list: List[Any]) -> List[Any]:
        return [self._serialize_item(i) for i in src_list]

    @classmethod
    def _deserialize(
        cls: Type["BaseResourceModel"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["BaseResourceModel"]:
        raise NotImplementedError()


# pylint: disable=too-many-instance-attributes
@dataclass
class ProgressEvent:
    # pylint: disable=invalid-name
    status: OperationStatus
    errorCode: Optional[HandlerErrorCode] = None
    message: str = ""
    callbackContext: Optional[MutableMapping[str, Any]] = None
    callbackDelaySeconds: int = 0
    resourceModel: Optional[BaseResourceModel] = None
    resourceModels: Optional[List[BaseResourceModel]] = None
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
            ser["operationStatus"] = ser.pop("status").name
            if self.resourceModel:
                # pylint: disable=protected-access
                ser["resourceModel"] = self.resourceModel._serialize()
            if self.resourceModels:
                ser["resourceModels"] = [
                    # pylint: disable=protected-access
                    model._serialize()
                    for model in self.resourceModels
                ]
            del ser["callbackDelaySeconds"]
            if "callbackContext" in ser:
                del ser["callbackContext"]
            if self.errorCode:
                ser["errorCode"] = self.errorCode.name
        return ser

    @classmethod
    def failed(
        cls: Type["ProgressEvent"], error_code: HandlerErrorCode, message: str
    ) -> "ProgressEvent":
        return cls(status=OperationStatus.FAILED, errorCode=error_code, message=message)


@dataclass
class BaseResourceHandlerRequest:
    # pylint: disable=invalid-name
    clientRequestToken: str
    desiredResourceState: Optional[BaseResourceModel]
    previousResourceState: Optional[BaseResourceModel]
    logicalResourceIdentifier: Optional[str]
    nextToken: Optional[str]
