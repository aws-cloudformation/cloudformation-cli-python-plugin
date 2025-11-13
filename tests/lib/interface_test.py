# pylint: disable=protected-access,redefined-outer-name,abstract-method
from dataclasses import dataclass

import boto3
import pytest
from cloudformation_cli_python_lib.interface import (
    BaseModel,
    HandlerErrorCode,
    HookAnnotation,
    HookAnnotationSeverityLevel,
    HookAnnotationStatus,
    HookProgressEvent,
    HookStatus,
    OperationStatus,
    ProgressEvent,
)
from cloudformation_cli_python_lib.utils import KitchenSinkEncoder

import hypothesis.strategies as s  # pylint: disable=C0411
import json
from hypothesis import given  # pylint: disable=C0411
from string import ascii_letters


@pytest.fixture(scope="module")
def client():
    return boto3.client(
        "cloudformation",
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_session_token="",
        region_name="us-east-1",
    )


# don't call this TestModel, or pytest will try and execute it
@dataclass
class ResourceModel(BaseModel):
    somekey: str
    someotherkey: str


def test_base_resource_model__deserialize():
    with pytest.raises(NotImplementedError):
        BaseModel()._deserialize({})


def test_base_resource_model__serialize():
    brm = BaseModel()
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


@given(s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_context(message):
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, callbackContext={"a": "b"}
    )

    print(event._serialize())
    assert event._serialize() == {
        "status": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "callbackContext": {"a": "b"},
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_model(message):
    model = ResourceModel("a", "b")
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, resourceModel=model
    )

    assert event._serialize() == {
        "status": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "resourceModel": {"somekey": "a", "someotherkey": "b"},
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_models(message):
    models = [ResourceModel("a", "b"), ResourceModel("c", "d")]
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message=message, resourceModels=models
    )

    assert event._serialize() == {
        "status": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "resourceModels": [
            {"somekey": "a", "someotherkey": "b"},
            {"somekey": "c", "someotherkey": "d"},
        ],
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters))
def test_progress_event_serialize_to_response_with_error_code(message):
    event = ProgressEvent(
        status=OperationStatus.SUCCESS,
        message=message,
        errorCode=HandlerErrorCode.InvalidRequest,
    )

    assert event._serialize() == {
        "status": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "errorCode": HandlerErrorCode.InvalidRequest.name,  # pylint: disable=no-member
        "callbackDelaySeconds": 0,
    }


@given(s.sampled_from(HandlerErrorCode), s.text(ascii_letters))
def test_hook_progress_event_failed_is_json_serializable(error_code, message):
    event = HookProgressEvent.failed(error_code, message)
    assert event.hookStatus == HookStatus.FAILED
    assert event.errorCode == error_code
    assert event.message == message

    assert json.loads(json.dumps(event._serialize())) == {
        "hookStatus": HookStatus.FAILED.value,
        "errorCode": error_code.value,
        "message": message,
        "callbackDelaySeconds": 0,
    }


@given(
    s.sampled_from(HandlerErrorCode),
    s.text(ascii_letters),
    s.sampled_from(HookAnnotationSeverityLevel),
)
def test_hook_progress_event_failed_with_annotations_is_json_serializable(
    error_code,
    message,
    annotation_severity_level,
):
    event = HookProgressEvent(
        hookStatus=OperationStatus.FAILED,
        message=message,
        errorCode=error_code,
        annotations=[
            HookAnnotation(
                annotationName="test_annotation_name_1",
                status=HookAnnotationStatus.FAILED,
                statusMessage="test_status_message_1",
                remediationMessage="test_remediation_message",
                remediationLink="https://localhost/test-1",
                severityLevel=annotation_severity_level,
            ),
            HookAnnotation(
                annotationName="test_annotation_name_2",
                status=HookAnnotationStatus.PASSED,
                statusMessage="test_status_message_2",
            ),
        ],
    )

    assert event.hookStatus == HookStatus.FAILED
    assert event.errorCode == error_code
    assert event.message == message

    assert event.annotations[0].annotationName == "test_annotation_name_1"
    assert event.annotations[0].status == HookAnnotationStatus.FAILED.name
    assert event.annotations[0].statusMessage == "test_status_message_1"
    assert event.annotations[0].remediationMessage == "test_remediation_message"
    assert event.annotations[0].remediationLink == "https://localhost/test-1"
    assert event.annotations[0].severityLevel == annotation_severity_level

    assert event.annotations[1].annotationName == "test_annotation_name_2"
    assert event.annotations[1].status == HookAnnotationStatus.PASSED.name
    assert event.annotations[1].statusMessage == "test_status_message_2"

    assert json.loads(
        json.dumps(
            event._serialize(),
            cls=KitchenSinkEncoder,
        )
    ) == {
        "hookStatus": HookStatus.FAILED.value,
        "errorCode": error_code.value,
        "message": message,
        "callbackDelaySeconds": 0,
        "annotations": [
            {
                "annotationName": "test_annotation_name_1",
                "status": "FAILED",
                "statusMessage": "test_status_message_1",
                "remediationMessage": "test_remediation_message",
                "remediationLink": "https://localhost/test-1",
                "severityLevel": annotation_severity_level.name,
            },
            {
                "annotationName": "test_annotation_name_2",
                "status": "PASSED",
                "statusMessage": "test_status_message_2",
            },
        ],
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_context(message):
    event = HookProgressEvent(
        hookStatus=HookStatus.SUCCESS, message=message, callbackContext={"a": "b"}
    )

    assert event._serialize() == {
        "hookStatus": HookStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "callbackContext": {"a": "b"},
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_context_with_annotation(
    message,
):
    event = HookProgressEvent(
        hookStatus=HookStatus.SUCCESS,
        message=message,
        callbackContext={"a": "b"},
        annotations=[
            HookAnnotation(
                annotationName="test_annotation_name",
                status=HookAnnotationStatus.PASSED,
                statusMessage="test_status_message",
            ),
        ],
    )

    assert json.loads(
        json.dumps(
            event._serialize(),
            cls=KitchenSinkEncoder,
        )
    ) == {
        "hookStatus": HookStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "callbackContext": {"a": "b"},
        "callbackDelaySeconds": 0,
        "annotations": [
            {
                "annotationName": "test_annotation_name",
                "status": "PASSED",
                "statusMessage": "test_status_message",
            },
        ],
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_data(message):
    result = "My hook data"
    event = HookProgressEvent(
        hookStatus=HookStatus.SUCCESS, message=message, result=result
    )

    assert event._serialize() == {
        "hookStatus": HookStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "callbackDelaySeconds": 0,
        "result": result,
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_data_with_annotation(message):
    result = "My hook data"
    event = HookProgressEvent(
        hookStatus=HookStatus.SUCCESS,
        message=message,
        result=result,
        annotations=[
            HookAnnotation(
                annotationName="test_annotation_name",
                status=HookAnnotationStatus.PASSED,
                statusMessage="test_status_message",
            ),
        ],
    )

    assert json.loads(
        json.dumps(
            event._serialize(),
            cls=KitchenSinkEncoder,
        )
    ) == {
        "hookStatus": HookStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "callbackDelaySeconds": 0,
        "result": result,
        "annotations": [
            {
                "annotationName": "test_annotation_name",
                "status": "PASSED",
                "statusMessage": "test_status_message",
            },
        ],
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_error_code(message):
    event = HookProgressEvent(
        hookStatus=HookStatus.SUCCESS,
        message=message,
        errorCode=HandlerErrorCode.InvalidRequest,
    )

    assert event._serialize() == {
        "hookStatus": HookStatus.SUCCESS.name,  # pylint: disable=no-member
        "message": message,
        "errorCode": HandlerErrorCode.InvalidRequest.name,  # pylint: disable=no-member
        "callbackDelaySeconds": 0,
    }


@given(s.text(ascii_letters))
def test_hook_progress_event_serialize_to_response_with_error_code_with_annotation(
    message,
):
    event = HookProgressEvent(
        hookStatus=HookStatus.FAILED,
        message=message,
        errorCode=HandlerErrorCode.InvalidRequest,
        annotations=[
            HookAnnotation(
                annotationName="test_annotation_name",
                status=HookAnnotationStatus.FAILED,
                statusMessage="test_status_message",
            ),
        ],
    )

    assert json.loads(
        json.dumps(
            event._serialize(),
            cls=KitchenSinkEncoder,
        )
    ) == {
        "hookStatus": HookStatus.FAILED.name,  # pylint: disable=no-member
        "message": message,
        "errorCode": HandlerErrorCode.InvalidRequest.name,  # pylint: disable=no-member
        "callbackDelaySeconds": 0,
        "annotations": [
            {
                "annotationName": "test_annotation_name",
                "status": "FAILED",
                "statusMessage": "test_status_message",
            },
        ],
    }


def test_operation_status_enum_matches_sdk(client):
    sdk = set(client.meta.service_model.shape_for("OperationStatus").enum)
    enum = set(OperationStatus.__members__)
    # CHANGE_SET_SUCCESS_SKIP_STACK_HOOK is a status specific to Hooks
    enum.remove("CHANGE_SET_SUCCESS_SKIP_STACK_HOOK")
    assert enum == sdk
