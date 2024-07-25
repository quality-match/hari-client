import typing

import requests

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
