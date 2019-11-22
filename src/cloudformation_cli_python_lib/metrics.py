import datetime
import logging
from typing import Any, List, Mapping

# boto3 doesn't have stub files
from boto3.session import Session  # type: ignore

from botocore.exceptions import ClientError  # type: ignore

from .interface import Action, MetricTypes, StandardUnit

LOG = logging.getLogger(__name__)


def format_dimensions(dimensions: Mapping[str, str]) -> List[Mapping[str, str]]:
    return [{"Name": key, "Value": value} for key, value in dimensions.items()]


class MetricPublisher:
    def __init__(self, namespace: str, session: Session) -> None:
        self.namespace = namespace
        self.client = session.client("cloudwatch")

    def _publish_metric(  # pylint: disable-msg=too-many-arguments
        self,
        metric_name: MetricTypes,
        dimensions: Mapping[str, str],
        unit: StandardUnit,
        value: float,
        timestamp: datetime.datetime,
    ) -> None:
        try:
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Dimensions": format_dimensions(dimensions),
                        "Unit": unit,
                        "Timestamp": str(timestamp),
                        "Value": value,
                    }
                ],
            )

        except ClientError as e:
            LOG.error("An error occurred while publishing metrics: %s", str(e))

    def publish_exception_metric(
        self, timestamp: datetime.datetime, action: Action, error: Any
    ) -> None:
        dimensions: Mapping[str, str] = {
            "DimensionKeyActionType": action,
            "DimensionKeyExceptionType": str(type(error)),
            "DimensionKeyResourceType": self.namespace,
        }

        self._publish_metric(
            metric_name=MetricTypes.HandlerException,
            dimensions=dimensions,
            unit=StandardUnit.Count,
            value=1.0,
            timestamp=timestamp,
        )

    def publish_invocation_metric(
        self, timestamp: datetime.datetime, action: Action
    ) -> None:
        dimensions = {
            "DimensionKeyActionType": action,
            "DimensionKeyResourceType": self.namespace,
        }

        self._publish_metric(
            metric_name=MetricTypes.HandlerInvocationCount,
            dimensions=dimensions,
            unit=StandardUnit.Count,
            value=1.0,
            timestamp=timestamp,
        )

    def publish_duration_metric(
        self, timestamp: datetime.datetime, action: Action, milliseconds: float
    ) -> None:
        dimensions = {
            "DimensionKeyActionType": action,
            "DimensionKeyResourceType": self.namespace,
        }

        self._publish_metric(
            metric_name=MetricTypes.HandlerInvocationDuration,
            dimensions=dimensions,
            unit=StandardUnit.Milliseconds,
            value=milliseconds,
            timestamp=timestamp,
        )
