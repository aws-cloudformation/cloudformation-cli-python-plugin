# pylint: disable=protected-access
from typing import Awaitable, Generic, Optional, Union
from unittest.mock import patch

import pytest
from cloudformation_cli_python_lib.exceptions import InvalidRequest
from cloudformation_cli_python_lib.recast import (
    _field_to_type,
    _recast_lists,
    _recast_primitive,
    get_forward_ref_type,
    recast_object,
)

from .sample_model import ResourceModel as ComplexResourceModel, SimpleResourceModel


def test_recast_complex_object():
    payload = {
        "ListListAny": [[{"key": "val"}]],
        "ListListInt": [["1", "2", "3"]],
        "ListSetInt": [{"1", "2", "3"}],
        "ASet": {"1", "2", "3"},
        "AnotherSet": {"a", "b", "c"},
        "AFreeformDict": {"somekey": "somevalue", "someotherkey": "1"},
        "APrimitiveTypeDict": {"somekey": "true", "someotherkey": "false"},
        "AnInt": "1",
        "ABool": "true",
        "AList": [
            {
                "DeeperBool": "false",
                "DeeperList": ["1", "2", "3"],
                "DeeperDictInList": {"DeepestBool": "true", "DeepestList": ["3", "4"]},
            },
            {"DeeperDictInList": {"DeepestBool": "false", "DeepestList": ["6", "7"]}},
        ],
        "ADict": {
            "DeepBool": "true",
            "DeepList": ["10", "11"],
            "DeepDict": {
                "DeeperBool": "false",
                "DeeperList": ["1", "2", "3"],
                "DeeperDict": {"DeepestBool": "true", "DeepestList": ["13", "17"]},
            },
        },
        "NestedList": [
            [{"NestedListInt": "true", "NestedListList": ["1", "2", "3"]}],
            [{"NestedListInt": "false", "NestedListList": ["11", "12", "13"]}],
        ],
    }
    expected = {
        "ListSetInt": [{1, 2, 3}],
        "ListListInt": [[1, 2, 3]],
        "ListListAny": [[{"key": "val"}]],
        "ASet": {"1", "2", "3"},
        "AnotherSet": {"a", "b", "c"},
        "AFreeformDict": {"somekey": "somevalue", "someotherkey": "1"},
        "APrimitiveTypeDict": {"somekey": True, "someotherkey": False},
        "AnInt": 1,
        "ABool": True,
        "AList": [
            {
                "DeeperBool": False,
                "DeeperList": [1, 2, 3],
                "DeeperDictInList": {"DeepestBool": True, "DeepestList": [3, 4]},
            },
            {"DeeperDictInList": {"DeepestBool": False, "DeepestList": [6, 7]}},
        ],
        "ADict": {
            "DeepBool": True,
            "DeepList": [10, 11],
            "DeepDict": {
                "DeeperBool": False,
                "DeeperList": [1, 2, 3],
                "DeeperDict": {"DeepestBool": True, "DeepestList": [13, 17]},
            },
        },
        "NestedList": [
            [{"NestedListInt": True, "NestedListList": [1.0, 2.0, 3.0]}],
            [{"NestedListInt": False, "NestedListList": [11.0, 12.0, 13.0]}],
        ],
    }
    model = ComplexResourceModel._deserialize(payload)
    assert payload == expected
    assert model._serialize() == expected
    # re-invocations should not fail because they already type-cast payloads
    assert ComplexResourceModel._deserialize(payload)._serialize() == expected


def test_recast_object_invalid_json_type():
    with pytest.raises(InvalidRequest) as excinfo:
        recast_object(SimpleResourceModel, [], {})
    assert str(excinfo.value) == f"Can only parse dict items, not {type([])}"


def test_recast_object_invalid_sub_type():
    k = "key"
    v = (1, 2)
    with pytest.raises(InvalidRequest) as excinfo:
        recast_object(SimpleResourceModel, {k: v}, {})
    assert str(excinfo.value) == f"Unsupported type: {type(v)} for {k}"


def test_recast_list_invalid_sub_type():
    k = "key"
    v = [(1, 2)]
    with pytest.raises(InvalidRequest) as excinfo:
        _recast_lists(SimpleResourceModel, k, v, {})
    assert str(excinfo.value) == f"Unsupported type: {type(v[0])} for {k}"


def test_recast_boolean_invalid_value():
    k = "key"
    v = "not-a-bool"
    with pytest.raises(InvalidRequest) as excinfo:
        _recast_primitive(bool, k, v)
    assert str(excinfo.value) == f'value for {k} "{v}" is not boolean'


def test_field_to_type_unhandled_types():
    k = "key"
    for field in [Union[str, list], Generic, Optional[Awaitable]]:
        with pytest.raises(InvalidRequest) as excinfo:
            _field_to_type(field, k, {})
        assert str(excinfo.value).startswith("Cannot process type ")


def test_field_to_type_unhandled_types_36():
    k = "key"

    class SixType:
        __args__ = None

    with pytest.raises(InvalidRequest) as excinfo:
        _field_to_type(SixType, k, {})
    assert str(excinfo.value).startswith("Cannot process type ")


def test_field_to_type_unhandled_types_37():
    k = "key"

    class SevenType:
        pass

    with pytest.raises(InvalidRequest) as excinfo:
        _field_to_type(SevenType, k, {})
    assert str(excinfo.value).startswith("Cannot process type ")


def test_get_forward_ref_type():
    with patch("cloudformation_cli_python_lib.recast.typing") as mock_typing:
        mock_typing.ForwardRef = "3.7+"
        assert get_forward_ref_type() == "3.7+"
    with patch("cloudformation_cli_python_lib.recast.typing") as mock_typing:
        mock_typing._ForwardRef = "3.6"
        get_forward_ref_type()
        assert get_forward_ref_type() == "3.6"
