import logging
import time
from typing import Any, Mapping, Optional

# boto3 doesn't have stub files
import boto3  # type: ignore


class ProviderFilter(logging.Filter):
    PROVIDER = ""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(self.PROVIDER)


class ProviderLogHandler(logging.Handler):
    def __init__(
        self,
        group: str,
        stream: str,
        creds: Mapping[str, str],
        *args: Any,
        **kwargs: Any,
    ):
        super(ProviderLogHandler, self).__init__(*args, **kwargs)
        self.group = group
        self.stream = stream.replace(":", "__")
        self.client = boto3.client("logs", **creds)
        self.sequence_token = ""

    @classmethod
    def _get_existing_logger(cls) -> Optional["ProviderLogHandler"]:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, cls):
                return handler
        return None

    @classmethod
    def setup(cls, event_data: Mapping[str, Any]) -> None:
        try:
            log_creds = event_data["requestData"]["providerCredentials"]
        except KeyError:
            log_creds = {}
        try:
            log_group = event_data["requestData"]["providerLogGroupName"]
        except KeyError:
            log_group = ""
        try:
            stream_name = (
                f'{event_data["stackId"]}/'
                f'{event_data["requestData"]["logicalResourceId"]}'
            )
        except KeyError:
            stream_name = f'{event_data["awsAccountId"]}-{event_data["region"]}'

        log_handler = cls._get_existing_logger()
        if log_creds and log_group:
            if log_handler:
                # This is a re-used lambda container, log handler is already setup, so
                # we just refresh the client with new creds
                log_handler.client = boto3.client(
                    "logs",
                    aws_access_key_id=log_creds["accessKeyId"],
                    aws_secret_access_key=log_creds["secretAccessKey"],
                    aws_session_token=log_creds["sessionToken"],
                )
                return
            # filter provider messages from platform
            ProviderFilter.PROVIDER = (
                event_data["resourceType"].replace("::", "_").lower()
            )
            logging.getLogger().handlers[0].addFilter(ProviderFilter())
            log_handler = cls(
                group=log_group,
                stream=stream_name,
                creds={
                    "aws_access_key_id": log_creds["accessKeyId"],
                    "aws_secret_access_key": log_creds["secretAccessKey"],
                    "aws_session_token": log_creds["sessionToken"],
                },
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
