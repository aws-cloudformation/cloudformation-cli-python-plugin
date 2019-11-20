import logging
from enum import Enum

LOG = logging.getLogger(__name__)

def create_dimension(item):
    key, value = item
    return {
        'Name': key,
        'Value': value
    }

class MetricTypes(Enum):
    HANDLER_EXCEPTION='HandlerException'
    HANDLER_INVOCATION_COUNT='HandlerInvocationCount'
    HANDLER_INVOCATION_DURATION='HandlerInvocationDuration'

class MetricUnits(Enum):
    SECONDS='Seconds'
    MICROSECONDS='Microseconds'
    MILLISECONDS='Milliseconds'
    BYTES='Bytes'
    KILOBYTES='Kilobytes'

class StandardUnit(Enum):
    COUNT='Count'
    MILLISECONDS='Milliseconds'

class MetricPublisher:
    def __init__(self, namespace, session):
        self.namespace = namespace
        self.client = session.client('cloudwatch')

    def _publish_metric(self, metric_name, dimensions, unit, value, date):
        dimensions = map(create_dimension, dimensions.items())
        metric_data = dict(
            Namespace=self.namespace,
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': dimensions,
                    'Unit': unit,
                    'Timestamp': date
                }
            ]
        )
        try:
            return self.client.put_metric_data(**metric_data)
        except Exception as e:
            LOG.error(f'An error occurred while publishing metrics: {str(e)}')

    def publish_exception_metric(self, date, action, error) -> None:
        dimensions = {
            'DimensionKeyActionType': action,
            'DimensionKeyExceptionType': str(error),
            'DimensionKeyResourceType': self.namespace,
        }

        res = self._publish_metric(
            error_type=MetricTypes.HANDLER_EXCEPTION,
            dimensions=dimensions,
            unit=StandardUnit.COUNT,
            value=1.0,
            date=date
        )
        LOG.debug(res)

    def publish_invocation_metric(self, date, action) -> None:
        dimensions = {
            'DimensionKeyExceptionType': action,
            'DimensionKeyResourceType': self.namespace,
        }

        res = self._publish_metric(
            error_type=MetricTypes.HANDLER_INVOCATION_COUNT,
            dimensions=dimensions,
            unit=StandardUnit.COUNT,
            value=1.0,
            date=date
        )
        LOG.debug(res)

    def publish_duration_metric(self, date, action, milliseconds) -> None:
        dimensions = {
            'DimensionKeyExceptionType': action,
            'DimensionKeyResourceType': self.namespace,
        }

        res = self._publish_metric(
            error_type=MetricTypes.HANDLER_INVOCATION_DURATION,
            dimensions=dimensions,
            unit=StandardUnit.MILLISECONDS,
            value=milliseconds,
            date=date
        )
        LOG.debug(res)