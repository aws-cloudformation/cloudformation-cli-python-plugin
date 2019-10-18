import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Mapping, MutableMapping, Optional, Type

from .interface import Action, ResourceHandlerRequest, T


class KitchenSinkEncoder(json.JSONEncoder):
    def default(self, o):  # type: ignore pylint: disable=method-hidden
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
    region_name: Optional[str] = None


@dataclass
class Credentials:
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str


@dataclass
class UnmodelledRequest:
    clientRequestToken: str
    desiredResourceState: Optional[Mapping[str, Any]] = None
    previousResourceState: Optional[Mapping[str, Any]] = None
    logicalResourceIdentifier: Optional[str] = None
    nextToken: Optional[str] = None

    def to_modelled(self, model_cls: Type[T]) -> ResourceHandlerRequest[T]:
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
