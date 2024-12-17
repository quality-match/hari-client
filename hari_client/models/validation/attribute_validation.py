import numbers
import typing

from hari_client import errors
from hari_client import models


def validate_attributes(
    attributes: list[models.AttributeCreate],
) -> None:
    """Raises an error if any requirements for attributes aren't met.
    Basic attribute requirements:
    - attributes with the same name and annotatable type must
      - have the same id
      - have the same value type
    - attributes with value type list must
      - contain only a single value type
      - contain only the same value type as other attributes with the same name and annotatable type

    Exceptions:
      - The value `None` isn't taken into account when value type consistency is checked.

    Args:
        attributes: List of attributes to validate.

    Raises:
        AttributeValidationInconsistentValueTypeError: If the value type for an attribute is inconsistent.
        AttributeValidationInconsistentListElementValueTypesError: If the elements in a list attribute value have mixed value types.
        AttributeValidationInconsistentListElementValueTypesMultipleAttributesError: If multiple list attributes have inconsistent element value types.
        AttributeValidationIdNotReusedError: If another attribute with the same name and attribute type has a different id.
    """
    grouped_by_annotatable_type: dict[str, list[models.AttributeCreate]] = {
        models.DataBaseObjectType.MEDIA: [],
        models.DataBaseObjectType.MEDIAOBJECT: [],
        models.DataBaseObjectType.INSTANCE: [],
    }
    for attribute in attributes:
        grouped_by_annotatable_type[attribute.annotatable_type].append(attribute)

    for (
        annotatable_type,
        attributes_with_same_annotatable_type,
    ) in grouped_by_annotatable_type.items():
        # to check the value type consistency of attribute.value
        name_value_type_map: dict[str, str] = {}

        # to check the value type consistency of list elements, when attribute.value is a list
        name_list_element_value_type_map: dict[str, str] = {}

        # to check whether the ids are reused as expected
        name_id_map: dict[str, str] = {}

        for attribute in attributes_with_same_annotatable_type:
            # check value type
            value_type = _get_value_type_for_comparison(attribute.value)
            # None values automatically pass the value type consistency check
            if value_type == "NoneType":
                continue

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
                if attribute.value == []:
                    continue
                found_list_element_value_types: set[str] = set()
                for element in attribute.value:
                    element_value_type = _get_value_type_for_comparison(element)
                    if element_value_type == "NoneType":
                        continue
                    else:
                        found_list_element_value_types.add(element_value_type)

                # check list element value type consistency within the attribute
                if len(found_list_element_value_types) > 1:
                    raise errors.AttributeValidationInconsistentListElementValueTypesError(
                        attribute_name=attribute.name,
                        annotatable_type=annotatable_type,
                        found_value_types=found_list_element_value_types,
                    )
                # check list element value type consistency across attributes
                attribute_list_element_value_type = list(
                    found_list_element_value_types
                )[0]
                if attribute.name in name_list_element_value_type_map:
                    if (
                        name_list_element_value_type_map[attribute.name]
                        != attribute_list_element_value_type
                    ):
                        raise errors.AttributeValidationInconsistentListElementValueTypesMultipleAttributesError(
                            attribute_name=attribute.name,
                            annotatable_type=annotatable_type,
                            found_value_types=[
                                name_list_element_value_type_map[attribute.name],
                                attribute_list_element_value_type,
                            ],
                        )
                else:
                    name_list_element_value_type_map[
                        attribute.name
                    ] = attribute_list_element_value_type

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
