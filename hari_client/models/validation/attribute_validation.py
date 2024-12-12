import numbers
import typing

from hari_client import errors
from hari_client import models


def validate_initial_attributes(
    attributes: list[models.AttributeCreate],
) -> None:
    """Raises an error if any requirements for initial attributes aren't met.
    Attribute requirements:
    - attributes with the same name and annotatable type must
        - have the same value type
        - have the same id
    - attributes with value type list, mustn't contain multiple value types in the list

    Args:
        attributes: List of attributes to validate.

    Raises:
        AttributeValidationInconsistentValueTypeError: If the value type for an attribute is inconsistent.
        AttributeValidationInconsistentListElementValueTypesError: If the elements in a list attribute value have mixed value types.
        AttributeValidationIdNotReusedError: If another attribute with the same name and attribute type has a different id.
    """
    grouped_by_attribute_type: dict[str, list[models.AttributeCreate]] = {
        models.DataBaseObjectType.MEDIA: [],
        models.DataBaseObjectType.MEDIAOBJECT: [],
        models.DataBaseObjectType.INSTANCE: [],
    }
    for attribute in attributes:
        grouped_by_attribute_type[attribute.annotatable_type].append(attribute)

    for (
        annotatable_type,
        attributes_with_same_annotatable_type,
    ) in grouped_by_attribute_type.items():
        name_value_type_map: dict[str, str] = {}
        name_id_map: dict[str, str] = {}

        for attribute in attributes_with_same_annotatable_type:
            # check value type
            value_type = _get_value_type_for_comparison(attribute.value)
            if attribute.name in name_value_type_map:
                if name_value_type_map[attribute.name] != value_type:
                    raise errors.AttributeValidationInconsistentValueTypeError(
                        attribute_name=attribute.name,
                        annotatable_type=annotatable_type,
                        found_value_types=[
                            name_value_type_map[attribute.name],
                            value_type,
                        ],
                    )
            else:
                name_value_type_map[attribute.name] = value_type

            # check list elements if value type is list
            if value_type == "list":
                found_list_element_value_types: set[str] = set()
                for element in attribute.value:
                    found_list_element_value_types.add(
                        _get_value_type_for_comparison(element)
                    )
                if len(found_list_element_value_types) > 1:
                    raise errors.AttributeValidationInconsistentListElementValueTypesError(
                        attribute_name=attribute.name,
                        annotatable_type=annotatable_type,
                        found_value_types=found_list_element_value_types,
                    )

            # check id
            if attribute.name in name_id_map:
                if name_id_map[attribute.name] != str(attribute.id):
                    raise errors.AttributeValidationIdNotReusedError(
                        attribute_name=attribute.name,
                        annotatable_type=annotatable_type,
                        found_ids=[
                            name_id_map[attribute.name],
                            str(attribute.id),
                        ],
                    )
            else:
                name_id_map[attribute.name] = str(attribute.id)


def _get_value_type_for_comparison(value: typing.Any) -> str:
    """Gets the type of the value.
    If the value is a number, returns "number" for comparison."""
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        return "number"
    return type(value).__name__
