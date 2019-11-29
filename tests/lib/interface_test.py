# pylint: disable=protected-access,redefined-outer-name,abstract-method
import json
from dataclasses import dataclass
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


@dataclass
class TestModel(BaseResourceModel):
    somekey: str
    someotherkey: str


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
def test_progress_event_serialize_to_response_with_context(message, bearer_token):
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, callbackContext={"a": "b"}
    )

    assert event._serialize(to_response=True, bearer_token=bearer_token) == {
        "operationStatus": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "bearerToken": bearer_token,
    }


@given(s.text(ascii_letters), s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_model(message, bearer_token):
    model = TestModel("a", "b")
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, resourceModel=model
    )

    assert event._serialize(to_response=True, bearer_token=bearer_token) == {
        "operationStatus": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "bearerToken": bearer_token,
        "resourceModel": {"somekey": "a", "someotherkey": "b"},
    }


@given(s.text(ascii_letters), s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_models(message, bearer_token):
    models = [TestModel("a", "b"), TestModel("c", "d")]
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, resourceModels=models
    )

    assert event._serialize(to_response=True, bearer_token=bearer_token) == {
        "operationStatus": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "bearerToken": bearer_token,
        "resourceModels": [
            {"somekey": "a", "someotherkey": "b"},
            {"somekey": "c", "someotherkey": "d"},
        ],
    }


def test_operation_status_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("OperationStatus").enum)
    enum = set(OperationStatus.__members__)
    assert enum == sdk


def test_handler_error_code_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("HandlerErrorCode").enum)
    enum = set(HandlerErrorCode.__members__)
    assert enum == sdk
