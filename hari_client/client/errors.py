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
        message: typing.Optional[str] = "",
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
    def __init__(self, found_extensions: list[str]):
        super().__init__(
            f"You can only upload files with the same file extension. Found: {found_extensions=}"
        )


class BulkUploadLimitExceededError(Exception):
    def __init__(self, limit: int, found_amount: int):
        super().__init__(
            f"You can only upload up to {limit=} objects at once. {found_amount=}"
        )
