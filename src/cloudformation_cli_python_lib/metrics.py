import logging
from typing import Any, Mapping

# boto3 doesn't have stub files
from boto3.session import Session  # type: ignore

from botocore.exceptions import ClientError  # type: ignore

from .interface import Action, MetricTypes, StandardUnit

LOG = logging.getLogger(__name__)

print(__name__)


def format_dimensions(dimensions: Mapping[Any, Any]) -> Any:  # TODO fix type
    formatted_dimensions = []
    for key, value in dimensions.items():
        formatted_dimensions.append({"Name": key, "Value": value})
    return formatted_dimensions


class MetricPublisher:
    def __init__(self, namespace: str, session: Session) -> None:
        self.namespace = namespace
        self.client = session.client("cloudwatch")

    def _publish_metric(  # pylint: disable-msg=too-many-arguments
        self,
        metric_name: MetricTypes,
        dimensions: Mapping[Any, Any],  # TODO: fix type
        unit: StandardUnit,
        value: Any,
        date: float,
    ) -> None:
        dimensions = format_dimensions(dimensions)
        try:
            res = self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Dimensions": dimensions,
                        "Unit": unit,
                        "Timestamp": date,
                        "Value": value,
                    }
                ],
            )
            print(__name__, LOG)
            LOG.debug(res)

        except ClientError as e:
            LOG.error("An error occurred while publishing metrics: %s", str(e))

    def publish_exception_metric(self, date: float, action: Action, error: Any) -> None:
        dimensions = {
            "DimensionKeyActionType": action,
            "DimensionKeyExceptionType": str(error),
            "DimensionKeyResourceType": self.namespace,
        }

        self._publish_metric(
            metric_name=MetricTypes.HandlerException,
            dimensions=dimensions,
            unit=StandardUnit.Count,
            value=1.0,
            date=date,
        )

    def publish_invocation_metric(self, date: float, action: Action) -> None:
        dimensions = {
            "DimensionKeyActionType": action,
            "DimensionKeyResourceType": self.namespace,
        }

        self._publish_metric(
            metric_name=MetricTypes.HandlerInvocationCount,
            dimensions=dimensions,
            unit=StandardUnit.Count,
            value=1.0,
            date=date,
        )

    def publish_duration_metric(
        self, date: float, action: Action, milliseconds: float
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
            date=date,
        )
