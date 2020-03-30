# pylint: disable=protected-access
import json
from unittest.mock import Mock, call, sentinel

import pytest
from cloudformation_cli_python_lib.exceptions import InvalidRequest
from cloudformation_cli_python_lib.interface import BaseModel
from cloudformation_cli_python_lib.utils import (
    HandlerRequest,
    KitchenSinkEncoder,
    UnmodelledRequest,
    deserialize_list,
)

import hypothesis.strategies as s
from hypothesis import given


def roundtrip(value):
    return json.loads(json.dumps(value, cls=KitchenSinkEncoder))


def default_assert(value):
    with pytest.raises(TypeError):
        json.dumps(value)

    assert value.isoformat() == roundtrip(value)


# apply decorator multiple times to create different tests
# pylint: disable=invalid-name
test_default_dates = given(s.dates())(default_assert)
test_default_datetimes = given(s.datetimes())(default_assert)
test_default_times = given(s.times())(default_assert)


def test_default_obj_has__serialize_method():
    value = {"a": "b"}

    class Serializable:
        @staticmethod
        def _serialize():
            return value

    assert value == roundtrip(Serializable())


def test_default_unsupported_type_goes_to_base_class():
    class Unserializable:
        pass

    with pytest.raises(TypeError):
        json.dumps(Unserializable(), cls=KitchenSinkEncoder)


def test_handler_request_serde_roundtrip():
    payload = {
        "awsAccountId": "123456789012",
        "bearerToken": "123456",
        "region": "us-east-1",
        "action": "CREATE",
        "responseEndpoint": "https://cloudformation.us-west-2.amazonaws.com",
        "resourceType": "AWS::Test::TestModel",
        "resourceTypeVersion": "1.0",
        "nextToken": None,
        "requestContext": {
            "invocation": 2,
            "callbackContext": {"contextPropertyA": "Value"},
            "cloudWatchEventsRuleName": "reinvoke-handler-4754ac8a-623b-45fe-84bc-f5394"
            "118a8be",
            "cloudWatchEventsTargetId": "reinvoke-target-4754ac8a-623b-45fe-84bc-f53941"
            "18a8be",
        },
        "requestData": {
            "callerCredentials": None,
            "platformCredentials": {
                "accessKeyId": "32IEHAHFIAG538KYASAI",
                "secretAccessKey": "0O2hop/5vllVHjbA8u52hK8rLcroZpnL5NPGOi66",
                "sessionToken": "gqe6eIsFPHOlfhc3RKl5s5Y6Dy9PYvN1CEYsswz5TQUsE8WfHD6LPK"
                "549euXm4Vn4INBY9nMJ1cJe2mxTYFdhWHSnkOQv2SHemal",
            },
            "providerCredentials": {
                "accessKeyId": "HDI0745692Y45IUTYR78",
                "secretAccessKey": "4976TUYVI234/5GW87ERYG823RF87GY9EIUH452I3",
                "sessionToken": "842HYOFIQAEUDF78R8T7IU43HSADYGIFHBJSDHFA87SDF9PYvN1CEY"
                "ASDUYFT5TQ97YASIHUDFAIUEYRISDKJHFAYSUDTFSDFADS",
            },
            "providerLogGroupName": "providerLoggingGroupName",
            "logicalResourceId": "myBucket",
            "resourceProperties": {},
            "previousResourceProperties": None,
            "stackTags": {"tag1": "abc"},
            "previousStackTags": {"tag1": "def"},
        },
        "stackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/SampleStack/e72"
        "2ae60-fe62-11e8-9a0e-0ae8cc519968",
    }
    ser = HandlerRequest.deserialize(payload).serialize()
    # remove None values from payload
    expected = {
        k: {k: v for k, v in payload["requestData"].items() if v is not None}
        if k == "requestData"
        else v
        for k, v in payload.items()
        if v is not None
    }

    assert ser == expected


def test_unmodelled_request_to_modelled():
    model_cls = Mock(spec_set=BaseModel)
    model_cls._deserialize.side_effect = [sentinel.new, sentinel.old]

    unmodelled = UnmodelledRequest(
        clientRequestToken="foo",
        desiredResourceState={"state": "new"},
        previousResourceState={"state": "old"},
        logicalResourceIdentifier="bar",
        nextToken="baz",
    )
    modelled = unmodelled.to_modelled(model_cls)

    model_cls.assert_has_calls(
        [call._deserialize({"state": "new"}), call._deserialize({"state": "old"})]
    )
    assert modelled.clientRequestToken == "foo"
    assert modelled.desiredResourceState == sentinel.new
    assert modelled.previousResourceState == sentinel.old
    assert modelled.logicalResourceIdentifier == "bar"
    assert modelled.nextToken == "baz"


def test_deserialize_list_empty():
    assert deserialize_list(None, BaseModel) is None
    assert deserialize_list([], BaseModel) is None


def test_deserialize_list_invalid():
    with pytest.raises(InvalidRequest):
        deserialize_list([(1, 2)], BaseModel)
