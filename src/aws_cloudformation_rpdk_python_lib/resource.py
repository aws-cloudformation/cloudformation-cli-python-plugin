import json
import logging
from functools import wraps
from typing import Any, Callable, Generic, Mapping, MutableMapping, Tuple, Type

from .boto3_proxy import SessionProxy, _get_boto_session
from .exceptions import InvalidRequest, _HandlerError
from .interface import (
    Action,
    HandlerErrorCode,
    ProgressEvent,
    ResourceHandlerRequest,
    T,
)
from .utils import Credentials, KitchenSinkEncoder, TestEvent, UnmodelledRequest

LOG = logging.getLogger(__name__)

HandlerSignature = Callable[
    [SessionProxy, ResourceHandlerRequest[T], MutableMapping[str, Any]],
    ProgressEvent[T],
]


def _ensure_serialize(
    entrypoint: Callable[[Any, Mapping[str, Any], Any], ProgressEvent[T]]
) -> Callable[[Any, Mapping[str, Any], Any], Any]:
    @wraps(entrypoint)
    def wrapper(self: Any, event: Mapping[str, Any], context: Any) -> Any:
        try:
            response = entrypoint(self, event, context)
            serialized = json.dumps(response, cls=KitchenSinkEncoder)
        except Exception as e:  # pylint: disable=broad-except
            return ProgressEvent.failed(
                HandlerErrorCode.InternalFailure, str(e)
            ).to_json()
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
        session: SessionProxy,
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
        self, event_data: Mapping[str, Any]
    ) -> Tuple[
        SessionProxy, ResourceHandlerRequest[T], Action, MutableMapping[str, Any]
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
        self, event: Mapping[str, Any], _context: Any
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
