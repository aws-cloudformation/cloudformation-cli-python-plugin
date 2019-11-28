# pylint: disable=no-member
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import boto3
from cloudformation_cli_python_lib.interface import Action, MetricTypes, StandardUnit
from cloudformation_cli_python_lib.metrics import (
    MetricPublisher,
    MetricsPublisherProxy,
    format_dimensions,
)

from botocore.stub import Stubber


class MockSession:
    def __init__(self, client):
        self._client = client

    def client(self, _name):
        return self._client


def test_format_dimensions():
    dimensions = {"MyDimensionKey": "val_1", "MyDimensionKey2": "val_2"}
    result = format_dimensions(dimensions)
    assert [
        {"Name": "MyDimensionKey", "Value": "val_1"},
        {"Name": "MyDimensionKey2", "Value": "val_2"},
    ] == result


@patch("cloudformation_cli_python_lib.metrics.LOG", auto_spec=True)
def test_put_metric_catches_error(mock_logger):
    client = boto3.client("cloudwatch")
    stubber = Stubber(client)

    stubber.add_client_error("put_metric_data", "InternalServiceError")
    stubber.activate()

    publisher = MetricPublisher("123412341234", "Aa::Bb::Cc", MockSession(client))
    dimensions = {
        "DimensionKeyActionType": Action.CREATE.name,
        "DimensionKeyResourceType": publisher.resource_type,
    }
    publisher.publish_metric(
        MetricTypes.HandlerInvocationCount,
        dimensions,
        StandardUnit.Count,
        1.0,
        datetime.now(),
    )
    stubber.deactivate()
    expected_calls = [
        call.error(
            "An error occurred while publishing metrics: %s",
            "An error occurred (InternalServiceError) when calling the "
            "PutMetricData operation: ",
        )
    ]
    assert expected_calls == mock_logger.mock_calls


def test_publish_exception_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    fake_datetime = datetime(2019, 1, 1)
    publisher = MetricPublisher("123412341234", "Aa::Bb::Cc", mock_client.return_value)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(publisher)
    proxy.publish_exception_metric(fake_datetime, Action.CREATE, Exception("fake-err"))
    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123412341234/Aa/Bb/Cc",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerException.name,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "CREATE"},
                        {
                            "Name": "DimensionKeyExceptionType",
                            "Value": "<class 'Exception'>",
                        },
                        {"Name": "DimensionKeyResourceType", "Value": "Aa::Bb::Cc"},
                    ],
                    "Unit": StandardUnit.Count.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls


def test_publish_invocation_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    fake_datetime = datetime(2019, 1, 1)
    publisher = MetricPublisher("123412341234", "Aa::Bb::Cc", mock_client.return_value)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(publisher)
    proxy.publish_invocation_metric(fake_datetime, Action.CREATE)

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123412341234/Aa/Bb/Cc",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationCount.name,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "CREATE"},
                        {"Name": "DimensionKeyResourceType", "Value": "Aa::Bb::Cc"},
                    ],
                    "Unit": StandardUnit.Count.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls


def test_publish_duration_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    fake_datetime = datetime(2019, 1, 1)
    publisher = MetricPublisher("123412341234", "Aa::Bb::Cc", mock_client.return_value)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(publisher)
    proxy.publish_duration_metric(fake_datetime, Action.CREATE, 100)

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123412341234/Aa/Bb/Cc",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationDuration.name,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "CREATE"},
                        {"Name": "DimensionKeyResourceType", "Value": "Aa::Bb::Cc"},
                    ],
                    "Unit": StandardUnit.Milliseconds.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 100,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls


def test_publish_log_delivery_exception_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    fake_datetime = datetime(2019, 1, 1)
    publisher = MetricPublisher("123412341234", "Aa::Bb::Cc", mock_client.return_value)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(publisher)
    proxy.publish_log_delivery_exception_metric(fake_datetime, TypeError("test"))

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123412341234/Aa/Bb/Cc",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerException.name,
                    "Dimensions": [
                        {
                            "Name": "DimensionKeyActionType",
                            "Value": "ProviderLogDelivery",
                        },
                        {
                            "Name": "DimensionKeyExceptionType",
                            "Value": "<class 'TypeError'>",
                        },
                        {"Name": "DimensionKeyResourceType", "Value": "Aa::Bb::Cc"},
                    ],
                    "Unit": StandardUnit.Count.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls
