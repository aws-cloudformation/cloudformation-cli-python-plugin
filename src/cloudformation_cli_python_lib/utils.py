# pylint: disable=invalid-name
import json
from dataclasses import dataclass, field, fields
from datetime import date, datetime, time
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Type,
    Union,
)

from .exceptions import InvalidRequest
from .interface import Action, BaseModel, BaseResourceHandlerRequest


class KitchenSinkEncoder(json.JSONEncoder):
    def default(self, o):  # type: ignore  # pylint: disable=method-hidden
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        try:
            return o._serialize()  # pylint: disable=protected-access
        except AttributeError:
            return super().default(o)


@dataclass
class TestEvent:
    credentials: Mapping[str, str]
    action: Action
    request: Mapping[str, Any]
    callbackContext: MutableMapping[str, Any] = field(default_factory=dict)
    region: Optional[str] = None


@dataclass
class Credentials:
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str


# pylint: disable=too-many-instance-attributes
@dataclass
class RequestData:
    resourceProperties: Mapping[str, Any]
    providerLogGroupName: Optional[str] = None
    logicalResourceId: Optional[str] = None
    systemTags: Optional[Mapping[str, Any]] = None
    stackTags: Optional[Mapping[str, Any]] = None
    # platform credentials aren't really optional, but this is used to
    # zero them out to prevent e.g. accidental logging
    callerCredentials: Optional[Credentials] = None
    providerCredentials: Optional[Credentials] = None
    previousResourceProperties: Optional[Mapping[str, Any]] = None
    previousStackTags: Optional[Mapping[str, Any]] = None
    previousSystemTags: Optional[Mapping[str, Any]] = None

    @classmethod
    def deserialize(cls, json_data: MutableMapping[str, Any]) -> "RequestData":
        req_data = RequestData(**json_data)
        for key in json_data:
            if not key.endswith("Credentials"):
                continue
            creds = json_data.get(key)
            if creds:
                setattr(req_data, key, Credentials(**creds))
        return req_data

    def serialize(self) -> Mapping[str, Any]:
        return {
            key: value.__dict__.copy() if key.endswith("Credentials") else value
            for key, value in self.__dict__.items()
            if value is not None
        }


# pylint: disable=too-many-instance-attributes
@dataclass
class HandlerRequest:
    action: str
    awsAccountId: str
    bearerToken: str
    region: str
    requestData: RequestData
    responseEndpoint: Optional[str] = None
    stackId: Optional[str] = None
    resourceType: Optional[str] = None
    resourceTypeVersion: Optional[str] = None
    callbackContext: Optional[MutableMapping[str, Any]] = None
    nextToken: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        dataclass_fields = {f.name for f in fields(self)}
        for k, v in kwargs.items():
            if k in dataclass_fields:
                setattr(self, k, v)

    @classmethod
    def deserialize(cls, json_data: MutableMapping[str, Any]) -> Any:
        event = HandlerRequest(**json_data)
        event.requestData = RequestData.deserialize(json_data.get("requestData", {}))
        return event

    def serialize(self) -> Mapping[str, Any]:
        return {
            key: value.serialize() if key == "requestData" else value
            for key, value in self.__dict__.items()
            if value is not None
        }


@dataclass
class UnmodelledRequest:
    clientRequestToken: str
    desiredResourceState: Optional[Mapping[str, Any]] = None
    previousResourceState: Optional[Mapping[str, Any]] = None
    desiredResourceTags: Optional[Mapping[str, Any]] = None
    previousResourceTags: Optional[Mapping[str, Any]] = None
    systemTags: Optional[Mapping[str, Any]] = None
    previousSystemTags: Optional[Mapping[str, Any]] = None
    awsAccountId: Optional[str] = None
    logicalResourceIdentifier: Optional[str] = None
    nextToken: Optional[str] = None
    stackId: Optional[str] = None
    region: Optional[str] = None

    def to_modelled(self, model_cls: Type[BaseModel]) -> BaseResourceHandlerRequest:
        # pylint: disable=protected-access
        return BaseResourceHandlerRequest(
            clientRequestToken=self.clientRequestToken,
            desiredResourceState=model_cls._deserialize(self.desiredResourceState),
            previousResourceState=model_cls._deserialize(self.previousResourceState),
            desiredResourceTags=self.desiredResourceTags,
            previousResourceTags=self.previousResourceTags,
            systemTags=self.systemTags,
            previousSystemTags=self.previousSystemTags,
            awsAccountId=self.awsAccountId,
            logicalResourceIdentifier=self.logicalResourceIdentifier,
            nextToken=self.nextToken,
            stackId=self.stackId,
            region=self.region,
            awsPartition=self.get_partition(self.region),
        )

    @staticmethod
    def get_partition(region: Optional[str]) -> Optional[str]:
        if region is None:
            return None

        if region.startswith("cn"):
            return "aws-cn"

        if region.startswith("us-gov"):
            return "aws-gov"
        return "aws"


class LambdaContext:
    get_remaining_time_in_millis: Callable[["LambdaContext"], int]
    invoked_function_arn: str


def deserialize_list(
    json_data: Union[List[Any], Dict[str, Any]], inner_dataclass: Any
) -> Optional[List[Any]]:
    if not json_data:
        return None
    return [_deser_item(item, inner_dataclass) for item in json_data]


def _deser_item(item: Any, inner_dataclass: Any) -> Any:
    if isinstance(item, list):
        return deserialize_list(item, inner_dataclass)
    if isinstance(item, dict):
        return inner_dataclass._deserialize(item)  # pylint: disable=protected-access
    raise InvalidRequest(f"cannot deserialize lists of {type(item)}")
