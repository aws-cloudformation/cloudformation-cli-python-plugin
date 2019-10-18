# pylint: disable=redefined-outer-name,protected-access
from datetime import datetime
from unittest.mock import Mock, call, patch, sentinel

import pytest
from aws_cloudformation_rpdk_python_lib.exceptions import InvalidRequest
from aws_cloudformation_rpdk_python_lib.interface import (
    Action,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)
from aws_cloudformation_rpdk_python_lib.resource import Resource, _ensure_serialize


@pytest.fixture
def resource():
    return Resource(None)


def test__ensure_serialize_uses_custom_encoder():
    now = datetime.now()

    @_ensure_serialize
    def wrapped(_self, _event, _context):
        return {"foo": now}

    json = wrapped(None, None, None)
    assert json == {"foo": now.isoformat()}


def test__ensure_serialize_invalid_returns_progress_event():
    @_ensure_serialize
    def wrapped(_self, _event, _context):
        class Unserializable:
            pass

        return {"foo": Unserializable()}

    serialized = wrapped(None, None, None)
    event = ProgressEvent.failed(
        HandlerErrorCode.InternalFailure,
        "Object of type Unserializable is not JSON serializable",
    )
    assert serialized == event._serialize()


def test_handler_decorator(resource):
    deco = resource.handler(Action.CREATE)
    assert deco(sentinel.mock_handler) is sentinel.mock_handler
    assert resource._handlers == {Action.CREATE: sentinel.mock_handler}


def test__invoke_handler_not_found(resource):
    actual = resource._invoke_handler(None, None, Action.CREATE, {})
    expected = ProgressEvent.failed(
        HandlerErrorCode.InternalFailure, "No handler for CREATE"
    )
    assert actual == expected


def test__invoke_handler_was_found(resource):
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=sentinel.response))

    resp = resource._invoke_handler(
        sentinel.session, sentinel.request, Action.CREATE, sentinel.context
    )
    assert resp is sentinel.response
    mock_handler.assert_called_once_with(
        sentinel.session, sentinel.request, sentinel.context
    )


@pytest.mark.parametrize("event,messages", [({}, ("missing", "credentials"))])
def test__parse_test_request_invalid_request(resource, event, messages):
    with pytest.raises(InvalidRequest) as excinfo:
        resource._parse_test_request(event)

    for msg in messages:
        assert msg in str(excinfo.value), msg


def test__parse_test_request_valid_request():
    mock_model = Mock(spec_set=["_deserialize"])
    mock_model._deserialize.side_effect = [sentinel.state_out1, sentinel.state_out2]

    payload = {
        "credentials": {"accessKeyId": "", "secretAccessKey": "", "sessionToken": ""},
        "action": "CREATE",
        "request": {
            "clientRequestToken": "ecba020e-b2e6-4742-a7d0-8a06ae7c4b2b",
            "desiredResourceState": sentinel.state_in1,
            "previousResourceState": sentinel.state_in2,
            "logicalResourceIdentifier": None,
        },
        "callbackContext": None,
    }

    resource = Resource(mock_model)

    with patch(
        "aws_cloudformation_rpdk_python_lib.resource._get_boto_session"
    ) as mock_session:
        ret = resource._parse_test_request(payload)
    session, request, action, callback_context = ret

    mock_session.assert_called_once()
    assert session is mock_session.return_value

    assert request.clientRequestToken == "ecba020e-b2e6-4742-a7d0-8a06ae7c4b2b"
    mock_model._deserialize.assert_has_calls(
        [call(sentinel.state_in1), call(sentinel.state_in2)]
    )
    assert request.desiredResourceState is sentinel.state_out1
    assert request.previousResourceState is sentinel.state_out2
    assert request.logicalResourceIdentifier is None

    assert action == Action.CREATE
    assert callback_context == {}


def test_test_entrypoint_handler_error(resource):
    # "un-apply" decorator
    event = resource.test_entrypoint.__wrapped__(  # pylint: disable=no-member
        resource, {}, None
    )
    assert event.status == OperationStatus.FAILED
    assert event.errorCode == HandlerErrorCode.InvalidRequest


@pytest.mark.parametrize("exc_cls", [Exception, BaseException])
def test_test_entrypoint_uncaught_exception(resource, exc_cls):
    with patch.object(resource, "_parse_test_request") as mock_parse:
        mock_parse.side_effect = exc_cls("hahaha")
        # "un-apply" decorator
        event = resource.test_entrypoint.__wrapped__(  # pylint: disable=no-member
            resource, {}, None
        )
    assert event.status == OperationStatus.FAILED
    assert event.errorCode == HandlerErrorCode.InternalFailure
    assert event.message == "hahaha"


def test_test_entrypoint_success():
    mock_model = Mock(spec_set=["_deserialize"])
    mock_model._deserialize.side_effect = [None, None]

    resource = Resource(mock_model)
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=sentinel.response))

    payload = {
        "credentials": {"accessKeyId": "", "secretAccessKey": "", "sessionToken": ""},
        "action": "CREATE",
        "request": {
            "clientRequestToken": "ecba020e-b2e6-4742-a7d0-8a06ae7c4b2b",
            "desiredResourceState": None,
            "previousResourceState": None,
            "logicalResourceIdentifier": None,
        },
    }

    event = resource.test_entrypoint.__wrapped__(  # pylint: disable=no-member
        resource, payload, None
    )
    assert event is sentinel.response

    mock_model._deserialize.assert_has_calls([call(None), call(None)])
    mock_handler.assert_called_once()
