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
            f"The 'file_path' has to be set when using an instance of models.MediaCreate in HARIClient.create_medias(). Found: {media_create.file_path=}"
        )


class UploadingFilesWithDifferentFileExtensionsError(Exception):
    def __init__(self, found_extensions: set[str]):
        super().__init__(
            f"You can only upload files with the same file extension. Found: {found_extensions=}"
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
