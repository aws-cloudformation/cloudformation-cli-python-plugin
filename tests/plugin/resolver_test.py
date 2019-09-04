from string import ascii_lowercase

import pytest

from rpdk.core.jsonutils.resolver import ContainerType, ResolvedType
from rpdk.python.resolver import PRIMITIVE_TYPES, models_in_properties, translate_type

RESOLVED_TYPES = [
    (ResolvedType(ContainerType.PRIMITIVE, item_type), native_type)
    for item_type, native_type in PRIMITIVE_TYPES.items()
]


def test_translate_type_model_typevar():
    traslated = translate_type(ResolvedType(ContainerType.MODEL, "Foo"))
    assert traslated == "TFoo"


@pytest.mark.parametrize("resolved_type,native_type", RESOLVED_TYPES)
def test_translate_type_primitive(resolved_type, native_type):
    assert translate_type(resolved_type) == native_type


@pytest.mark.parametrize("resolved_type,native_type", RESOLVED_TYPES)
def test_translate_type_dict(resolved_type, native_type):
    traslated = translate_type(ResolvedType(ContainerType.DICT, resolved_type))
    assert traslated == f"MutableMapping[str, {native_type}]"


@pytest.mark.parametrize("resolved_type,native_type", RESOLVED_TYPES)
def test_translate_type_list(resolved_type, native_type):
    traslated = translate_type(ResolvedType(ContainerType.LIST, resolved_type))
    assert traslated == f"Sequence[{native_type}]"


@pytest.mark.parametrize("resolved_type,native_type", RESOLVED_TYPES)
def test_translate_type_set(resolved_type, native_type):
    traslated = translate_type(ResolvedType(ContainerType.SET, resolved_type))
    assert traslated == f"AbstractSet[{native_type}]"


@pytest.mark.parametrize("resolved_type,_native_type", RESOLVED_TYPES)
def test_translate_type_unknown(resolved_type, _native_type):
    with pytest.raises(ValueError):
        translate_type(ResolvedType("foo", resolved_type))


def test_models_in_properties():
    properties = dict(
        zip(
            ascii_lowercase,
            [
                ResolvedType(ContainerType.MODEL, "foo"),
                ResolvedType(ContainerType.PRIMITIVE, "string"),
                ResolvedType(ContainerType.PRIMITIVE, "boolean"),
                ResolvedType(ContainerType.MODEL, "foo"),
                ResolvedType(ContainerType.DICT, None),
                ResolvedType(ContainerType.MODEL, "foo"),
                ResolvedType(ContainerType.LIST, None),
                ResolvedType(ContainerType.MODEL, "bar"),
                ResolvedType(ContainerType.SET, None),
            ],
        )
    )
    models = models_in_properties(properties)
    assert models == ["bar", "foo"]
