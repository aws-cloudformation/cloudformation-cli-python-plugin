import logging
from datetime import datetime, timedelta
from typing import List

from .boto3_proxy import Boto3Client

LOG = logging.getLogger(__name__)


class Metrics:
    METRIC_NAMESPACE_ROOT = "AWS_TMP/CloudFormation"
    METRIC_NAME_HANDLER_EXCEPTION = "HandlerException"
    METRIC_NAME_HANDLER_DURATION = "HandlerInvocationDuration"
    METRIC_NAME_HANDLER_INVOCATION_COUNT = "HandlerInvocationCount"
    DIMENSION_KEY_ACTION_TYPE = "Action"
    DIMENSION_KEY_EXCEPTION_TYPE = "ExceptionType"
    DIMENSION_KEY_RESOURCE_TYPE = "ResourceType"

    def __init__(self, resource_type: str, session_config: dict = None, b3=Boto3Client):
        if session_config is None:
            session_config = {}
        self.resource_type = resource_type
        self.namespace = "{}/{}".format(
            Metrics.METRIC_NAMESPACE_ROOT, resource_type.replace("::", "/")
        )
        self._cw_client = b3(**session_config).client("cloudwatch")
        self.data: List[dict] = []

    def _reset_data(self):
        self.data = []

    def exception(self, timestamp: datetime, action: str, exception: Exception):
        self.data.append(
            {
                "MetricName": Metrics.METRIC_NAME_HANDLER_EXCEPTION,
                "Dimensions": [
                    {"Name": Metrics.DIMENSION_KEY_ACTION_TYPE, "Value": action},
                    {
                        "Name": Metrics.DIMENSION_KEY_EXCEPTION_TYPE,
                        "Value": type(exception).__name__,
                    },
                    {
                        "Name": Metrics.DIMENSION_KEY_RESOURCE_TYPE,
                        "Value": self.resource_type,
                    },
                ],
                "Timestamp": timestamp,
                "Value": 1.0,
                "Unit": "Count",
            }
        )

    def invocation(self, timestamp: datetime, action: str):
        self.data.append(
            {
                "MetricName": Metrics.METRIC_NAME_HANDLER_INVOCATION_COUNT,
                "Dimensions": [
                    {"Name": Metrics.DIMENSION_KEY_ACTION_TYPE, "Value": action},
                    {
                        "Name": Metrics.DIMENSION_KEY_RESOURCE_TYPE,
                        "Value": self.resource_type,
                    },
                ],
                "Timestamp": timestamp,
                "Value": 1.0,
                "Unit": "Count",
            }
        )

    def duration(self, timestamp: datetime, action: str, duration: timedelta):
        ms_elapsed = int(round(duration.total_seconds() * 1000))
        self.data.append(
            {
                "MetricName": Metrics.METRIC_NAME_HANDLER_DURATION,
                "Dimensions": [
                    {"Name": Metrics.DIMENSION_KEY_ACTION_TYPE, "Value": action},
                    {
                        "Name": Metrics.DIMENSION_KEY_RESOURCE_TYPE,
                        "Value": self.resource_type,
                    },
                ],
                "Timestamp": timestamp,
                "Value": ms_elapsed,
                "Unit": "Milliseconds",
            }
        )

    def publish(self):
        LOG.debug(self.data)
        if not self.data:
            LOG.warning("No metrics available to publish")
            return
        self._cw_client.put_metric_data(Namespace=self.namespace, MetricData=self.data)
        self._reset_data()
