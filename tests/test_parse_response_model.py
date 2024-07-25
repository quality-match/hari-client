import pydantic
import pytest

from hari_client import errors
from hari_client import models
from hari_client.client.client import _parse_response_model


@pytest.mark.parametrize(
    "response_data, response_model",
    [
        (2, int),
        (2.45, float),
        ("hello_world", str),
        ([1, 2, 3, {"a": 7}], list),
        ({"a": 1, "b": 6, "c": {"d": 99}}, dict),
    ],
)
def test_parse_response_model_works_with_basic_builtins(response_data, response_model):
    response = _parse_response_model(
        response_data=response_data, response_model=response_model
    )
    assert isinstance(response, response_model)
    assert response == response_data


def test_parse_response_model_works_with_none():
    response = _parse_response_model(response_data=None, response_model=None)
    assert response is None


def test_parse_response_model_works_with_pydantic_models():
    class MyModel(pydantic.BaseModel):
        a: int
        b: float
        c: str

    response = _parse_response_model(
        response_data={"a": 1, "b": 6.78, "c": "hello"}, response_model=MyModel
    )
    assert isinstance(response, MyModel)
    assert response.a == 1
    assert response.b == 6.78
    assert response.c == "hello"


def test_parse_response_model_works_with_list_of_pydantic_models():
    response_data = [
        {
            "upload_url": "http://example.com/upload/1234",
            "media_id": "1234",
            "media_url": "http://example.com/media/1234",
        },
        {
            "upload_url": "http://example.com/upload/5678",
            "media_id": "5678",
            "media_url": "http://example.com/media/5678",
        },
    ]

    response = _parse_response_model(
        response_data=response_data, response_model=models.MediaUploadUrlInfo
    )

    assert isinstance(response, list)

    for idx, item in enumerate(response):
        assert isinstance(item, models.MediaUploadUrlInfo)
        assert item.upload_url == response_data[idx]["upload_url"]
        assert item.media_id == response_data[idx]["media_id"]
        assert item.media_url == response_data[idx]["media_url"]


@pytest.mark.parametrize(
    "response_data, response_model",
    [
        (2, float),
        (2.45, int),
        ("hello_world", None),
        ([1, 2, 3, {"a": 7}], dict),
        ({"a": 1, "b": 6, "c": {"d": 99}}, list),
        (
            {
                "upload_url": "http://example.com/upload/1234",
                "media_id": "1234",
                "media_url": "http://example.com/media/1234",
            },
            models.VisualisationUploadUrlInfo,
        ),
    ],
)
def test_parse_response_model_fails_for_response_data_not_matching_expected_response_model(
    response_data, response_model
):
    with pytest.raises(errors.ParseResponseModelError):
        _parse_response_model(
            response_data=response_data, response_model=response_model
        )
