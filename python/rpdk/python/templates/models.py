# DO NOT modify this file by hand, changes will be overwritten
import sys
from dataclasses import dataclass
from inspect import getmembers, isclass
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
    BaseModel,
    BaseResourceHandlerRequest,
)
from cloudformation_cli_python_lib.recast import recast_object
from cloudformation_cli_python_lib.utils import deserialize_list

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
class {{ model }}(BaseModel):
    {% for name, type in properties.items() %}
    {{ name }}: Optional[{{ type|translate_type }}]
    {% endfor %}

    @classmethod
    def _deserialize(
        cls: Type["_{{ model }}"],
        json_data: Optional[Mapping[str, Any]],
    ) -> Optional["_{{ model }}"]:
        if not json_data:
            return None
        {% if model == "ResourceModel" %}
        dataclasses = {n: o for n, o in getmembers(sys.modules[__name__]) if isclass(o)}
        recast_object(cls, json_data, dataclasses)
        {% endif %}
        return cls(
            {% for name, type in properties.items() %}
            {% set container = type.container %}
            {% set resolved_type = type.type %}
            {% if container == ContainerType.MODEL %}
            {{ name }}={{ resolved_type }}._deserialize(json_data.get("{{ name }}")),
            {% elif container == ContainerType.SET %}
            {{ name }}=set_or_none(json_data.get("{{ name }}")),
            {% elif container == ContainerType.LIST %}
            {% if type | contains_model %}
            {{name}}=deserialize_list(json_data.get("{{ name }}"), {{resolved_type.type}}),
            {% else %}
            {{ name }}=json_data.get("{{ name }}"),
            {% endif %}
            {% else %}
            {{ name }}=json_data.get("{{ name }}"),
            {% endif %}
            {% endfor %}
        )


# work around possible type aliasing issues when variable has same name as a model
_{{ model }} = {{ model }}


{% endfor -%}
