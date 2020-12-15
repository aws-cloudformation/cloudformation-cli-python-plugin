import typing
from typing import Any, Dict, List, Mapping, Set

from .exceptions import InvalidRequest

PRIMITIVES = (str, bool, int, float)


# CloudFormation recasts all primitive types as strings, this tries to set them back to
# the types in the type hints
def recast_object(
    cls: Any, json_data: Mapping[str, Any], classes: Dict[str, Any]
) -> None:
    if not isinstance(json_data, dict):
        raise InvalidRequest(f"Can only parse dict items, not {type(json_data)}")
    # if type is Any, we leave it as is
    if cls == typing.Any:
        return
    for k, v in json_data.items():
        if isinstance(v, dict):
            child_cls = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
            recast_object(child_cls, v, classes)
        elif isinstance(v, list):
            json_data[k] = _recast_lists(cls, k, v, classes)
        elif isinstance(v, set):
            json_data[k] = _recast_sets(cls, k, v, classes)
        elif isinstance(v, PRIMITIVES):
            dest_type = cls
            if "__dataclass_fields__" in dir(cls):
                dest_type = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
            json_data[k] = _recast_primitive(dest_type, k, v)
        else:
            raise InvalidRequest(f"Unsupported type: {type(v)} for {k}")


def _recast_lists(cls: Any, k: str, v: List[Any], classes: Dict[str, Any]) -> List[Any]:
    # Leave as is if type is Any
    if cls == typing.Any:
        return v
    if "__dataclass_fields__" not in dir(cls):
        pass
    elif k in cls.__dataclass_fields__:
        cls = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
    return [cast_sequence_item(cls, k, item, classes) for item in v]


def _recast_sets(cls: Any, k: str, v: Set[Any], classes: Dict[str, Any]) -> Set[Any]:
    if "__dataclass_fields__" in dir(cls):
        cls = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
    return {cast_sequence_item(cls, k, item, classes) for item in v}


def cast_sequence_item(cls: Any, k: str, item: Any, classes: Dict[str, Any]) -> Any:
    if isinstance(item, PRIMITIVES):
        return _recast_primitive(cls, k, item)
    if isinstance(item, list):
        return _recast_lists(cls, k, item, classes)
    if isinstance(item, set):
        return _recast_sets(cls, k, item, classes)
    if isinstance(item, dict):
        recast_object(cls, item, classes)
        return item
    raise InvalidRequest(f"Unsupported type: {type(item)} for {k}")


def _recast_primitive(cls: Any, k: str, v: Any) -> Any:
    if cls == typing.Any:
        # If the type is Any, we cannot guess what the original type was, so we leave
        # it as a string
        return v
    if cls == bool and isinstance(v, str):
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        raise InvalidRequest(f'value for {k} "{v}" is not boolean')
    return cls(v)


# yes, introspecting type hints is ugly, but hopefully only needed temporarily
def _field_to_type(field: Any, key: str, classes: Dict[str, Any]) -> Any:  # noqa: C901
    if field in [int, float, str, bool, typing.Any]:
        return field
    # If it's a ForwardRef we need to find base type
    if isinstance(field, get_forward_ref_type()):
        # Assuming codegen added an _ as a prefix, removing it and then getting the
        # class from model classes
        return classes[field.__forward_arg__[1:]]
    # Assuming this is a generic object created by typing.Union
    try:
        possible_types = field.__args__
        if not possible_types:
            raise InvalidRequest(f"Cannot process type {field} for field {key}")
    except AttributeError as attribute_error:
        raise InvalidRequest(
            f"Cannot process type {field} for field {key}"
        ) from attribute_error
    # Assuming that the union is generated from typing.Optional, so only
    # contains one type and None
    # pylint: disable=unidiomatic-typecheck
    fields = [t for t in possible_types if type(None) != t]
    if len(fields) != 1:
        raise InvalidRequest(f"Cannot process type {field} for field {key}")
    field = fields[0]
    # If it's a primitive we're done
    if field in [int, float, str, bool, typing.Any]:
        return field
    # If it's a ForwardRef we need to find base type
    if isinstance(field, get_forward_ref_type()):
        # Assuming codegen added an _ as a prefix, removing it and then getting the
        # class from model classes
        return classes[field.__forward_arg__[1:]]
    # reduce Sequence/AbstractSet to inner type
    if str(field).startswith("typing.Sequence") or str(field).startswith(
        "typing.AbstractSet"
    ):
        return _field_to_type(field.__args__[0], key, classes)
    if str(field).startswith("typing.MutableMapping"):
        return _field_to_type(field.__args__[1], key, classes)
    # If it's a type we don't know how to handle, we bail
    raise InvalidRequest(f"Cannot process type {field} for field {key}")


# pylint: disable=protected-access,no-member
def get_forward_ref_type() -> Any:
    # ignoring mypy on the import as it catches (_)ForwardRef as invalid, use for
    # introspection is valid:
    # https://docs.python.org/3/library/typing.html#typing.ForwardRef
    if "ForwardRef" in dir(typing):
        return typing.ForwardRef  # type: ignore
    return typing._ForwardRef  # type: ignore
