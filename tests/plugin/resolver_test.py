import pytest

from rpdk.core.jsonutils.resolver import ContainerType, ResolvedType
from rpdk.python.resolver import PRIMITIVE_TYPES, contains_model, translate_type

RESOLVED_TYPES = [
    (ResolvedType(ContainerType.PRIMITIVE, item_type), native_type)
    for item_type, native_type in PRIMITIVE_TYPES.items()
]


def test_translate_type_model_typevar_not_resource_model():
    traslated = translate_type(ResolvedType(ContainerType.MODEL, "Foo"))
    assert traslated == '"_Foo"'


def test_translate_type_model_typevar_main_resource_model():
    traslated = translate_type(ResolvedType(ContainerType.MODEL, "ResourceModel"))
    assert traslated == '"_ResourceModel"'


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


@pytest.mark.parametrize("resolved_type,_native_type", RESOLVED_TYPES)
def test_contains_model_list_containing_primitive(resolved_type, _native_type):
    assert contains_model(ResolvedType(ContainerType.LIST, resolved_type)) is False


def test_contains_model_list_containing_model():
    resolved_type = ResolvedType(
        ContainerType.LIST,
        ResolvedType(ContainerType.LIST, ResolvedType(ContainerType.MODEL, "Foo")),
    )
    assert contains_model(resolved_type) is True


def test_translate_type_multiple():
    traslated = translate_type(ResolvedType(ContainerType.MULTIPLE, "multiple"))
    assert traslated == "Any"
