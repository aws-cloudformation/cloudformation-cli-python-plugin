import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Mapping, MutableMapping, Optional, Type

from .interface import Action, ResourceHandlerRequest, T


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
    # pylint: disable=invalid-name
    credentials: Mapping[str, str]
    action: Action
    request: Mapping[str, Any]
    callbackContext: MutableMapping[str, Any] = field(default_factory=dict)
    region_name: Optional[str] = None


@dataclass
class Credentials:
    # pylint: disable=invalid-name
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str


# pylint: disable=too-many-instance-attributes
@dataclass
class RequestData:
    # pylint: disable=invalid-name
    callerCredentials: Credentials
    platformCredentials: Credentials
    providerCredentials: Credentials
    providerLogGroupName: str
    logicalResourceId: str
    resourceProperties: Mapping[str, Any]
    systemTags: Mapping[str, Any]
    stackTags: Mapping[str, Any]
    previousResourceProperties: Optional[Mapping[str, Any]] = None
    previousStackTags: Optional[Mapping[str, Any]] = None

    @classmethod
    def deserialize(cls, json_data: MutableMapping[str, Any]) -> "RequestData":
        req_data = RequestData(**json_data)
        for prefix in ["caller", "provider", "platform"]:
            cred_type = f"{prefix}Credentials"
            setattr(req_data, cred_type, Credentials(**json_data.get(cred_type, {})))
        return req_data


# pylint: disable=too-many-instance-attributes
@dataclass
class HandlerRequest:
    # pylint: disable=invalid-name
    awsAccountId: str
    bearerToken: str
    region: str
    action: str
    responseEndpoint: str
    resourceType: str
    resourceTypeVersion: str
    requestData: RequestData
    stackId: str
    nextToken: Optional[str] = None
    requestContext: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def deserialize(cls, json_data: MutableMapping[str, Any]) -> "HandlerRequest":
        event = HandlerRequest(**json_data)
        event.requestData = RequestData.deserialize(json_data.get("requestData", {}))
        return event


@dataclass
class UnmodelledRequest:
    # pylint: disable=invalid-name
    clientRequestToken: str
    desiredResourceState: Optional[Mapping[str, Any]] = None
    previousResourceState: Optional[Mapping[str, Any]] = None
    logicalResourceIdentifier: Optional[str] = None
    nextToken: Optional[str] = None

    def to_modelled(self, model_cls: Type[T]) -> ResourceHandlerRequest[T]:
        # pylint: disable=protected-access
        return ResourceHandlerRequest(
            clientRequestToken=self.clientRequestToken,
            desiredResourceState=model_cls._deserialize(  # type: ignore
                self.desiredResourceState
            ),
            previousResourceState=model_cls._deserialize(  # type: ignore
                self.previousResourceState
            ),
            logicalResourceIdentifier=self.logicalResourceIdentifier,
            nextToken=self.nextToken,
        )
