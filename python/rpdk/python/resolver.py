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
        # quote types to ensure they can be referenced before they are declared.
        # use alias (underscore) to avoid clashes with property names. there's
        # an issue if a property has the same name as the type and it's used twice:
        #   Memo: Optional["Memo"]
        #   SecondCopyOfMemo: Optional["Memo"]  <-- mypy doesn't like this
        # due to the schema, property names can't start with underscores, so
        # the alias works well
        return f'"_{resolved_type.type}"'
    if resolved_type.container == ContainerType.PRIMITIVE:
        return PRIMITIVE_TYPES[resolved_type.type]

    if resolved_type.container == ContainerType.MULTIPLE:
        return "Any"

    item_type = translate_type(resolved_type.type)

    if resolved_type.container == ContainerType.DICT:
        key_type = PRIMITIVE_TYPES["string"]
        return f"MutableMapping[{key_type}, {item_type}]"
    if resolved_type.container == ContainerType.LIST:
        return f"Sequence[{item_type}]"
    if resolved_type.container == ContainerType.SET:
        return f"AbstractSet[{item_type}]"

    raise ValueError(f"Unknown container type {resolved_type.container}")


def contains_model(resolved_type):
    if resolved_type.container in [ContainerType.LIST, ContainerType.SET]:
        return contains_model(resolved_type.type)
    return resolved_type.container == ContainerType.MODEL
