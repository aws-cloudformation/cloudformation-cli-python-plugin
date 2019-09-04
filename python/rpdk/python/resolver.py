from rpdk.core.jsonutils.resolver import UNDEFINED, ContainerType

PRIMITIVE_TYPES = {
    "string": "str",
    "integer": "int",
    "boolean": "bool",
    "number": "float",
    UNDEFINED: "Any",
}


def translate_type(resolved_type):
    if resolved_type.container == ContainerType.MODEL:
        # we create type vars to make it easier to ref later models
        return f"T{resolved_type.type}"
    if resolved_type.container == ContainerType.PRIMITIVE:
        return PRIMITIVE_TYPES[resolved_type.type]

    item_type = translate_type(resolved_type.type)

    if resolved_type.container == ContainerType.DICT:
        key_type = PRIMITIVE_TYPES["string"]
        return f"MutableMapping[{key_type}, {item_type}]"
    if resolved_type.container == ContainerType.LIST:
        return f"Sequence[{item_type}]"
    if resolved_type.container == ContainerType.SET:
        return f"AbstractSet[{item_type}]"

    raise ValueError(f"Unknown container type {resolved_type.container}")


def models_in_properties(properties):
    # set for de-dupe, sorted for consistency
    return sorted(
        {
            resolved_type.type
            for resolved_type in properties.values()
            if resolved_type.container == ContainerType.MODEL
        }
    )
