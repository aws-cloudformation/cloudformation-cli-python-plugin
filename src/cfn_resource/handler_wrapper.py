import importlib
import logging
from datetime import datetime
from time import sleep

from . import ProgressEvent, Status, request
from .boto3_proxy import get_boto3_proxy_session, get_boto_session_config
from .exceptions import Codes, InternalFailure
from .metrics import Metrics
from .scheduler import CloudWatchScheduler
from .utils import get_log_level_from_env, is_sam_local, setup_json_logger

LOG = logging.getLogger(__name__)

try:
    from resource_model import ResourceModel  # pylint: disable=import-error
except ModuleNotFoundError as e:
    if str(e) == "No module named 'resource_model'":
        LOG.warning(
            "resource_model module not present in path, using BaseResourceModel"
        )
        from .base_resource_model import BaseResourceModel as ResourceModel
    else:
        raise

LOG_LEVEL_ENV_VAR = "LOG_LEVEL"
BOTO_LOG_LEVEL_ENV_VAR = "BOTO_LOG_LEVEL"


# TODO:
# - catch timeouts


def _handler_wrapper(event, context):
    progress_event = ProgressEvent(Status.FAILED, resourceModel=ResourceModel())
    try:
        setup_json_logger(
            level=get_log_level_from_env(LOG_LEVEL_ENV_VAR),
            boto_level=get_log_level_from_env(BOTO_LOG_LEVEL_ENV_VAR, logging.ERROR),
            acctid=event["awsAccountId"],
            token=event["bearerToken"],
            action=event["action"],
            logicalid=event["requestData"]["logicalResourceId"],
            stackid=event["stackId"],
        )

        wrapper = HandlerWrapper(event, context)
        logging.info("Invoking %s handler", event["action"])
        progress_event = wrapper.run_handler()
    except Exception as e:  # pylint: disable=broad-except
        LOG.error("CloudWatch Metrics for this invocation have not been published")
        LOG.error("unhandled exception", exc_info=True)
        progress_event.errorCode = (
            type(e).__name__ if Codes.is_handled(e) else Codes.INTERNAL_FAILURE
        )
        progress_event.message = "{}: {}".format(type(e).__name__, str(e))
    finally:
        return progress_event.json()  # pylint: disable=lost-exception


class HandlerWrapper:  # pylint: disable=too-many-instance-attributes
    def __init__(self, event, context):
        self._start_time = datetime.now()
        self._event = event
        self._context = context
        self._action = event["action"]
        self._handler_response = ProgressEvent(
            Status.FAILED, resourceModel=ResourceModel()
        )
        self._session_config = get_boto_session_config(event)
        self._metrics = Metrics(
            resource_type=event["resourceType"], session_config=self._session_config
        )
        self._metrics.invocation(self._start_time, action=event["action"])
        self._handler_args = self._event_parse()
        self._scheduler = CloudWatchScheduler(self._session_config)
        self._scheduler.cleanup(event)
        self._timer = None

    def _get_handler(self, handler_path="handlers"):
        try:
            handlers = importlib.import_module(handler_path)
        except ModuleNotFoundError as e:
            if str(e) == "No module named '{}'".format(handler_path):
                raise InternalFailure("handlers.py does not exist")
            raise
        try:
            return getattr(handlers, "{}_handler".format(self._action.lower()))
        except AttributeError:
            LOG.error("AttributeError", exc_info=True)
            raise InternalFailure(
                "handlers.py does not contain a {}_handler function".format(
                    self._action
                )
            )

    def _event_parse(self):
        props, prev_props, callback = request.extract_event_data(self._event)
        session_config = get_boto_session_config(self._event)
        args = [
            ResourceModel.new(**props),
            request.RequestContext(self._event, self._context),
            get_boto3_proxy_session(session_config),
        ]
        # Write actions can be async
        if self._event["action"] in [
            request.Action.CREATE,
            request.Action.UPDATE,
            request.Action.DELETE,
        ]:
            args.append(callback)
        # Update action gets previous properties
        if self._event["action"] == request.Action.UPDATE:
            args.append(ResourceModel.new(**prev_props))
        return args

    def _is_local_callback(self):
        if self._handler_response.callbackDelaySeconds > 60:
            return False
        remaining = self._context.get_remaining_time_in_millis() / 1000
        needed = self._handler_response.callbackDelaySeconds * 1.2
        return needed < remaining

    def _is_callback(self):
        return self._handler_response.status == Status.IN_PROGRESS

    def _local_callback(self):
        self._handler_args[3] = self._handler_response.callbackContext
        if "invocation" not in self._event["requestContext"]:
            self._event["requestContext"]["invocation"] = 1
        self._event["requestContext"]["invocation"] += 1
        handler = self._get_handler()
        self._handler_response = handler(*self._handler_args)

    def _callback(self):
        while self._is_local_callback() and self._is_callback():
            sleep(self._handler_response.callbackDelaySeconds)
            self._local_callback()
        if not self._is_local_callback() and self._is_callback():
            self._scheduler.reschedule(
                function_arn=self._context.invoked_function_arn,
                event=self._event,
                callback_context=self._handler_response.callbackContext,
                seconds=self._handler_response.callbackDelaySeconds,
            )

    def run_handler(self):
        try:
            logging.debug(self._handler_args)
            handler = self._get_handler()
            self._handler_response = handler(*self._handler_args)
            self._callback()
        except Exception as e:  # pylint: disable=broad-except
            LOG.error("unhandled exception", exc_info=True)
            self._metrics.exception(self._start_time, action=self._action, exception=e)
            self._handler_response.message = "{}: {}".format(type(e).__name__, str(e))
            self._handler_response.errorCode = (
                type(e).__name__ if Codes.is_handled(e) else Codes.INTERNAL_FAILURE
            )
        finally:
            try:
                self._metrics.duration(
                    self._start_time,
                    action=self._action,
                    duration=datetime.now() - self._start_time,
                )
                if is_sam_local():
                    LOG.warning(
                        "Not publishing CloudWatch metrics as invocation is SAM local"
                    )
                else:
                    self._metrics.publish()
            except Exception as e:  # pylint: disable=broad-except
                LOG.error(
                    "CloudWatch Metrics for this invocation have not been published"
                )
                LOG.error("unhandled exception", exc_info=True)
                self._handler_response.status = Status.FAILED
                self._handler_response.message = "{}: {}".format(
                    type(e).__name__, str(e)
                )
                self._handler_response.errorCode = (
                    type(e).__name__ if Codes.is_handled(e) else Codes.INTERNAL_FAILURE
                )
            return self._handler_response  # pylint: disable=lost-exception
