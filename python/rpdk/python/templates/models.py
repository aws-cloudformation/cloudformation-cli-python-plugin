{%- macro class_model_bindings(properties) -%}
{%- set used_models = properties|models_in_properties -%}
{%- if used_models -%}(
{%- for name in used_models -%}
"{{ name }}"{%- if not loop.last -%}, {%- endif -%}
{%- endfor -%}
){%- endif -%}
{%- endmacro -%}
{%- macro typevar_model_bindings(properties) -%}
{%- set used_models = properties|models_in_properties -%}
{%- if used_models -%}[{{ used_models|join(", ") }}]{%- endif %}
{%- endmacro -%}
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


def set_or_none(value: Optional[Sequence[Any]]) -> Optional[AbstractSet[Any]]:
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
class {{ model|resource_name_suffix }}(BaseResourceModel):
    {% for name, type in properties.items() %}
    {{ name }}: Optional[{{ type|translate_type }}]
    {% endfor %}

    @classmethod
    def _deserialize(
        cls: Type["{{ model|resource_name_suffix }}"],
        json_data: Optional[Mapping[str, Any]],
    ) -> Optional["{{ model|resource_name_suffix }}"]:
        if not json_data:
            return None
        return cls(
            {% for name, type in properties.items() %}
            {% if type.container == ContainerType.MODEL %}
            {{ name }}={{ type.type|resource_name_suffix }}._deserialize(json_data.get("{{ name }}")),
            {% elif type.container == ContainerType.SET %}
            {{ name }}=set_or_none(json_data.get("{{ name }}")),
            {% else %}
            {{ name }}=json_data.get("{{ name }}"),
            {% endif %}
            {% endfor %}
        )
{% endfor %}
