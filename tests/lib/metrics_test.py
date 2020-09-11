# auto enums `.name` causes no-member
# pylint: disable=redefined-outer-name,no-member
from datetime import datetime
from unittest.mock import Mock, call, patch

import boto3
import pytest
from cloudformation_cli_python_lib.interface import Action, MetricTypes, StandardUnit
from cloudformation_cli_python_lib.metrics import (
    MetricsPublisher,
    MetricsPublisherProxy,
    format_dimensions,
)

from botocore.stub import Stubber  # pylint: disable=C0411

RESOURCE_TYPE = "Aa::Bb::Cc"
NAMESPACE = MetricsPublisher._make_namespace(  # pylint: disable=protected-access
    RESOURCE_TYPE
)


@pytest.fixture
def mock_session():
    return Mock(spec_set=["client"])


def test_format_dimensions():
    dimensions = {"MyDimensionKey": "val_1", "MyDimensionKey2": "val_2"}
    result = format_dimensions(dimensions)
    assert result == [
        {"Name": "MyDimensionKey", "Value": "val_1"},
        {"Name": "MyDimensionKey2", "Value": "val_2"},
    ]


def test_put_metric_catches_error(mock_session):
    client = boto3.client("cloudwatch")
    stubber = Stubber(client)

    stubber.add_client_error("put_metric_data", "InternalServiceError")
    stubber.activate()

    mock_session.client.return_value = client

    publisher = MetricsPublisher(mock_session, NAMESPACE)
    dimensions = {
        "DimensionKeyActionType": Action.CREATE.name,
        "DimensionKeyResourceType": RESOURCE_TYPE,
    }

    with patch(
        "cloudformation_cli_python_lib.metrics.LOG", auto_spec=True
    ) as mock_logger:
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
    assert mock_logger.mock_calls == expected_calls


def test_publish_exception_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(mock_session, RESOURCE_TYPE)
    proxy.publish_exception_metric(fake_datetime, Action.CREATE, Exception("fake-err"))
    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/Aa/Bb/Cc",
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
    assert mock_session.mock_calls == expected_calls


def test_publish_invocation_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(mock_session, RESOURCE_TYPE)
    proxy.publish_invocation_metric(fake_datetime, Action.CREATE)

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/Aa/Bb/Cc",
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
    assert mock_session.mock_calls == expected_calls


def test_publish_duration_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(mock_session, RESOURCE_TYPE)
    proxy.publish_duration_metric(fake_datetime, Action.CREATE, 100)

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/Aa/Bb/Cc",
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
    assert mock_session.mock_calls == expected_calls


def test_publish_log_delivery_exception_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(mock_session, RESOURCE_TYPE)
    proxy.publish_log_delivery_exception_metric(fake_datetime, TypeError("test"))

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/Aa/Bb/Cc",
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
    assert mock_session.mock_calls == expected_calls


def test_metrics_publisher_proxy_add_metrics_publisher_none_safe():
    proxy = MetricsPublisherProxy()
    proxy.add_metrics_publisher(None, None)
    assert proxy._publishers == []  # pylint: disable=protected-access
