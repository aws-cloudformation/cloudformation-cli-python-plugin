# pylint: disable=redefined-outer-name,protected-access
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from cloudformation_cli_python_lib.scheduler import CloudWatchScheduler


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
    mock_boto3_session.client.assert_called_once_with(("events"))
    assert cw_scheduler.client == mock_boto3_session.client.return_value


@patch(
    "cloudformation_cli_python_lib.scheduler.CloudWatchScheduler._min_to_cron",
    return_value="cron('30 16 21 11 ? 2019')",
)
@patch(
    "cloudformation_cli_python_lib.scheduler.uuid4", autospec=True, return_value=uuid4()
)
def test_reschedule_after_minutes(
    mock_uuid4, mock_min_to_cron, mock_boto3_session, mock_handler_request
):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)
    # if called with zero, should call cron with a 1
    cw_scheduler.reschedule_after_minutes("arn:goes:here", 0, mock_handler_request)
    mock_min_to_cron.assert_called_once_with(1)
    mock_min_to_cron.reset_mock()
    cw_scheduler.client.reset_mock()

    # if called with another number, should use that
    cw_scheduler.reschedule_after_minutes("arn:goes:here", 2, mock_handler_request)
    mock_min_to_cron.assert_called_once_with(2)

    # should have made appropriate calls to create the schedule
    cw_scheduler.client.put_targets.assert_called_once_with(
        Rule=f"reinvoke-handler-{mock_uuid4.return_value.hex}",
        Targets=[
            {
                "Id": f"reinvoke-target-{mock_uuid4.return_value.hex}",
                "Arn": "arn:goes:here",
                "Input": "{}",
            }
        ],
    )
    cw_scheduler.client.put_rule.assert_called_once_with(
        Name=f"reinvoke-handler-{mock_uuid4.return_value.hex}",
        ScheduleExpression="cron('30 16 21 11 ? 2019')",
        State="ENABLED",
    )


@patch("cloudformation_cli_python_lib.scheduler.LOG", autospec=True)
def test_cleanup_cloudwatch_events(mock_logger, mock_boto3_session):
    cw_scheduler = CloudWatchScheduler(boto3_session=mock_boto3_session)

    # cleanup should silently pass if rule/target are empty
    cw_scheduler.cleanup_cloudwatch_events("", "")
    assert cw_scheduler.client.remove_targets.called is False
    assert cw_scheduler.client.delete_rule.called is False
    assert mock_logger.error.called is False

    # when rule_name and target_id are provided we should call events client and not
    # log errors if the deletion succeeds
    cw_scheduler.cleanup_cloudwatch_events("rulename", "targetid")
    assert mock_logger.error.called is False
    cw_scheduler.client.remove_targets.assert_called_once()
    cw_scheduler.client.delete_rule.assert_called_once()
    cw_scheduler.client.remove_targets.reset_mock()
    cw_scheduler.client.delete_rule.reset_mock()

    # cleanup should catch and log boto failures
    cw_scheduler.client.remove_targets.side_effect = Exception("raised")
    cw_scheduler.client.delete_rule.side_effect = Exception("raised")
    cw_scheduler.cleanup_cloudwatch_events("rulename", "targetid")
    assert mock_logger.error.call_count == 2
    cw_scheduler.client.remove_targets.assert_called_once()
    cw_scheduler.client.delete_rule.assert_called_once()


@patch("cloudformation_cli_python_lib.scheduler.datetime", autospec=True)
def test__min_to_cron(mock_datetime):
    mock_datetime.now.return_value = datetime.fromisoformat("2019-01-01 01:01:01")
    cron = CloudWatchScheduler._min_to_cron(1)
    assert cron == "cron('03 01 01 01 ? 2019')"
