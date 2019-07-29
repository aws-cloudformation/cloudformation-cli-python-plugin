import importlib
import logging
from datetime import datetime
from multiprocessing import Process
from threading import Timer
from time import sleep
from typing import Optional

from . import ProgressEvent, Status, exceptions, request
from .boto3_proxy import Boto3Client, get_boto3_proxy_session, get_boto_session_config
from .exceptions import Codes, InternalFailure, InvalidRequest
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


def _handler_wrapper(event, context):
    progress_event = ProgressEvent(Status.FAILED, resourceModel=ResourceModel())
    record_handler_progress = None
    timer = None
    try:
        level = get_log_level_from_env(LOG_LEVEL_ENV_VAR)
        boto_level = get_log_level_from_env(BOTO_LOG_LEVEL_ENV_VAR, logging.ERROR)
        setup_json_logger(level, boto_level, event)

        if not event["responseEndpoint"]:
            raise InvalidRequest("responseEndpoint is missing")
        record_handler_progress = _create_cfn_client(
            get_boto_session_config(event, "platformCredentials"),
            event["responseEndpoint"],
        ).record_handler_progress
        wrapper = HandlerWrapper(event, context, record_handler_progress)
        timer = wrapper.timer
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
        if timer:
            timer.cancel()
        _report_progress(event["bearerToken"], progress_event, record_handler_progress)
        return progress_event.json()  # pylint: disable=lost-exception


def _report_progress(bearer_token, progress_event, record_handler_progress):
    if progress_event.status != Status.IN_PROGRESS:
        return
    if not record_handler_progress:
        LOG.error("unable to report progress as client method is not defined")
        return
    try:
        response = record_handler_progress(
            BearerToken=bearer_token,
            OperationStatus=progress_event.status,
            StatusMessage=progress_event.message,
            ErrorCode=progress_event.errorCode,
            ResourceModel=progress_event.resourceModel,
        )
        LOG.debug(response)
    except Exception as e:  # pylint: disable=broad-except
        LOG.error("failed to submit RecordHandlerProgress response", exc_info=True)
        progress_event.status = Status.FAILED
        progress_event.errorCode = Codes.INTERNAL_FAILURE
        progress_event.message = str(e)


def _create_cfn_client(credentials, endpoint):
    session = Boto3Client(**credentials)
    return session.client("cloudformation", endpoint_url=f"https://{endpoint}")


class HandlerWrapper:  # pylint: disable=too-many-instance-attributes
    TIMEOUT_BUFFER = 2.5
    LOCAL_CALLBACK_BUFFER = 2.0
    HANDLER_MAX_EXECUTION_TIME = 60.0
    HANDLER_TIMEOUT_RETRIES = 3

    def __init__(self, event, context, record_handler_progress):
        self.progress: ProgressEvent = ProgressEvent(
            Status.FAILED, resourceModel=ResourceModel()
        )
        self._event = event
        self._context = context
        self._action = event["action"]
        self._session_config = get_boto_session_config(event, "platformCredentials")
        session_configs = [self._session_config]
        if "resourceOwnerLoggingCredentials" in event:
            session_configs.append(
                get_boto_session_config(event, "resourceOwnerLoggingCredentials")
            )
        self._metrics = Metrics(
            resource_type=event["resourceType"], session_configs=session_configs
        )
        self._handler_args = self._event_parse()
        self._scheduler = CloudWatchScheduler(self._session_config)
        self._scheduler.cleanup(event)
        self._record_handler_progress = record_handler_progress
        self._bearer_token = event["bearerToken"]
        self._handler_thread: Optional[Process] = None
        self._handler_timeout_count = 0
        self._timer = None
        self._invoke_start = None

    @property
    def timer(self):
        return self._timer

    def _timeout(self):
        LOG.error("Execution is about to time out")
        if self._handler_thread:
            self._handler_thread.terminate()
        self._handler_timeout_count += 1
        if self._handler_timeout_count < 3:
            self.progress.status = Status.IN_PROGRESS
            self.progress.message = "Handler timed out and is being re-invoked"
            self._callback()
        else:
            self.progress.status = Status.FAILED
            self.progress.message = "Resource timed out"
            self.progress.errorCode = exceptions.Codes.SERVICE_TIMEOUT

    def _set_timeout(self):
        if self._timer:
            self._timer.cancel()
        self._timer = Timer(self._timeout, self.HANDLER_MAX_EXECUTION_TIME)

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
        session_config = get_boto_session_config(self._event, "callerCredentials")
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
        if self.progress.callbackDelaySeconds > 60 or not self._is_callback():
            return False
        remaining = self._context.get_remaining_time_in_millis() / 1000
        needed = (
            self.progress.callbackDelaySeconds
            + self.HANDLER_MAX_EXECUTION_TIME
            + self.LOCAL_CALLBACK_BUFFER
        )
        remaining = remaining - self.TIMEOUT_BUFFER
        return needed < remaining

    def _is_callback(self):
        return self.progress.status == Status.IN_PROGRESS

    def _local_callback(self):
        self._handler_args[3] = self.progress.callbackContext
        self._handler_args[1].invocation_count += 1
        self.run_handler()

    def _callback(self):
        while self._is_local_callback():
            _report_progress(
                self._bearer_token, self.progress, self._record_handler_progress
            )
            sleep(self.progress.callbackDelaySeconds)
            self._local_callback()
        if self._is_callback():
            self._scheduler.reschedule(
                function_arn=self._context.invoked_function_arn,
                event=self._event,
                callback_context=self.progress.callbackContext,
                seconds=self.progress.callbackDelaySeconds,
            )

    def run_handler(self):
        self._metrics.invocation(datetime.now(), action=self._action)
        self._invoke_start = datetime.now()
        self._handler_thread = Process(target=self._run_handler_thread())
        self._handler_thread.start()
        self._set_timeout()
        self._handler_thread.join()
        return self.progress

    def _run_handler_thread(self):
        try:
            logging.debug(self._handler_args)
            handler = self._get_handler()
            self.progress = handler(*self._handler_args)
            self._callback()
        except Exception as e:  # pylint: disable=broad-except
            LOG.error("unhandled exception", exc_info=True)
            self._metrics.exception(datetime.now(), action=self._action, exception=e)
            self.progress.message = "{}: {}".format(type(e).__name__, str(e))
            self.progress.errorCode = (
                type(e).__name__ if Codes.is_handled(e) else Codes.INTERNAL_FAILURE
            )
        finally:
            try:
                self._metrics.duration(
                    self._invoke_start,
                    action=self._action,
                    duration=datetime.now() - self._invoke_start,
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
                self.progress.status = Status.FAILED
                self.progress.message = "{}: {}".format(type(e).__name__, str(e))
                self.progress.errorCode = (
                    type(e).__name__ if Codes.is_handled(e) else Codes.INTERNAL_FAILURE
                )
