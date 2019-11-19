import json

import pytest
from cloudformation_cli_python_lib.utils import KitchenSinkEncoder

import hypothesis.strategies as s
from hypothesis import given


def roundtrip(value):
    return json.loads(json.dumps(value, cls=KitchenSinkEncoder))


def default_assert(value):
    with pytest.raises(TypeError):
        json.dumps(value)

    assert value == value.fromisoformat(roundtrip(value))


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
