# pylint: disable=protected-access,redefined-outer-name
import json
from string import ascii_letters

import boto3
import pytest
from cloudformation_cli_python_lib.interface import (
    BaseResourceModel,
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


def test_base_resource_model__deserialize():
    with pytest.raises(NotImplementedError):
        BaseResourceModel()._deserialize({})


def test_base_resource_model__serialize():
    brm = BaseResourceModel()
    assert brm._serialize() == brm.__dict__


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
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters), s.text(ascii_letters))
def test_progress_event_serialize_to_response(message, bearer_token):
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, callbackDelaySeconds=1
    )

    assert event._serialize(to_response=True, bearer_token=bearer_token) == {
        "operationStatus": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "bearerToken": bearer_token,
    }


def test_operation_status_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("OperationStatus").enum)
    enum = set(OperationStatus.__members__)
    assert enum == sdk


def test_handler_error_code_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("HandlerErrorCode").enum)
    enum = set(HandlerErrorCode.__members__)
    assert enum == sdk
