import datetime
import logging
from typing import Any, List, Mapping

# boto3 doesn't have stub files
from boto3.session import Session  # type: ignore

from botocore.exceptions import ClientError  # type: ignore

from .interface import Action, MetricTypes, StandardUnit

LOG = logging.getLogger(__name__)

METRIC_NAMESPACE_ROOT = "AWS/CloudFormation"


def format_dimensions(dimensions: Mapping[str, str]) -> List[Mapping[str, str]]:
    return [{"Name": key, "Value": value} for key, value in dimensions.items()]


class MetricPublisher:
    def __init__(self, account_id: str, resource_type: str, session: Session) -> None:
        suffix = resource_type.replace("::", "/")
        self.namespace = f"{METRIC_NAMESPACE_ROOT}/{account_id}/{suffix}"
        self.resource_type = resource_type
        self.client = session.client("cloudwatch")

    def publish_metric(  # pylint: disable-msg=too-many-arguments
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
                        "MetricName": metric_name.name,
                        "Dimensions": format_dimensions(dimensions),
                        "Unit": unit.name,
                        "Timestamp": str(timestamp),
                        "Value": value,
                    }
                ],
            )

        except ClientError as e:
            LOG.error("An error occurred while publishing metrics: %s", str(e))


class MetricsPublisherProxy:
    def __init__(self) -> None:
        self._publishers: List[MetricPublisher] = []

    def add_metrics_publisher(self, publisher: MetricPublisher) -> None:
        self._publishers.append(publisher)

    def publish_exception_metric(
        self, timestamp: datetime.datetime, action: Action, error: Any
    ) -> None:
        for publisher in self._publishers:
            dimensions: Mapping[str, str] = {
                "DimensionKeyActionType": action.name,
                "DimensionKeyExceptionType": str(type(error)),
                "DimensionKeyResourceType": publisher.resource_type,
            }
            publisher.publish_metric(
                metric_name=MetricTypes.HandlerException,
                dimensions=dimensions,
                unit=StandardUnit.Count,
                value=1.0,
                timestamp=timestamp,
            )

    def publish_invocation_metric(
        self, timestamp: datetime.datetime, action: Action
    ) -> None:
        for publisher in self._publishers:
            dimensions = {
                "DimensionKeyActionType": action.name,
                "DimensionKeyResourceType": publisher.resource_type,
            }
            publisher.publish_metric(
                metric_name=MetricTypes.HandlerInvocationCount,
                dimensions=dimensions,
                unit=StandardUnit.Count,
                value=1.0,
                timestamp=timestamp,
            )

    def publish_duration_metric(
        self, timestamp: datetime.datetime, action: Action, milliseconds: float
    ) -> None:
        for publisher in self._publishers:
            dimensions = {
                "DimensionKeyActionType": action.name,
                "DimensionKeyResourceType": publisher.resource_type,
            }
            publisher.publish_metric(
                metric_name=MetricTypes.HandlerInvocationDuration,
                dimensions=dimensions,
                unit=StandardUnit.Milliseconds,
                value=milliseconds,
                timestamp=timestamp,
            )

    def publish_log_delivery_exception_metric(
        self, timestamp: datetime.datetime, error: Any
    ) -> None:
        for publisher in self._publishers:
            dimensions: Mapping[str, str] = {
                "DimensionKeyActionType": "ProviderLogDelivery",
                "DimensionKeyExceptionType": str(type(error)),
                "DimensionKeyResourceType": publisher.resource_type,
            }
            publisher.publish_metric(
                metric_name=MetricTypes.HandlerException,
                dimensions=dimensions,
                unit=StandardUnit.Count,
                value=1.0,
                timestamp=timestamp,
            )
