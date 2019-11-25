# pylint: disable=redefined-outer-name,protected-access
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from cloudformation_cli_python_lib.scheduler import CloudWatchScheduler

from botocore.exceptions import ClientError


@pytest.fixture
def mock_boto3_session():
    return Mock("cloudformation_cli_python_lib.scheduler.Session", autospec=True)()


@pytest.fixture
def mock_handler_request():
    mock_request = Mock(
        "cloudformation_cli_python_lib.utils.HandlerRequest", autospec=True
    )()
    mock_request.requestContext = {}
    mock_request.serialize.return_value = {}
    return mock_request


def test_instantiates_boto3_client(mock_boto3_session):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)
    mock_boto3_session.client.assert_called_once_with("events")
    assert cw_scheduler.client == mock_boto3_session.client.return_value


@patch(
    "cloudformation_cli_python_lib.scheduler.CloudWatchScheduler._min_to_cron",
    return_value="cron('30 16 21 11 ? 2019')",
)
def test_reschedule_after_minutes_zero(
    mock_min_to_cron, mock_boto3_session, mock_handler_request
):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)

    # if called with zero, should call cron with a 1
    cw_scheduler.reschedule_after_minutes("arn:goes:here", 0, mock_handler_request)
    mock_min_to_cron.assert_called_once_with(1)


@patch(
    "cloudformation_cli_python_lib.scheduler.CloudWatchScheduler._min_to_cron",
    return_value="cron('30 16 21 11 ? 2019')",
)
def test_reschedule_after_minutes_not_zero(
    mock_min_to_cron, mock_boto3_session, mock_handler_request
):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)
    # if called with another number, should use that
    cw_scheduler.reschedule_after_minutes("arn:goes:here", 2, mock_handler_request)
    mock_min_to_cron.assert_called_once_with(2)


@patch(
    "cloudformation_cli_python_lib.scheduler.uuid4",
    autospec=True,
    return_value=str(uuid4()),
)
def test_reschedule_after_minutes_success(
    mock_uuid4, mock_boto3_session, mock_handler_request
):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)
    with patch(
        "cloudformation_cli_python_lib.scheduler.CloudWatchScheduler._min_to_cron",
        return_value="cron('30 16 21 11 ? 2019')",
    ):
        cw_scheduler.reschedule_after_minutes("arn:goes:here", 2, mock_handler_request)

    # should have made appropriate calls to create the schedule
    cw_scheduler.client.put_targets.assert_called_once_with(
        Rule=f"reinvoke-handler-{mock_uuid4.return_value}",
        Targets=[
            {
                "Id": f"reinvoke-target-{mock_uuid4.return_value}",
                "Arn": "arn:goes:here",
                "Input": "{}",
            }
        ],
    )
    cw_scheduler.client.put_rule.assert_called_once_with(
        Name=f"reinvoke-handler-{mock_uuid4.return_value}",
        ScheduleExpression="cron('30 16 21 11 ? 2019')",
        State="ENABLED",
    )


@patch("cloudformation_cli_python_lib.scheduler.LOG", autospec=True)
def test_cleanup_cloudwatch_events_empty(mock_logger, mock_boto3_session):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)

    # cleanup should silently pass if rule/target are empty
    cw_scheduler.cleanup_cloudwatch_events("", "")
    assert cw_scheduler.client.remove_targets.called is False
    assert cw_scheduler.client.delete_rule.called is False
    assert mock_logger.error.called is False


@patch("cloudformation_cli_python_lib.scheduler.LOG", autospec=True)
def test_cleanup_cloudwatch_events_success(mock_logger, mock_boto3_session):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)

    # when rule_name and target_id are provided we should call events client and not
    # log errors if the deletion succeeds
    cw_scheduler.cleanup_cloudwatch_events("rulename", "targetid")
    assert mock_logger.error.called is False
    cw_scheduler.client.remove_targets.assert_called_once()
    cw_scheduler.client.delete_rule.assert_called_once()


@patch("cloudformation_cli_python_lib.scheduler.LOG", autospec=True)
def test_cleanup_cloudwatch_events_boto_error(mock_logger, mock_boto3_session):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)

    # cleanup should catch and log boto failures
    err = ClientError(error_response={"Error": {"Code": "1"}}, operation_name="mock")
    cw_scheduler.client.remove_targets.side_effect = err
    cw_scheduler.client.delete_rule.side_effect = err
    cw_scheduler.cleanup_cloudwatch_events("rulename", "targetid")
    assert mock_logger.error.call_count == 2
    cw_scheduler.client.remove_targets.assert_called_once()
    cw_scheduler.client.delete_rule.assert_called_once()


@patch("cloudformation_cli_python_lib.scheduler.datetime", autospec=True)
def test__min_to_cron(mock_datetime):
    mock_datetime.now.return_value = datetime.fromisoformat("2019-01-01 01:01:01")
    cron = CloudWatchScheduler._min_to_cron(1)
    assert cron == "cron('03 01 01 01 ? 2019')"
