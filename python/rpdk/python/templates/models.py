{%- macro class_model_bindings(properties) -%}
{%- set used_models = properties|models_in_properties -%}
{%- if used_models -%}(
{%- for name in used_models -%}
Generic[T{{ name }}]{%- if not loop.last -%}, {%- endif -%}
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

T = TypeVar("T")


def set_or_none(value: Optional[Sequence[T]]) -> Optional[AbstractSet[T]]:
    if value:
        return set(value)
    return None


{% for model, properties in models.items() %}
T{{ model }} = TypeVar("T{{ model }}", bound="{{ model }}{{ typevar_model_bindings(properties) }}")
{% endfor %}
{% for model, properties in models.items() %}


@dataclass
class {{ model }}{{ class_model_bindings(properties) }}:
    {% for name, type in properties.items() %}
    {{ name }}: Optional[{{ type|translate_type }}]
    {% endfor %}

    def _serialize(self) -> Mapping[str, Any]:
        return self.__dict__

    @classmethod
    def _deserialize(
        cls: Type[T{{ model }}],
        json: Mapping[str, Any],
    ) -> Optional[T{{ model }}]:
        if not json:
            return None
        return cls(
            {% for name, type in properties.items() %}
            {% if type.container == ContainerType.MODEL %}
            {{ name }}={{ type.type }}._deserialize(json.get("{{ name }}")),  # type: ignore
            {% elif type.container == ContainerType.SET %}
            {{ name }}=set_or_none(json.get("{{ name }}")),
            {% else %}
            {{ name }}=json.get("{{ name }}"),
            {% endif %}
            {% endfor %}
        )
{% endfor %}
