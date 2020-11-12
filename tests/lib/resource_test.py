# pylint: disable=redefined-outer-name,protected-access
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import Mock, call, patch, sentinel

import pytest
from cloudformation_cli_python_lib.exceptions import InternalFailure, InvalidRequest
from cloudformation_cli_python_lib.interface import (
    Action,
    BaseModel,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)
from cloudformation_cli_python_lib.resource import Resource, _ensure_serialize
from cloudformation_cli_python_lib.utils import Credentials, HandlerRequest

ENTRYPOINT_PAYLOAD = {
    "awsAccountId": "123456789012",
    "bearerToken": "123456",
    "region": "us-east-1",
    "action": "CREATE",
    "responseEndpoint": None,
    "resourceType": "AWS::Test::TestModel",
    "resourceTypeVersion": "1.0",
    "callbackContext": {},
    "requestData": {
        "callerCredentials": {
            "accessKeyId": "IASAYK835GAIFHAHEI23",
            "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5/poh2O0",
            "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DH"
            "fW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg",
        },
        "providerCredentials": {
            "accessKeyId": "HDI0745692Y45IUTYR78",
            "secretAccessKey": "4976TUYVI234/5GW87ERYG823RF87GY9EIUH452I3",
            "sessionToken": "842HYOFIQAEUDF78R8T7IU43HSADYGIFHBJSDHFA87SDF9PYvN1C"
            "EYASDUYFT5TQ97YASIHUDFAIUEYRISDKJHFAYSUDTFSDFADS",
        },
        "providerLogGroupName": "providerLoggingGroupName",
        "logicalResourceId": "myBucket",
        "resourceProperties": sentinel.state_in1,
        "previousResourceProperties": sentinel.state_in2,
        "systemTags": {"aws:cloudformation:stack-id": "SampleStack"},
        "previousSystemTags": {},
        "stackTags": {"tag1": "abc"},
        "previousStackTags": {"tag1": "def"},
    },
    "stackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/SampleStack/e"
    "722ae60-fe62-11e8-9a0e-0ae8cc519968",
    "snapshotRequested": None,
}
TYPE_NAME = "Test::Foo::Bar"


@pytest.fixture
def resource():
    return Resource(TYPE_NAME, None)


def patch_and_raise(resource, str_to_patch, exc_cls, entrypoint):
    with patch.object(resource, str_to_patch) as mock_parse:
        mock_parse.side_effect = exc_cls("hahaha")
        # "un-apply" decorator
        event = entrypoint.__wrapped__(resource, {}, None)  # pylint: disable=no-member
    return event


def test_entrypoint_handler_error(resource):
    with patch("cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"):
        event = resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, {}, None
        )
    assert event["status"] == OperationStatus.FAILED.value
    assert event["errorCode"] == HandlerErrorCode.InvalidRequest


def test_entrypoint_success():
    resource = Resource(TYPE_NAME, Mock())
    event = ProgressEvent(status=OperationStatus.SUCCESS, message="")
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=event))

    with patch(
        "cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"
    ) as mock_log_delivery:
        event = resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, ENTRYPOINT_PAYLOAD, None
        )
    mock_log_delivery.assert_called_once()

    assert event == {
        "message": "",
        "status": OperationStatus.SUCCESS.name,  # pylint: disable=no-member
        "callbackDelaySeconds": 0,
    }

    mock_handler.assert_called_once()


def test_entrypoint_handler_raises():
    @dataclass
    class ResourceModel(BaseModel):
        a_string: str

        @classmethod
        def _deserialize(cls, json_data):
            return cls("test")

    resource = Resource(Mock(), ResourceModel)

    with patch(
        "cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"
    ), patch(
        "cloudformation_cli_python_lib.resource.MetricsPublisherProxy"
    ) as mock_metrics, patch(
        "cloudformation_cli_python_lib.resource.Resource._invoke_handler"
    ) as mock__invoke_handler:
        mock__invoke_handler.side_effect = InvalidRequest("handler failed")
        event = resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, ENTRYPOINT_PAYLOAD, None
        )

    mock_metrics.return_value.publish_exception_metric.assert_called_once()
    assert event == {
        "errorCode": "InvalidRequest",
        "message": "handler failed",
        "status": "FAILED",
        "callbackDelaySeconds": 0,
    }


def test_entrypoint_non_mutating_action():
    payload = ENTRYPOINT_PAYLOAD.copy()
    payload["action"] = "READ"
    resource = Resource(TYPE_NAME, Mock())
    event = ProgressEvent(status=OperationStatus.SUCCESS, message="")
    resource.handler(Action.CREATE)(Mock(return_value=event))

    with patch(
        "cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"
    ) as mock_return_progress:
        resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, payload, None
        )
    assert mock_return_progress.call_count == 1


def test_entrypoint_with_context():
    payload = ENTRYPOINT_PAYLOAD.copy()
    payload["callbackContext"] = {"a": "b"}
    resource = Resource(TYPE_NAME, Mock())
    event = ProgressEvent(
        status=OperationStatus.SUCCESS, message="", callbackContext={"c": "d"}
    )
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=event))

    with patch("cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"):
        resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, payload, None
        )

    mock_handler.assert_called_once()


def test_entrypoint_success_without_caller_provider_creds():
    resource = Resource(TYPE_NAME, Mock())
    event = ProgressEvent(status=OperationStatus.SUCCESS, message="")
    resource.handler(Action.CREATE)(Mock(return_value=event))

    payload = ENTRYPOINT_PAYLOAD.copy()
    payload["requestData"] = payload["requestData"].copy()

    expected = {
        "message": "",
        "status": OperationStatus.SUCCESS,
        "callbackDelaySeconds": 0,
    }

    with patch("cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"):
        # Credentials are defined in payload, but null
        payload["requestData"]["providerCredentials"] = None
        payload["requestData"]["callerCredentials"] = None
        event = resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, payload, None
        )
        assert event == expected

        # Credentials are undefined in payload
        del payload["requestData"]["providerCredentials"]
        del payload["requestData"]["callerCredentials"]

        event = resource.__call__.__wrapped__(  # pylint: disable=no-member
            resource, payload, None
        )
        assert event == expected


def test_cast_resource_request_invalid_request(resource):
    request = HandlerRequest.deserialize(ENTRYPOINT_PAYLOAD)
    request.requestData = None
    with pytest.raises(InvalidRequest) as excinfo:
        resource._cast_resource_request(request)

    assert "AttributeError" in str(excinfo.value)


def test__parse_request_valid_request_and__cast_resource_request():
    mock_model = Mock(spec_set=["_deserialize"])
    mock_model._deserialize.side_effect = [sentinel.state_out1, sentinel.state_out2]

    resource = Resource(TYPE_NAME, mock_model)

    with patch(
        "cloudformation_cli_python_lib.resource._get_boto_session"
    ) as mock_session:
        ret = resource._parse_request(ENTRYPOINT_PAYLOAD)
    sessions, action, callback_context, request = ret

    mock_session.assert_has_calls(
        [
            call(Credentials(**ENTRYPOINT_PAYLOAD["requestData"]["callerCredentials"])),
            call(
                Credentials(**ENTRYPOINT_PAYLOAD["requestData"]["providerCredentials"])
            ),
        ],
        any_order=True,
    )

    # credentials are used when rescheduling, so can't zero them out (for now)
    assert request.requestData.callerCredentials is not None
    assert request.requestData.providerCredentials is not None

    caller_sess, provider_sess = sessions
    assert caller_sess is mock_session.return_value
    assert provider_sess is mock_session.return_value

    assert action == Action.CREATE
    assert callback_context == {}

    modeled_request = resource._cast_resource_request(request)

    mock_model._deserialize.assert_has_calls(
        [call(sentinel.state_in1), call(sentinel.state_in2)]
    )
    assert modeled_request.clientRequestToken == request.bearerToken
    assert modeled_request.desiredResourceState is sentinel.state_out1
    assert modeled_request.previousResourceState is sentinel.state_out2
    assert modeled_request.logicalResourceIdentifier == "myBucket"
    assert modeled_request.nextToken is None


@pytest.mark.parametrize("exc_cls", [Exception, BaseException])
def test_entrypoint_uncaught_exception(resource, exc_cls):
    with patch("cloudformation_cli_python_lib.resource.ProviderLogHandler.setup"):
        event = patch_and_raise(resource, "_parse_request", exc_cls, resource.__call__)
    assert event["status"] == OperationStatus.FAILED
    assert event["errorCode"] == HandlerErrorCode.InternalFailure
    assert event["message"] == "hahaha"


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
    try:
        # Python 3.7/3.8
        assert serialized == event._serialize()
    except AssertionError:
        # Python 3.6
        event.message = "Object of type 'Unserializable' is not JSON serializable"
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
    progress_event = ProgressEvent(status=OperationStatus.IN_PROGRESS)
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=progress_event))

    resp = resource._invoke_handler(
        sentinel.session, sentinel.request, Action.CREATE, sentinel.context
    )
    assert resp is progress_event
    mock_handler.assert_called_once_with(
        sentinel.session, sentinel.request, sentinel.context
    )


@pytest.mark.parametrize("action", [Action.LIST, Action.READ])
def test__invoke_handler_non_mutating_must_be_synchronous(resource, action):
    progress_event = ProgressEvent(status=OperationStatus.IN_PROGRESS)
    resource.handler(action)(Mock(return_value=progress_event))
    with pytest.raises(Exception) as excinfo:
        resource._invoke_handler(
            sentinel.session, sentinel.request, action, sentinel.context
        )
    assert excinfo.value.args[0] == "READ and LIST handlers must return synchronously."


@pytest.mark.parametrize("event,messages", [({}, ("missing", "credentials"))])
def test__parse_test_request_invalid_request(resource, event, messages):
    with pytest.raises(InternalFailure) as excinfo:
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

    resource = Resource(TYPE_NAME, mock_model)

    with patch(
        "cloudformation_cli_python_lib.resource._get_boto_session"
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
    assert event.errorCode == HandlerErrorCode.InternalFailure


@pytest.mark.parametrize("exc_cls", [Exception, BaseException])
def test_test_entrypoint_uncaught_exception(resource, exc_cls):
    event = patch_and_raise(
        resource, "_parse_test_request", exc_cls, resource.test_entrypoint
    )
    assert event.status == OperationStatus.FAILED
    assert event.errorCode == HandlerErrorCode.InternalFailure
    assert event.message == "hahaha"


def test_test_entrypoint_success():
    mock_model = Mock(spec_set=["_deserialize"])
    mock_model._deserialize.side_effect = [None, None]

    resource = Resource(TYPE_NAME, mock_model)
    progress_event = ProgressEvent(status=OperationStatus.SUCCESS)
    mock_handler = resource.handler(Action.CREATE)(Mock(return_value=progress_event))

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
    assert event is progress_event

    mock_model._deserialize.assert_has_calls([call(None), call(None)])
    mock_handler.assert_called_once()
