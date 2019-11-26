import json
import logging
from functools import wraps
from time import sleep
from typing import Any, Callable, MutableMapping, Optional, Tuple, Type, Union

# boto3 doesn't have stub files
import boto3  # type: ignore

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
from .scheduler import CloudWatchScheduler
from .utils import (
    BaseResourceModel,
    Credentials,
    HandlerRequest,
    KitchenSinkEncoder,
    LambdaContext,
    TestEvent,
    UnmodelledRequest,
)

LOG = logging.getLogger(__name__)

MUTATING_ACTIONS = (Action.CREATE, Action.UPDATE, Action.DELETE)
INVOCATION_TIMEOUT_MS = 60000

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
    def __init__(self, resouce_model_cls: Type[BaseResourceModel]) -> None:
        self._model_cls: Type[BaseResourceModel] = resouce_model_cls
        self._handlers: MutableMapping[Action, HandlerSignature] = {}

    def handler(self, action: Action) -> Callable[[HandlerSignature], HandlerSignature]:
        def _add_handler(f: HandlerSignature) -> HandlerSignature:
            self._handlers[action] = f
            return f

        return _add_handler

    @staticmethod
    def schedule_reinvocation(
        handler_request: HandlerRequest,
        handler_response: ProgressEvent,
        context: LambdaContext,
        credentials: Credentials,
    ) -> bool:
        if handler_response.status != OperationStatus.IN_PROGRESS:
            return False
        # modify requestContext dict in-place, so that invoke count is bumped on local
        # reinvoke too
        reinvoke_context = handler_request.requestContext
        reinvoke_context["invocation"] = reinvoke_context.get("invocation", 0) + 1
        callback_delay_s = handler_response.callbackDelaySeconds
        remaining_ms = context.get_remaining_time_in_millis()

        # when a handler requests a sub-minute callback delay, and if the lambda
        # invocation has enough runtime (with 20% buffer), we can re-run the handler
        # locally otherwise we re-invoke through CloudWatchEvents
        needed_ms_remaining = callback_delay_s * 1200 + INVOCATION_TIMEOUT_MS
        if callback_delay_s < 60 and remaining_ms > needed_ms_remaining:
            LOG.info(
                "Scheduling re-invoke locally after %s seconds, with Context {%s}",
                callback_delay_s,
                reinvoke_context,
            )
            sleep(callback_delay_s)
            return True
        LOG.info("Scheduling re-invoke with Context {%s}", reinvoke_context)
        callback_delay_min = int(callback_delay_s / 60)
        session = boto3.Session(
            aws_access_key_id=credentials.accessKeyId,
            aws_secret_access_key=credentials.secretAccessKey,
            aws_session_token=credentials.sessionToken,
        )
        CloudWatchScheduler(boto3_session=session).reschedule_after_minutes(
            function_arn=context.invoked_function_arn,
            minutes_from_now=callback_delay_min,
            handler_request=handler_request,
        )
        return False

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

            session = _get_boto_session(creds, event.region_name)
            action = Action[event.action]
        except Exception as e:  # pylint: disable=broad-except
            LOG.exception("Invalid request")
            raise InvalidRequest(f"{e} ({type(e).__name__})") from e
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

    def _parse_request(
        self, event_data: MutableMapping[str, Any]
    ) -> Tuple[
        Optional[SessionProxy],
        BaseResourceHandlerRequest,
        Action,
        MutableMapping[str, Any],
    ]:
        try:
            event = HandlerRequest.deserialize(event_data)
            creds = event.requestData.callerCredentials
            request: BaseResourceHandlerRequest = UnmodelledRequest(
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
        self, event_data: MutableMapping[str, Any], context: LambdaContext
    ) -> MutableMapping[str, Any]:
        try:
            ProviderLogHandler.setup(event_data)
            parsed = self._parse_request(event_data)
            session, request, action, callback_context = parsed
            invoke = True
            while invoke:
                progress_event = self._invoke_handler(
                    session, request, action, callback_context
                )
                invoke = self.schedule_reinvocation(
                    HandlerRequest.deserialize(event_data),
                    progress_event,
                    context,
                    Credentials(**event_data["requestData"]["platformCredentials"]),
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
