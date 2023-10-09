# pylint: disable=protected-access,line-too-long
import pytest
from cloudformation_cli_python_lib.exceptions import InvalidRequest
from cloudformation_cli_python_lib.interface import BaseModel
from cloudformation_cli_python_lib.utils import (
    HandlerRequest,
    HookInvocationRequest,
    KitchenSinkEncoder,
    UnmodelledRequest,
    deserialize_list,
)

import hypothesis.strategies as s  # pylint: disable=C0411
import json
from hypothesis import given  # pylint: disable=C0411
from unittest.mock import Mock, call, sentinel


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
        "callbackContext": {"contextPropertyA": "Value"},
        "requestData": {
            "callerCredentials": None,
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
            "undesiredField": "value",
            "typeConfiguration": {},
        },
        "stackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/SampleStack/e72"
        "2ae60-fe62-11e8-9a0e-0ae8cc519968",
    }
    undesired = "undesiredField"
    ser = HandlerRequest.deserialize(payload).serialize()
    # remove None values from payload
    expected = {
        k: {
            k: v
            for k, v in payload["requestData"].items()
            if v is not None and k not in undesired
        }
        if k == "requestData"
        else v
        for k, v in payload.items()
        if v is not None and k not in undesired
    }
    assert ser == expected


def test_hook_handler_request_serde_roundtrip():
    payload = {
        "awsAccountId": "123456789012",
        "clientRequestToken": "4b90a7e4-b790-456b-a937-0cfdfa211dfe",
        "actionInvocationPoint": "CREATE_PRE_PROVISION",
        "hookTypeName": "AWS::Test::TestHook",
        "hookTypeVersion": "1.0",
        "requestContext": {
            "invocation": 1,
            "callbackContext": {},
        },
        "requestData": {
            "callerCredentials": '{"accessKeyId": "IASAYK835GAIFHAHEI23", "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5poh2O0", "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DHfW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg"}',  # noqa: B950
            "providerCredentials": None,
            "providerLogGroupName": "providerLoggingGroupName",
            "targetName": "AWS::Test::Resource",
            "targetType": "RESOURCE",
            "targetLogicalId": "myResource",
            "hookEncryptionKeyArn": None,
            "hookEncryptionKeyRole": None,
            "targetModel": {
                "resourceProperties": {},
                "previousResourceProperties": None,
            },
            "undesiredField": "value",
        },
        "stackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/SampleStack/e"
        "722ae60-fe62-11e8-9a0e-0ae8cc519968",
        "hookModel": {},
    }
    undesired = "undesiredField"
    ser = HookInvocationRequest.deserialize(payload).serialize()
    # remove None values from payload
    expected = {
        k: {
            k: {k: v for k, v in v.items() if v is not None}
            if k == "targetModel"
            else json.loads(v)
            if k.endswith("Credentials")
            else v
            for k, v in v.items()
            if v is not None and k not in undesired
        }
        if k in ("requestData", "requestContext")
        else v
        for k, v in payload.items()
        if v is not None and k not in undesired
    }

    assert ser == expected


@pytest.mark.parametrize("region", ("us-east-1", "cn-region1", "us-gov-region1"))
def test_unmodelled_request_to_modelled(region):
    model_cls = Mock(spec_set=BaseModel)
    model_cls._deserialize.side_effect = [sentinel.new, sentinel.old]

    mock_type_configuration_model_cls = Mock(spec_set=BaseModel)
    mock_type_configuration_model_cls._deserialize.side_effect = [
        sentinel.type_configuration
    ]

    unmodelled = UnmodelledRequest(
        clientRequestToken="foo",
        desiredResourceState={"state": "new"},
        previousResourceState={"state": "old"},
        typeConfiguration={"state": "test"},
        logicalResourceIdentifier="bar",
        nextToken="baz",
        region=region,
    )
    modelled = unmodelled.to_modelled(model_cls, mock_type_configuration_model_cls)

    model_cls.assert_has_calls(
        [call._deserialize({"state": "new"}), call._deserialize({"state": "old"})]
    )
    mock_type_configuration_model_cls.assert_has_calls(
        [call._deserialize({"state": "test"})]
    )
    assert modelled.clientRequestToken == "foo"
    assert modelled.desiredResourceState == sentinel.new
    assert modelled.previousResourceState == sentinel.old
    assert modelled.logicalResourceIdentifier == "bar"
    assert modelled.typeConfiguration == sentinel.type_configuration
    assert modelled.nextToken == "baz"


def test_deserialize_list_empty():
    assert deserialize_list(None, BaseModel) is None
    assert deserialize_list([], BaseModel) is None


def test_deserialize_list_invalid():
    with pytest.raises(InvalidRequest):
        deserialize_list([(1, 2)], BaseModel)
