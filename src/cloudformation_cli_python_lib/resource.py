import json
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Callable, MutableMapping, Optional, Tuple, Type, Union

from .boto3_proxy import SessionProxy, _get_boto_session
from .exceptions import InternalFailure, InvalidRequest, _HandlerError
from .interface import (
    Action,
    BaseResourceHandlerRequest,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)
from .log_delivery import ProviderLogHandler
from .metrics import MetricsPublisherProxy
from .utils import (
    BaseModel,
    Credentials,
    HandlerRequest,
    KitchenSinkEncoder,
    LambdaContext,
    TestEvent,
    UnmodelledRequest,
)

LOG = logging.getLogger(__name__)

MUTATING_ACTIONS = (Action.CREATE, Action.UPDATE, Action.DELETE)

HandlerSignature = Callable[
    [Optional[SessionProxy], Any, MutableMapping[str, Any]], ProgressEvent
]


def _ensure_serialize(
    entrypoint: Callable[
        [Any, MutableMapping[str, Any], Any],
        Union[ProgressEvent, MutableMapping[str, Any]],
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


class Resource:
    def __init__(self, type_name: str, resouce_model_cls: Type[BaseModel]) -> None:
        self.type_name = type_name
        self._model_cls: Type[BaseModel] = resouce_model_cls
        self._handlers: MutableMapping[Action, HandlerSignature] = {}

    def handler(self, action: Action) -> Callable[[HandlerSignature], HandlerSignature]:
        def _add_handler(f: HandlerSignature) -> HandlerSignature:
            self._handlers[action] = f
            return f

        return _add_handler

    def _invoke_handler(
        self,
        session: Optional[SessionProxy],
        request: BaseResourceHandlerRequest,
        action: Action,
        callback_context: MutableMapping[str, Any],
    ) -> ProgressEvent:
        try:
            handler = self._handlers[action]
        except KeyError:
            return ProgressEvent.failed(
                HandlerErrorCode.InternalFailure, f"No handler for {action}"
            )
        progress = handler(session, request, callback_context)
        is_in_progress = progress.status == OperationStatus.IN_PROGRESS
        is_mutable = action in MUTATING_ACTIONS
        if is_in_progress and not is_mutable:
            raise InternalFailure("READ and LIST handlers must return synchronously.")
        return progress

    def _parse_test_request(
        self, event_data: MutableMapping[str, Any]
    ) -> Tuple[
        Optional[SessionProxy],
        BaseResourceHandlerRequest,
        Action,
        MutableMapping[str, Any],
    ]:
        try:
            event = TestEvent(**event_data)
            creds = Credentials(**event.credentials)
            request: BaseResourceHandlerRequest = UnmodelledRequest(
                **event.request
            ).to_modelled(self._model_cls)

            session = _get_boto_session(creds, event.region)
            action = Action[event.action]
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InternalFailure(f"{e} ({type(e).__name__})") from e
        return session, request, action, event.callbackContext or {}

    @_ensure_serialize
    def test_entrypoint(
        self, event: MutableMapping[str, Any], _context: Any
    ) -> ProgressEvent:
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

    @staticmethod
    def _parse_request(
        event_data: MutableMapping[str, Any]
    ) -> Tuple[
        Tuple[Optional[SessionProxy], Optional[SessionProxy]],
        Action,
        MutableMapping[str, Any],
        HandlerRequest,
    ]:
        try:
            event = HandlerRequest.deserialize(event_data)
            caller_sess = _get_boto_session(event.requestData.callerCredentials)
            provider_sess = _get_boto_session(event.requestData.providerCredentials)
            # credentials are used when rescheduling, so can't zero them out (for now)
            action = Action[event.action]
            callback_context = event.callbackContext or {}
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InvalidRequest(f"{e} ({type(e).__name__})") from e
        return ((caller_sess, provider_sess), action, callback_context, event)

    def _cast_resource_request(
        self, request: HandlerRequest
    ) -> BaseResourceHandlerRequest:
        try:
            return UnmodelledRequest(
                clientRequestToken=request.bearerToken,
                desiredResourceState=request.requestData.resourceProperties,
                previousResourceState=request.requestData.previousResourceProperties,
                desiredResourceTags=request.requestData.stackTags,
                previousResourceTags=request.requestData.previousStackTags,
                systemTags=request.requestData.systemTags,
                previousSystemTags=request.requestData.previousSystemTags,
                awsAccountId=request.awsAccountId,
                logicalResourceIdentifier=request.requestData.logicalResourceId,
                stackId=request.stackId,
                region=request.region,
            ).to_modelled(self._model_cls)
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InvalidRequest(f"{e} ({type(e).__name__})") from e

    # TODO: refactor to reduce branching and locals
    @_ensure_serialize  # noqa: C901
    def __call__(  # pylint: disable=too-many-locals  # noqa: C901
        self, event_data: MutableMapping[str, Any], context: LambdaContext
    ) -> MutableMapping[str, Any]:
        logs_setup = False

        def print_or_log(message: str) -> None:
            if logs_setup:
                LOG.exception(message, exc_info=True)
            else:
                print(message)
                traceback.print_exc()

        try:
            sessions, action, callback, event = self._parse_request(event_data)
            caller_sess, provider_sess = sessions

            request = self._cast_resource_request(event)

            metrics = MetricsPublisherProxy()
            if event.requestData.providerLogGroupName and provider_sess:
                ProviderLogHandler.setup(event, provider_sess)
                logs_setup = True
                metrics.add_metrics_publisher(provider_sess, event.resourceType)

            metrics.publish_invocation_metric(datetime.utcnow(), action)
            start_time = datetime.utcnow()
            error = None

            try:
                progress = self._invoke_handler(caller_sess, request, action, callback)
            except Exception as e:  # pylint: disable=broad-except
                error = e
            m_secs = (datetime.utcnow() - start_time).total_seconds() * 1000.0
            metrics.publish_duration_metric(datetime.utcnow(), action, m_secs)
            if error:
                metrics.publish_exception_metric(datetime.utcnow(), action, error)
                raise error
        except _HandlerError as e:
            print_or_log("Handler error")
            progress = e.to_progress_event()
        except Exception as e:  # pylint: disable=broad-except
            print_or_log("Exception caught")
            progress = ProgressEvent.failed(HandlerErrorCode.InternalFailure, str(e))
        except BaseException as e:  # pylint: disable=broad-except
            print_or_log("Base exception caught (this is usually bad)")
            progress = ProgressEvent.failed(HandlerErrorCode.InternalFailure, str(e))

        # use the raw event_data as a last-ditch attempt to call back if the
        # request is invalid
        return progress._serialize()  # pylint: disable=protected-access
