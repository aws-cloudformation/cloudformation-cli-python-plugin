import json
import logging
from functools import wraps
from typing import Any, Callable, Generic, MutableMapping, Optional, Tuple, Type, Union

from .boto3_proxy import SessionProxy, _get_boto_session
from .exceptions import InvalidRequest, _HandlerError
from .interface import (
    Action,
    HandlerErrorCode,
    ProgressEvent,
    ResourceHandlerRequest,
    T,
)
from .log_delivery import ProviderLogHandler
from .utils import (
    Credentials,
    HandlerRequest,
    KitchenSinkEncoder,
    TestEvent,
    UnmodelledRequest,
)

LOG = logging.getLogger(__name__)

HandlerSignature = Callable[
    [Optional[SessionProxy], ResourceHandlerRequest[T], MutableMapping[str, Any]],
    ProgressEvent[T],
]


def _ensure_serialize(
    entrypoint: Callable[
        [Any, MutableMapping[str, Any], Any],
        Union[ProgressEvent[T], MutableMapping[str, Any]],
    ]
) -> Callable[[Any, MutableMapping[str, Any], Any], Any]:
    @wraps(entrypoint)
    def wrapper(self: Any, event: MutableMapping[str, Any], context: Any) -> Any:
        try:
            response = entrypoint(self, event, context)
            serialized = json.dumps(response, cls=KitchenSinkEncoder)
        except Exception as e:  # pylint: disable=broad-except
            return ProgressEvent.failed(  # pylint: disable=protected-access
                HandlerErrorCode.InternalFailure, str(e)
            )._serialize()
        return json.loads(serialized)

    return wrapper


class Resource(Generic[T]):
    def __init__(self, resouce_model_cls: Type[T]) -> None:
        self._model_cls: Type[T] = resouce_model_cls
        self._handlers: MutableMapping[Action, HandlerSignature[T]] = {}

    def handler(
        self, action: Action
    ) -> Callable[[HandlerSignature[T]], HandlerSignature[T]]:
        def _add_handler(f: HandlerSignature[T]) -> HandlerSignature[T]:
            self._handlers[action] = f
            return f

        return _add_handler

    def _invoke_handler(
        self,
        session: Optional[SessionProxy],
        request: ResourceHandlerRequest[T],
        action: Action,
        callback_context: MutableMapping[str, Any],
    ) -> ProgressEvent[T]:
        try:
            handler = self._handlers[action]
        except KeyError:
            return ProgressEvent.failed(
                HandlerErrorCode.InternalFailure, f"No handler for {action}"
            )

        return handler(session, request, callback_context)

    def _parse_test_request(
        self, event_data: MutableMapping[str, Any]
    ) -> Tuple[
        Optional[SessionProxy],
        ResourceHandlerRequest[T],
        Action,
        MutableMapping[str, Any],
    ]:
        try:
            event = TestEvent(**event_data)
            creds = Credentials(**event.credentials)
            request: ResourceHandlerRequest[T] = UnmodelledRequest(
                **event.request
            ).to_modelled(self._model_cls)

            session = _get_boto_session(creds, event.region_name)
            action = Action[event.action]
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InvalidRequest(f"{e} ({type(e).__name__})") from e
        return session, request, action, event.callbackContext or {}

    @_ensure_serialize
    def test_entrypoint(
        self, event: MutableMapping[str, Any], _context: Any
    ) -> ProgressEvent[T]:
        msg = "Uninitialized"
        try:
            session, request, action, callback_context = self._parse_test_request(event)
            return self._invoke_handler(session, request, action, callback_context)
        except _HandlerError as e:
            LOG.exception("Handler error")
            return e.to_progress_event()
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Exception caught")
            msg = str(e)
        except BaseException as e:  # pylint: disable=broad-except
            LOG.critical("Base exception caught (this is usually bad)", exc_info=True)
            msg = str(e)
        return ProgressEvent.failed(HandlerErrorCode.InternalFailure, msg)

    def _parse_request(
        self, event_data: MutableMapping[str, Any]
    ) -> Tuple[
        Optional[SessionProxy],
        ResourceHandlerRequest[T],
        Action,
        MutableMapping[str, Any],
    ]:
        try:
            event = HandlerRequest.deserialize(event_data)
            creds = event.requestData.callerCredentials
            request: ResourceHandlerRequest[T] = UnmodelledRequest(
                clientRequestToken=event.bearerToken,
                desiredResourceState=event.requestData.resourceProperties,
                previousResourceState=event.requestData.previousResourceProperties,
                logicalResourceIdentifier=event.requestData.logicalResourceId,
            ).to_modelled(self._model_cls)

            session = _get_boto_session(creds, event.region)
            action = Action[event.action]
            callback_context = event.requestContext.get("callbackContext", {})
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InvalidRequest(f"{e} ({type(e).__name__})") from e
        return session, request, action, callback_context

    @_ensure_serialize
    def __call__(
        self, event_data: MutableMapping[str, Any], _context: Any
    ) -> MutableMapping[str, Any]:
        try:
            ProviderLogHandler.setup(event_data)
            parsed = self._parse_request(event_data)
            session, request, action, callback_context = parsed
            progress_event = self._invoke_handler(
                session, request, action, callback_context
            )
        except _HandlerError as e:
            LOG.exception("Handler error", exc_info=True)
            progress_event = e.to_progress_event()
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Exception caught", exc_info=True)
            progress_event = ProgressEvent.failed(
                HandlerErrorCode.InternalFailure, str(e)
            )
        except BaseException as e:  # pylint: disable=broad-except
            LOG.critical("Base exception caught (this is usually bad)", exc_info=True)
            progress_event = ProgressEvent.failed(
                HandlerErrorCode.InternalFailure, str(e)
            )
        return progress_event._serialize(  # pylint: disable=protected-access
            to_response=True, bearer_token=event_data.get("bearerToken")
        )
