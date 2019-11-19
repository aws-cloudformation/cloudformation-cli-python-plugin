# DO NOT modify this file by hand, changes will be overwritten
from dataclasses import dataclass
from typing import (
    AbstractSet,
    Any,
    Generic,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from cloudformation_cli_python_lib.interface import (
    BaseResourceHandlerRequest,
    BaseResourceModel,
)

T = TypeVar("T")


def set_or_none(value: Optional[Sequence[T]]) -> Optional[AbstractSet[T]]:
    if value:
        return set(value)
    return None


@dataclass
class ResourceHandlerRequest(BaseResourceHandlerRequest):
    # pylint: disable=invalid-name
    desiredResourceState: Optional["ResourceModel"]
    previousResourceState: Optional["ResourceModel"]


{% for model, properties in models.items() %}
@dataclass
class {{ model }}{% if model == "ResourceModel" %}(BaseResourceModel){% endif %}:
    {% for name, type in properties.items() %}
    {{ name }}: Optional[{{ type|translate_type }}]
    {% endfor %}

    @classmethod
    def _deserialize(
        cls: Type["{{ model }}Alias"],
        json_data: Optional[Mapping[str, Any]],
    ) -> Optional["{{ model }}Alias"]:
        if not json_data:
            return None
        return cls(
            {% for name, type in properties.items() %}
            {% if type.container == ContainerType.MODEL %}
            {{ name }}={{ type.type }}._deserialize(json_data.get("{{ name }}")),
            {% elif type.container == ContainerType.SET %}
            {{ name }}=set_or_none(json_data.get("{{ name }}")),
            {% else %}
            {{ name }}=json_data.get("{{ name }}"),
            {% endif %}
            {% endfor %}
        )


# work around possible type aliasing issues where variable has same name as type
{{ model }}Alias = {{ model }}


{% endfor -%}
