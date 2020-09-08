import logging
import time
from typing import Any, Optional

from .boto3_proxy import SessionProxy
from .utils import HandlerRequest


class ProviderFilter(logging.Filter):
    def __init__(self, provider: str):
        super().__init__()
        self.provider = provider

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(self.provider)


class ProviderLogHandler(logging.Handler):
    def __init__(
        self, group: str, stream: str, session: SessionProxy, *args: Any, **kwargs: Any
    ):
        super().__init__(*args, **kwargs)
        self.group = group
        self.stream = stream.replace(":", "__")
        self.client = session.client("logs")
        self.sequence_token = ""

    @classmethod
    def _get_existing_logger(cls) -> Optional["ProviderLogHandler"]:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, cls):
                return handler
        return None

    @classmethod
    def setup(
        cls, request: HandlerRequest, provider_sess: Optional[SessionProxy]
    ) -> None:
        log_group = request.requestData.providerLogGroupName
        if request.stackId and request.requestData.logicalResourceId:
            stream_name = f"{request.stackId}/{request.requestData.logicalResourceId}"
        else:
            stream_name = f"{request.awsAccountId}-{request.region}"

        log_handler = cls._get_existing_logger()
        if provider_sess and log_group and request.resourceType:
            if log_handler:
                # This is a re-used lambda container, log handler is already setup, so
                # we just refresh the client with new creds
                log_handler.client = provider_sess.client("logs")
                return
            # filter provider messages from platform
            provider = request.resourceType.replace("::", "_").lower()
            logging.getLogger().handlers[0].addFilter(ProviderFilter(provider))
            log_handler = cls(
                group=log_group, stream=stream_name, session=provider_sess
            )
            # add log handler to root, so that provider gets plugin logs too
            logging.getLogger().addHandler(log_handler)

    def _create_log_group(self) -> None:
        try:
            self.client.create_log_group(logGroupName=self.group)
        except self.client.exceptions.ResourceAlreadyExistsException:
            pass

    def _create_log_stream(self) -> None:
        try:
            self.client.create_log_stream(
                logGroupName=self.group, logStreamName=self.stream
            )
        except self.client.exceptions.ResourceAlreadyExistsException:
            pass

    def _put_log_event(self, msg: logging.LogRecord) -> None:
        kwargs = {
            "logGroupName": self.group,
            "logStreamName": self.stream,
            "logEvents": [
                {"timestamp": round(time.time() * 1000), "message": self.format(msg)}
            ],
        }
        if self.sequence_token:
            kwargs["sequenceToken"] = self.sequence_token
        try:
            self.sequence_token = self.client.put_log_events(**kwargs)[
                "nextSequenceToken"
            ]
        except (
            self.client.exceptions.DataAlreadyAcceptedException,
            self.client.exceptions.InvalidSequenceTokenException,
        ) as e:
            self.sequence_token = str(e).split(" ")[-1]
            self._put_log_event(msg)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._put_log_event(record)
        except self.client.exceptions.ResourceNotFoundException as e:
            if "log group does not exist" in str(e):
                self._create_log_group()
            self._create_log_stream()
            self._put_log_event(record)
