# pylint: disable=redefined-outer-name,protected-access
from unittest.mock import Mock, patch
from uuid import uuid4

import boto3
from cloudformation_cli_python_lib.callback import report_progress
from cloudformation_cli_python_lib.interface import (
    BaseModel,
    HandlerErrorCode,
    OperationStatus,
)


class MockSession:
    def __init__(self):
        self._cfn = Mock(boto3.client("cloudformation"), autospec=True)
        self._cfn.record_handler_progress.return_value = {
            "ResponseMetadata": {"RequestId": "mock_request"}
        }

    def client(self, _name):
        return self._cfn


def test_report_progress_minimal():
    session = MockSession()
    uuid = uuid4()
    with patch("cloudformation_cli_python_lib.callback.uuid4", return_value=uuid):
        report_progress(
            session, "123", None, OperationStatus.IN_PROGRESS, None, None, ""
        )
    session._cfn.record_handler_progress.assert_called_once_with(
        BearerToken="123",
        OperationStatus="IN_PROGRESS",
        StatusMessage="",
        ClientRequestToken=str(uuid),
    )


def test_report_progress_full():
    session = MockSession()
    uuid = uuid4()
    with patch("cloudformation_cli_python_lib.callback.uuid4", return_value=uuid):
        report_progress(
            session,
            "123",
            HandlerErrorCode.InternalFailure,
            OperationStatus.FAILED,
            OperationStatus.IN_PROGRESS,
            BaseModel(),
            "test message",
        )
    session._cfn.record_handler_progress.assert_called_once_with(
        BearerToken="123",
        OperationStatus="FAILED",
        CurrentOperationStatus="IN_PROGRESS",
        StatusMessage="test message",
        ResourceModel="{}",
        ErrorCode="InternalFailure",
        ClientRequestToken=str(uuid),
    )
