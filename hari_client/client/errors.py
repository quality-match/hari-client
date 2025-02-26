import typing

import requests

from hari_client.models import models

T = typing.TypeVar("T")


class APIError(Exception):
    def __init__(self, response: requests.Response):
        http_response_status_code = response.status_code
        message = ""
        try:
            message = response.json()
        except:
            pass
        super().__init__(f"{http_response_status_code=}: {message=}")


class AuthenticationError(APIError):
    pass


class ParseResponseModelError(Exception):
    def __init__(
        self,
        response_data: typing.Any,
        response_model: T,
        message: str | None = "",
    ):
        self.response_data = response_data
        self.response_model = response_model
        if message:
            self.message = message
        else:
            self.message = f"{response_data=}, {response_model=}"

        super().__init__(self.message)


class MediaCreateMissingFilePathError(Exception):
    def __init__(self, media_create: models.MediaCreate):
        super().__init__(
            f"The 'file_path' has to be set when using an instance of models.MediaCreate in HARIClient.create_medias() when with_media_files_upload is True. {media_create.back_reference=}"
        )


class MediaCreateMissingFileKeyError(Exception):
    def __init__(self, media_create: models.MediaCreate):
        super().__init__(
            f"The 'file_key' has to be set when using an instance of models.MediaCreate in HARIClient.create_medias() when with_media_files_upload is False. {media_create.back_reference=}"
        )


class MediaFileExtensionNotIdentifiedDuringUploadError(Exception):
    def __init__(self, file_path: str):
        super().__init__(
            f"The media file extension of the provided file_path could not be identified when trying to upload the file: {file_path}"
        )


class BulkUploadSizeRangeError(Exception):
    def __init__(self, limit: int, found_amount: int):
        super().__init__(
            f"You tried uploading {found_amount} items at once, but it has to be at least 1 and max {limit}"
        )


class ParameterNumberRangeError(Exception):
    def __init__(
        self,
        param_name: str,
        minimum: int | float,
        maximum: int | float,
        value: int | float,
    ):
        super().__init__(
            f"The valid range for the {param_name} parameter is: {minimum=}, {maximum=}, but actual value is {value=}"
        )


class ParameterListLengthError(Exception):
    def __init__(
        self,
        param_name: str,
        minimum: int,
        maximum: int,
        length: int,
    ):
        super().__init__(
            f"The valid length for the {param_name} parameter is: {minimum=}, {maximum=}, but actual length is {length=}"
        )


class BulkOperationAnnotatableIdMissing(Exception):
    def __init__(self):
        message = (
            "The 'bulk_operation_annotatable_id' field is missing. "
            "Please include 'bulk_operation_annotatable_id' for each item to proceed with this bulk operation. "
            "Its value should be a unique UUID for each item within the bulk."
        )
        super().__init__(message)


class AttributeValidationInconsistentValueTypeError(Exception):
    def __init__(
        self, attribute_name: str, annotatable_type: str, found_value_types: list[str]
    ):
        message = (
            f"Found multiple value types {found_value_types} for attribute {attribute_name} with {annotatable_type=}."
            + " Make sure every attribute with the same name and annotatable type has the same value type."
        )
        super().__init__(message)


class AttributeValidationInconsistentListElementValueTypesError(Exception):
    def __init__(
        self, attribute_name: str, annotatable_type: str, found_value_types: list[str]
    ):
        message = (
            f"Found multiple list element value types {found_value_types} for attribute {attribute_name} with {annotatable_type=}."
            + " Make sure every list element has the same value type."
        )
        super().__init__(message)


class AttributeValidationInconsistentListElementValueTypesMultipleAttributesError(
    Exception
):
    def __init__(
        self, attribute_name: str, annotatable_type: str, found_value_types: list[str]
    ):
        message = (
            f"Found multiple instances of attribute {attribute_name} with {annotatable_type=} with inconsistent list element value types {found_value_types}."
            + " Make sure every instance of this attribute uses the same list element value types."
        )
        super().__init__(message)


class AttributeValidationIdNotReusedError(Exception):
    def __init__(
        self, attribute_name: str, annotatable_type: str, found_ids: list[str]
    ):
        message = (
            f"Found multiple ids {found_ids} for the same attribute name {attribute_name} with {annotatable_type=}."
            + " Make sure every attribute with the same name and annotatable type is using the same id."
        )
        super().__init__(message)
