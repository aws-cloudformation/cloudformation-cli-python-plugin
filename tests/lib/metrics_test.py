import time
from unittest.mock import MagicMock, call, patch

import boto3
from cloudformation_cli_python_lib.interface import MetricTypes, StandardUnit
from cloudformation_cli_python_lib.metrics import MetricPublisher, format_dimensions

from botocore.stub import Stubber

# TODO convert patch to fixture


class MockSession:
    def __init__(self, client):
        self._client = client

    def client(self, name):  # pylint: disable-msg=unused-argument
        return self._client


class MockLog:
    def __init__(self, handler):
        self.debug = handler


def test_format_dimensions():
    dimensions = {"MyDimensionKey": "val_1", "MyDimensionKey2": "val_2"}
    result = format_dimensions(dimensions)
    assert [
        {"Name": "MyDimensionKey", "Value": "val_1"},
        {"Name": "MyDimensionKey2", "Value": "val_2"},
    ] == result


# TODO actually do assertions on this test
def test_put_metric_catches_error():
    client = boto3.client("cloudwatch")
    stubber = Stubber(client)

    stubber.add_client_error("put_metric_data", "InternalServiceError")
    stubber.activate()

    publisher = MetricPublisher("fake-namespace", MockSession(client))
    publisher.publish_exception_metric(time.time(), "CREATE", "fake-error")
    stubber.deactivate()


def test_publish_exception_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    publisher = MetricPublisher("fake-namespace", mock_client.return_value)
    publisher.publish_exception_metric("fake-date", "fake-action", "fake-error")

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="fake-namespace",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerException,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "fake-action"},
                        {"Name": "DimensionKeyExceptionType", "Value": "fake-error"},
                        {"Name": "DimensionKeyResourceType", "Value": "fake-namespace"},
                    ],
                    "Unit": StandardUnit.Count,
                    "Timestamp": "fake-date",
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls


def test_publish_invocation_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    publisher = MetricPublisher("fake-namespace", mock_client.return_value)
    publisher.publish_invocation_metric("fake-date", "fake-action")

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="fake-namespace",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationCount,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "fake-action"},
                        {"Name": "DimensionKeyResourceType", "Value": "fake-namespace"},
                    ],
                    "Unit": StandardUnit.Count,
                    "Timestamp": "fake-date",
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls


def test_publish_duration_metric():
    mock_client = patch("boto3.client")
    mock_client.return_value = MagicMock()

    publisher = MetricPublisher("fake-namespace", mock_client.return_value)
    publisher.publish_duration_metric("fake-date", "fake-action", 100)

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="fake-namespace",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationDuration,
                    "Dimensions": [
                        {"Name": "DimensionKeyActionType", "Value": "fake-action"},
                        {"Name": "DimensionKeyResourceType", "Value": "fake-namespace"},
                    ],
                    "Unit": StandardUnit.Milliseconds,
                    "Timestamp": "fake-date",
                    "Value": 100,
                }
            ],
        ),
    ]
    assert expected_calls == mock_client.return_value.mock_calls
