# auto enums `.name` causes no-member
# pylint: disable=redefined-outer-name,no-member,protected-access
import pytest
from cloudformation_cli_python_lib.interface import (
    Action,
    HookInvocationPoint,
    MetricTypes,
    StandardUnit,
)
from cloudformation_cli_python_lib.metrics import (
    HookMetricsPublisher,
    MetricsPublisher,
    MetricsPublisherProxy,
    format_dimensions,
)

import botocore.errorfactory
import botocore.session
from datetime import datetime
from unittest.mock import Mock, call, patch

cloudwatch_model = botocore.session.get_session().get_service_model("cloudwatch")
factory = botocore.errorfactory.ClientExceptionsFactory()
cloudwatch_exceptions = factory.create_client_exceptions(cloudwatch_model)


ACCOUNT_ID = "123456789012"
RESOURCE_TYPE = "Aa::Bb::Cc"
RESOURCE_NAMESPACE = MetricsPublisher._make_namespace(RESOURCE_TYPE)
HOOK_TYPE = "De::Ee::Ff"
HOOK_NAMESPACE = HookMetricsPublisher._make_hook_namespace(HOOK_TYPE, ACCOUNT_ID)


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
    client = mock_session.client("cloudwatch")
    client.exceptions = cloudwatch_exceptions
    mock_put = client.put_metric_data
    mock_put.return_value = {}
    mock_put.side_effect = [
        cloudwatch_exceptions.InternalServiceFault(
            {"Error": {"Code": "InternalServiceError", "Message": ""}},
            operation_name="PutMetricData",
        ),
    ]

    mock_session.client.return_value = client

    publisher = MetricsPublisher(mock_session, RESOURCE_NAMESPACE)
    dimensions = {
        "DimensionKeyActionType": Action.CREATE.name,
        "DimensionKeyResourceType": RESOURCE_TYPE,
    }

    with patch(
        "cloudformation_cli_python_lib.metrics.LOG", autospec=True
    ) as mock_logger:
        publisher.publish_metric(
            MetricTypes.HandlerInvocationCount,
            dimensions,
            StandardUnit.Count,
            1.0,
            datetime.now(),
        )

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


def test_put_hook_metric_catches_error(mock_session):
    client = mock_session.client("cloudwatch")
    client.exceptions = cloudwatch_exceptions
    mock_put = client.put_metric_data
    mock_put.return_value = {}
    mock_put.side_effect = [
        cloudwatch_exceptions.InternalServiceFault(
            {"Error": {"Code": "InternalServiceError", "Message": ""}},
            operation_name="PutMetricData",
        ),
    ]

    mock_session.client.return_value = client

    publisher = HookMetricsPublisher(mock_session, HOOK_NAMESPACE, ACCOUNT_ID)
    dimensions = {
        "DimensionKeyInvocationPointType": HookInvocationPoint.CREATE_PRE_PROVISION,
        "DimensionKeyHookType": HOOK_TYPE,
    }

    with patch(
        "cloudformation_cli_python_lib.metrics.LOG", autospec=True
    ) as mock_logger:
        publisher.publish_metric(
            MetricTypes.HandlerInvocationCount,
            dimensions,
            StandardUnit.Count,
            1.0,
            datetime.now(),
        )

    expected_calls = [
        call.error(
            "An error occurred while publishing metrics: %s",
            "An error occurred (InternalServiceError) when calling the "
            "PutMetricData operation: ",
        )
    ]
    assert mock_logger.mock_calls == expected_calls


def test_publish_hook_exception_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_hook_metrics_publisher(mock_session, HOOK_TYPE, ACCOUNT_ID)
    proxy.publish_exception_metric(
        fake_datetime, HookInvocationPoint.CREATE_PRE_PROVISION, Exception("fake-err")
    )
    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123456789012/De/Ee/Ff",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerException.name,
                    "Dimensions": [
                        {
                            "Name": "DimensionKeyInvocationPointType",
                            "Value": "CREATE_PRE_PROVISION",
                        },
                        {
                            "Name": "DimensionKeyExceptionType",
                            "Value": "<class 'Exception'>",
                        },
                        {"Name": "DimensionKeyHookType", "Value": "De::Ee::Ff"},
                    ],
                    "Unit": StandardUnit.Count.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert mock_session.mock_calls == expected_calls


def test_publish_hook_invocation_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_hook_metrics_publisher(mock_session, HOOK_TYPE, ACCOUNT_ID)
    proxy.publish_invocation_metric(
        fake_datetime, HookInvocationPoint.CREATE_PRE_PROVISION
    )

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123456789012/De/Ee/Ff",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationCount.name,
                    "Dimensions": [
                        {
                            "Name": "DimensionKeyInvocationPointType",
                            "Value": "CREATE_PRE_PROVISION",
                        },
                        {"Name": "DimensionKeyHookType", "Value": "De::Ee::Ff"},
                    ],
                    "Unit": StandardUnit.Count.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 1.0,
                }
            ],
        ),
    ]
    assert mock_session.mock_calls == expected_calls


def test_publish_hook_duration_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_hook_metrics_publisher(mock_session, HOOK_TYPE, ACCOUNT_ID)
    proxy.publish_duration_metric(
        fake_datetime, HookInvocationPoint.CREATE_PRE_PROVISION, 100
    )

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123456789012/De/Ee/Ff",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerInvocationDuration.name,
                    "Dimensions": [
                        {
                            "Name": "DimensionKeyInvocationPointType",
                            "Value": "CREATE_PRE_PROVISION",
                        },
                        {"Name": "DimensionKeyHookType", "Value": "De::Ee::Ff"},
                    ],
                    "Unit": StandardUnit.Milliseconds.name,
                    "Timestamp": str(fake_datetime),
                    "Value": 100,
                }
            ],
        ),
    ]
    assert mock_session.mock_calls == expected_calls


def test_publish_hook_log_delivery_exception_metric(mock_session):
    fake_datetime = datetime(2019, 1, 1)
    proxy = MetricsPublisherProxy()
    proxy.add_hook_metrics_publisher(mock_session, HOOK_TYPE, ACCOUNT_ID)
    proxy.publish_log_delivery_exception_metric(fake_datetime, TypeError("test"))

    expected_calls = [
        call.client("cloudwatch"),
        call.client().put_metric_data(
            Namespace="AWS/CloudFormation/123456789012/De/Ee/Ff",
            MetricData=[
                {
                    "MetricName": MetricTypes.HandlerException.name,
                    "Dimensions": [
                        {
                            "Name": "DimensionKeyInvocationPointType",
                            "Value": "ProviderLogDelivery",
                        },
                        {
                            "Name": "DimensionKeyExceptionType",
                            "Value": "<class 'TypeError'>",
                        },
                        {"Name": "DimensionKeyHookType", "Value": "De::Ee::Ff"},
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
    proxy.add_hook_metrics_publisher(None, None, None)
    assert not proxy._publishers  # pylint: disable=protected-access
