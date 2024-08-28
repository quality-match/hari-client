import typing

import pydantic
import pytest

from hari_client import errors
from hari_client import models
from hari_client.client.client import _parse_response_model


class SimpleModel1(pydantic.BaseModel):
    a: int
    b: float
    c: str


class SimpleModel1WithRootField(pydantic.RootModel[list[SimpleModel1]]):
    pass


class SimpleModel2(pydantic.BaseModel):
    x: bool
    y: list
    z: dict


class SimpleModelWithRootFieldForUnionOfTwoModels(
    pydantic.RootModel[list[SimpleModel1 | SimpleModel2]]
):
    pass


class ComplexModelWithNestedListOfUnions(pydantic.BaseModel):
    i: int
    k: list[typing.Union[SimpleModel1, SimpleModel2]]


TestObject1 = {"a": 1, "b": 6.78, "c": "hello"}  # should be parsed into SimpleModel1
TestObject2 = {
    "x": False,
    "y": [1, 2],
    "z": {"m": 3},
}  # should be parsed into SimpleModel2


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
    response = _parse_response_model(
        response_data=TestObject1, response_model=SimpleModel1
    )
    assert isinstance(response, SimpleModel1)
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
        response_data=response_data, response_model=models.MediaUploadUrlInfoList
    )

    for idx, item in enumerate(response):
        assert isinstance(item, models.MediaUploadUrlInfo)
        assert item.upload_url == response_data[idx]["upload_url"]
        assert item.media_id == response_data[idx]["media_id"]
        assert item.media_url == response_data[idx]["media_url"]


type_mismatch_error_match = ".Types do not match."


@pytest.mark.parametrize(
    "response_data, response_model, error, error_message",
    [
        (2, float, errors.ParseResponseModelError, type_mismatch_error_match),
        (2.45, int, errors.ParseResponseModelError, type_mismatch_error_match),
        (
            "hello_world",
            None,
            errors.ParseResponseModelError,
            type_mismatch_error_match,
        ),
        (
            None,
            "hello_world",
            errors.ParseResponseModelError,
            type_mismatch_error_match,
        ),
        (
            [1, 2, 3, {"a": 7}],
            dict,
            errors.ParseResponseModelError,
            type_mismatch_error_match,
        ),
        (
            {"a": 1, "b": 6, "c": {"d": 99}},
            list,
            errors.ParseResponseModelError,
            type_mismatch_error_match,
        ),
        (
            {
                "upload_url": "http://example.com/upload/1234",
                "media_id": "1234",
                "media_url": "http://example.com/media/1234",
            },
            models.VisualisationUploadUrlInfo,
            pydantic.ValidationError,
            "Failed to parse response_data into response_model.",
        ),
    ],
)
def test_parse_response_model_fails_for_response_data_not_matching_expected_response_model(
    response_data, response_model, error, error_message
):
    with pytest.raises(errors.ParseResponseModelError, match=error_message):
        _parse_response_model(
            response_data=response_data, response_model=response_model
        )


def test_parse_response_model_works_with_pydantic_model_with_root_field_of_list():
    response = _parse_response_model(
        response_data=[TestObject1], response_model=SimpleModel1WithRootField
    )
    assert isinstance(response, SimpleModel1WithRootField)
    assert response.root[0].a == 1
    assert response.root[0].b == 6.78
    assert response.root[0].c == "hello"

    response = _parse_response_model(
        response_data=[TestObject1, TestObject2],
        response_model=SimpleModelWithRootFieldForUnionOfTwoModels,
    )
    assert isinstance(response, SimpleModelWithRootFieldForUnionOfTwoModels)
    assert response.root[0].a == 1
    assert response.root[0].b == 6.78
    assert response.root[0].c == "hello"

    assert isinstance(response, SimpleModelWithRootFieldForUnionOfTwoModels)
    assert response.root[1].x is False
    assert response.root[1].y == [1, 2]
    assert response.root[1].z == {"m": 3}
