import typing
from typing import Any, Dict, List, Mapping

from .exceptions import InvalidRequest


# CloudFormation recasts all primitive types as strings, this tries to set them back to
# the types in the type hints
def recast_object(
    cls: Any, json_data: Mapping[str, Any], classes: Dict[str, Any]
) -> None:
    if not isinstance(json_data, dict):
        raise InvalidRequest(f"Can only parse dict items, not {type(json_data)}")
    for k, v in json_data.items():
        if isinstance(v, dict):
            child_cls = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
            recast_object(child_cls, v, classes)
        elif isinstance(v, list):
            json_data[k] = _recast_lists(cls, k, v, classes)
        elif isinstance(v, str):
            dest_type = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
            json_data[k] = _recast_primitive(dest_type, k, v)
        else:
            raise InvalidRequest(f"Unsupported type: {type(v)} for {k}")


def _recast_lists(cls: Any, k: str, v: List[Any], classes: Dict[str, Any]) -> List[Any]:
    casted_list: List[Any] = []
    if k in cls.__dataclass_fields__:
        cls = _field_to_type(cls.__dataclass_fields__[k].type, k, classes)
    for item in v:
        if isinstance(item, str):
            casted_item: Any = _recast_primitive(cls, k, item)
        elif isinstance(item, list):
            casted_item = _recast_lists(cls, k, item, classes)
        elif isinstance(item, dict):
            recast_object(cls, item, classes)
            casted_item = item
        else:
            raise InvalidRequest(f"Unsupported type: {type(v)} for {k}")
        casted_list.append(casted_item)
    return casted_list


def _recast_primitive(cls: Any, k: str, v: str) -> Any:
    if cls == bool:
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        raise InvalidRequest(f'value for {k} "{v}" is not boolean')
    return cls(v)


def _field_to_type(field: Any, key: str, classes: Dict[str, Any]) -> Any:
    if field in [int, float, str, bool]:
        return field
    # If it's a ForwardRef we need to find base type
    if isinstance(field, get_forward_ref_type()):
        # Assuming codegen added an _ as a prefix, removing it and then gettting the
        # class from model classes
        return classes[field.__forward_arg__[1:]]
    # Assuming this is a generic object created by typing.Union
    try:
        possible_types = field.__args__
    except AttributeError:
        raise InvalidRequest(f"Cannot process type {field.__repr__()} for field {key}")
    # Assuming that the union is generated from typing.Optional, so only
    # contains one type and None
    # pylint: disable=unidiomatic-typecheck
    fields = [t for t in possible_types if type(None) != t]
    if len(fields) != 1:
        raise InvalidRequest(f"Cannot process type {field.__repr__()} for field {key}")
    field = fields[0]
    # If it's a primitive we're done
    if field in [int, float, str, bool]:
        return field
    # If it's a ForwardRef we need to find base type
    if isinstance(field, get_forward_ref_type()):
        # Assuming codegen added an _ as a prefix, removing it and then gettting the
        # class from model classes
        return classes[field.__forward_arg__[1:]]
    # If it's not a type we don't know how to handle we bail
    if not str(field).startswith("typing.Sequence"):
        raise InvalidRequest(f"Cannot process type {field} for field {key}")
    return _field_to_type(field.__args__[0], key, classes)


# pylint: disable=protected-access,no-member
def get_forward_ref_type() -> Any:
    # ignoring mypy on the import as it catches (_)ForwardRef as invalid, use for
    # introspection is valid:
    # https://docs.python.org/3/library/typing.html#typing.ForwardRef
    if "ForwardRef" in dir(typing):
        return typing.ForwardRef  # type: ignore
    return typing._ForwardRef  # type: ignore
