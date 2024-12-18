import numbers
import typing

from hari_client import errors
from hari_client import models


def validate_attributes(
    attributes: list[models.AttributeCreate],
) -> None:
    """Raises an error if any requirements for attribute consistency aren't met.
    Basic attribute requirements:
    - attributes with the same name and annotatable type must
        - have the same id
        - have the same value type
            - additionally attributes with value type list must
                - have consistent list element value types (for example: all elements are strings; the list fits list[str])
                - have consistent list element value types across all attributes with that name (for example: all attributes with name "my_attribute" have a value that fits list[str])
            - Exceptions:
                - The value `None` isn't taken into account when value type consistency is checked.
                - Numeric types (int, float) are treated as the same value type can be mixed

    Args:
        attributes: List of attributes to validate.

    Raises:
        AttributeValidationInconsistentValueTypeError: If the value type for an attribute is inconsistent.
        AttributeValidationInconsistentListElementValueTypesError: If the elements in a list attribute value have inconsistent value types.
        AttributeValidationInconsistentListElementValueTypesMultipleAttributesError: If multiple list attributes have inconsistent element value types.
        AttributeValidationIdNotReusedError: If multiple attributes with the same name and annotatable type have different ids.
    """
    grouped_by_annotatable_type: dict[str, list[models.AttributeCreate]] = {
        models.DataBaseObjectType.MEDIA: [],
        models.DataBaseObjectType.MEDIAOBJECT: [],
        models.DataBaseObjectType.INSTANCE: [],
    }
    for attribute in attributes:
        grouped_by_annotatable_type[attribute.annotatable_type].append(attribute)

    for attributes_with_same_annotatable_type in grouped_by_annotatable_type.values():
        validator = AttributeConsistencyValidator(
            attributes=attributes_with_same_annotatable_type
        )
        validator.validate_attributes()


class AttributeConsistencyValidator:
    attributes: list[models.AttributeCreate]

    # to check the value type consistency of attribute.value
    name_value_type_map: dict[str, str]

    # to check the value type consistency of list elements, when attribute.value is a list
    name_list_element_value_type_map: dict[str, str]

    # to check whether the ids are reused as expected
    name_id_map: dict[str, str]

    def __init__(self, attributes: list[models.AttributeCreate]):
        self.attributes = attributes
        self.name_value_type_map = {}
        self.name_list_element_value_type_map = {}
        self.name_id_map = {}

    def validate_attributes(self) -> None:
        """Validates that attributes in a list have consistent value types and ids."""
        for attribute in self.attributes:
            value_type = self._check_value_type(attribute)

            # None values automatically pass the value type consistency check
            if value_type != "NoneType":
                self._check_list_elements_value_types(attribute, value_type)

            self._check_attribute_id_usage(attribute)

    def _check_value_type(self, attribute: models.AttributeCreate) -> str:
        value_type = _get_value_type_for_comparison(attribute.value)

        # None values automatically pass the value type consistency check
        if value_type == "NoneType":
            return value_type

        if attribute.name in self.name_value_type_map:
            if self.name_value_type_map[attribute.name] != value_type:
                raise errors.AttributeValidationInconsistentValueTypeError(
                    attribute_name=attribute.name,
                    annotatable_type=attribute.annotatable_type,
                    found_value_types=[
                        self.name_value_type_map[attribute.name],
                        value_type,
                    ],
                )
        else:
            self.name_value_type_map[attribute.name] = value_type

        return value_type

    def _check_list_elements_value_types(
        self, attribute: models.AttributeCreate, value_type: str
    ) -> None:
        # check list elements if value type is list
        if value_type != "list" or attribute.value == []:
            return

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
                annotatable_type=attribute.annotatable_type,
                found_value_types=found_list_element_value_types,
            )
        # check list element value type consistency across attributes
        attribute_list_element_value_type = list(found_list_element_value_types)[0]
        if attribute.name in self.name_list_element_value_type_map:
            if (
                self.name_list_element_value_type_map[attribute.name]
                != attribute_list_element_value_type
            ):
                raise errors.AttributeValidationInconsistentListElementValueTypesMultipleAttributesError(
                    attribute_name=attribute.name,
                    annotatable_type=attribute.annotatable_type,
                    found_value_types=[
                        self.name_list_element_value_type_map[attribute.name],
                        attribute_list_element_value_type,
                    ],
                )
        else:
            self.name_list_element_value_type_map[
                attribute.name
            ] = attribute_list_element_value_type

    def _check_attribute_id_usage(self, attribute: models.AttributeCreate) -> None:
        if attribute.name in self.name_id_map:
            if self.name_id_map[attribute.name] != str(attribute.id):
                raise errors.AttributeValidationIdNotReusedError(
                    attribute_name=attribute.name,
                    annotatable_type=attribute.annotatable_type,
                    found_ids=[
                        self.name_id_map[attribute.name],
                        str(attribute.id),
                    ],
                )
        else:
            self.name_id_map[attribute.name] = str(attribute.id)


def _get_value_type_for_comparison(value: typing.Any) -> str:
    """Gets the type of the value.
    If the value is a number, returns "number" for comparison."""
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        return "number"
    return type(value).__name__
