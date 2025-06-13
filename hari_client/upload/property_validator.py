"""Entity validation for HARI uploads.

This module provides a class for validating HARI properties (medias, media objects)
and their relationships before uploading to HARI.
"""
from collections import defaultdict

from hari_client import models


class ValidationResult:
    """Results of property validation.

    Stores found values and validation errors.
    """

    def __init__(self) -> None:
        """Initialize a new validation result."""
        self.found_values: dict[str, set[str]] = {}
        self.errors: dict[str, list[Exception]] = {}

    def has_errors(self) -> bool:
        """Check if there are any validation errors.

        Returns:
            True if there are errors, False otherwise.
        """
        return any(self.errors.values())

    def get_all_errors(self) -> list[Exception]:
        """Get all validation errors.

        Returns:
            List of all errors.
        """
        return [error for errors in self.errors.values() for error in errors]

    def add_found_value(self, field_name: str, value: str) -> None:
        """Add a found value.

        Args:
            field_name: The name of the field.
            value: The value found.
        """
        if field_name not in self.found_values:
            self.found_values[field_name] = set()
        self.found_values[field_name].add(value)

    def add_error(self, error_type: str, error: Exception) -> None:
        """Add a validation error.

        Args:
            error_type: The type of the error.
            error: The error to add.
        """
        if error_type not in self.errors:
            self.errors[error_type] = []
        self.errors[error_type].append(error)


class PropertyValidator:
    """Validates HARI properties and their relationships."""

    def __init__(
        self,
        allowed_values: dict[str, set[str]],
        consistency_fields: list[str] | None = None,
    ) -> None:
        """Initialize the validator.

        Args:
            allowed_values: Dict mapping field names to sets of allowed values.
            consistency_fields: List of field names to check for consistency.
                Defaults to None.
        """
        self.allowed_values = allowed_values
        self.consistency_fields = consistency_fields or []

        # Define which object types each field applies to
        self.field_applicability = {
            "scene_back_reference": ["media", "media_object"],
            "object_category_subset_name": ["media_object"],
        }

    def validate_field(
        self,
        obj: models.BulkMediaCreate | models.BulkMediaObjectCreate,
        field_name: str,
        object_type: str,
        result: ValidationResult,
        error_class: type[Exception],
    ) -> bool:
        """Validate a single field on an object.

        Args:
            obj: The object to validate.
            field_name: The name of the field to validate.
            object_type: The type of object (e.g. "media", "media_object").
            result: The validation result to update.
            error_class: The exception class to use for validation errors.

        Returns:
            True if the field exists and has a value, False otherwise.
        """
        # Skip validation if field doesn't exist or has no value
        if not hasattr(obj, field_name) or getattr(obj, field_name) is None:
            return False

        # Skip validation if field isn't applicable to this object type
        if (
            field_name in self.field_applicability
            and object_type not in self.field_applicability[field_name]
        ):
            return False

        field_value = getattr(obj, field_name)
        result.add_found_value(field_name, field_value)

        # Validate against allowed values
        if (
            field_name in self.allowed_values
            and field_value not in self.allowed_values[field_name]
        ):
            result.add_error(
                field_name,
                error_class(
                    f"A {field_name} for the specified value ({field_value}) wasn't specified. "
                    f"Only the values that were specified in the HARIUploader constructor are allowed: "
                    f"{self.allowed_values[field_name]}. {object_type}: {obj}"
                ),
            )

        return True

    def validate_consistency(
        self,
        media: models.BulkMediaCreate,
        media_object: models.BulkMediaObjectCreate,
        result: ValidationResult,
        error_class: type[Exception],
    ) -> None:
        """Validate consistency between a media and a media object.

        Args:
            media: The media object.
            media_object: The media object to validate.
            result: The validation result to update.
            error_class: The exception class to use for consistency errors.
        """
        for field_name in self.consistency_fields:
            # Skip if either doesn't have the field or field is None
            if (
                not hasattr(media, field_name)
                or not hasattr(media_object, field_name)
                or getattr(media, field_name) is None
                or getattr(media_object, field_name) is None
            ):
                continue

            media_value = getattr(media, field_name)
            media_object_value = getattr(media_object, field_name)

            if media_value != media_object_value:
                result.add_error(
                    "consistency",
                    error_class(
                        f"Media and Media Object {field_name} are inconsistent. "
                        f"Media {field_name}: {media_value}, Media Object {field_name}: {media_object_value}. "
                        f"Media (back_ref: {getattr(media, 'back_reference', 'N/A')}), "
                        f"Media Object (back_ref: {getattr(media_object, 'back_reference', 'N/A')})"
                    ),
                )

    def collect_frame_info(
        self, properties: list[models.BulkMediaCreate], field_name: str
    ) -> dict[str, set[int]]:
        """Collect frame information for scenes.

        Args:
            properties: List of properties to collect from.
            field_name: The field name to collect from.

        Returns:
            Dict mapping field values to sets of frame indices.
        """
        frame_info = defaultdict(set)

        for property in properties:
            # Check the property
            if (
                hasattr(property, field_name)
                and getattr(property, field_name) is not None
                and hasattr(property, "frame_idx")
                and property.frame_idx is not None
            ):
                field_value = getattr(property, field_name)
                frame_info[field_value].add(property.frame_idx)

            # Check media objects if this is a media
            if hasattr(property, "media_objects"):
                for media_object in property.media_objects:
                    if (
                        hasattr(media_object, field_name)
                        and getattr(media_object, field_name) is not None
                        and hasattr(media_object, "frame_idx")
                        and media_object.frame_idx is not None
                    ):
                        field_value = getattr(media_object, field_name)
                        frame_info[field_value].add(media_object.frame_idx)

        return frame_info

    def validate_properties(
        self,
        medias: list[models.BulkMediaCreate],
        scene_error_class: type[Exception],
        category_error_class: type[Exception],
        consistency_error_class: type[Exception],
    ) -> tuple[bool, ValidationResult, dict[str, list[str]]]:
        """Validate medias and their media objects.

        Args:
            medias: The medias to validate.
            scene_error_class: The exception class for scene validation errors.
            category_error_class: The exception class for category validation errors.
            consistency_error_class: The exception class for consistency errors.

        Returns:
            A tuple containing:
                - Whether validation succeeded (no errors)
                - The validation result
                - A dictionary with properties to create by field name
        """
        result = ValidationResult()

        # Map field names to their error classes
        field_error_classes = {
            "scene_back_reference": scene_error_class,
            "object_category_subset_name": category_error_class,
        }

        # Track values to create
        to_create: dict[str, list[str]] = {field: [] for field in self.allowed_values}

        # Validate all medias and media objects
        for media in medias:
            # Validate fields on media
            for field_name in self.allowed_values:
                if self.validate_field(
                    media, field_name, "media", result, field_error_classes[field_name]
                ):
                    # Add to creation list if not already there
                    field_value = getattr(media, field_name)
                    if field_value not in to_create[field_name]:
                        to_create[field_name].append(field_value)

            # Validate media objects
            for media_object in media.media_objects:
                # Validate fields on media object
                for field_name in self.allowed_values:
                    if self.validate_field(
                        media_object,
                        field_name,
                        "media_object",
                        result,
                        field_error_classes[field_name],
                    ):
                        # Add to creation list if not already there
                        field_value = getattr(media_object, field_name)
                        if field_value not in to_create[field_name]:
                            to_create[field_name].append(field_value)

                # Validate consistency
                self.validate_consistency(
                    media, media_object, result, consistency_error_class
                )

        return not result.has_errors(), result, to_create
