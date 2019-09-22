# pylint: disable=protected-access,redefined-outer-name
import json
from string import ascii_letters

import boto3
import pytest
from aws_cloudformation_rpdk_python_lib.interface import (
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)

import hypothesis.strategies as s
from hypothesis import given


@pytest.fixture
def client():
    return boto3.client(
        "cloudformation",
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_session_token="",
        region_name="us-east-1",
    )


@given(s.sampled_from(HandlerErrorCode), s.text(ascii_letters))
def test_progress_event_failed_is_json_serializable(error_code, message):
    event = ProgressEvent.failed(error_code, message)
    assert event.status == OperationStatus.FAILED
    assert event.errorCode == error_code
    assert event.message == message

    assert json.loads(json.dumps(event._serialize())) == {
        "status": OperationStatus.FAILED.value,
        "errorCode": error_code.value,
        "message": message,
        "callbackContext": {},
        "callbackDelaySeconds": 0,
    }


def test_operation_status_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("OperationStatus").enum)
    enum = set(OperationStatus.__members__)
    assert enum == sdk


def test_handler_error_code_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("HandlerErrorCode").enum)
    enum = set(HandlerErrorCode.__members__)
    assert enum == sdk
