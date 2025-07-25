import uuid

import pytest

from hari_client import errors
from hari_client import hari_uploader
from hari_client import models
from hari_client import validation

_some_uuids = [uuid.uuid4() for _ in range(10)]


@pytest.mark.parametrize(
    "attributes",
    [
        [
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_0",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=5,
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value="7",
            ),
        ],
        [
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_0",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=[5],
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value="7",
            ),
        ],
        [
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_0",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=[],
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value="7",
            ),
        ],
        [
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_0",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=True,
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value="banana",
            ),
        ],
        [
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_0",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=True,
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=False,
            ),
            models.AttributeCreate(
                id=_some_uuids[0],
                name="a",
                annotatable_id="media_1",
                annotatable_type=models.DataBaseObjectType.MEDIA,
                value=None,
            ),
            models.AttributeCreate(
                id=_some_uuids[1],
                name="b",
                annotatable_id="media_object_0",
                annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                value="banana",
            ),
            models.AttributeCreate(
                id=_some_uuids[1],
                name="b",
                annotatable_id="media_object_1",
                annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                value=0,
            ),
        ],
    ],
)
def test_attribute_validation_inconsistent_value_type(attributes):
    with pytest.raises(errors.AttributeValidationInconsistentValueTypeError):
        validation.validate_attributes(attributes)


@pytest.mark.parametrize(
    "attributes, expected_exception",
    [
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_1",
                    annotatable_type=models.DataBaseObjectType.MEDIA,
                    value=[5, 3, "seven", 4, 42],
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesError,
        ),
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_1",
                    annotatable_type=models.DataBaseObjectType.MEDIA,
                    value=[5, 3, 4.666, 42],
                ),
            ],
            None,
        ),
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_1",
                    annotatable_type=models.DataBaseObjectType.MEDIA,
                    value=[5, 3, False, 4, 42],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_0",
                    annotatable_type=models.DataBaseObjectType.MEDIA,
                    value=[7, 8, 2, 1, 0],
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesError,
        ),
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_0",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=[None, 7, 8, 2, 1, 0],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_1",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=["5", "hello_world", None, "banana"],
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesMultipleAttributesError,
        ),
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_0",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=[],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_1",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=["5", "hello_world", None, "banana"],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_1",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=[True, False, None, True],
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesMultipleAttributesError,
        ),
        (
            [
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_0",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=[True, False, False],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_2",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=["5", "hello_world", None, "banana"],
                ),
                models.AttributeCreate(
                    id=_some_uuids[0],
                    name="a",
                    annotatable_id="media_object_1",
                    annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
                    value=[True, False, None, True],
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesMultipleAttributesError,
        ),
    ],
)
def test_attribute_validation_inconsistent_list_element_value_types(
    attributes, expected_exception
):
    if expected_exception is None:
        validation.validate_attributes(attributes)
    else:
        with pytest.raises(expected_exception):
            validation.validate_attributes(attributes)


@pytest.mark.parametrize(
    "media_attributes, media_object_attributes, expected_exception_to_raise",
    [
        (
            [hari_uploader.HARIAttribute(id=_some_uuids[0], name="a", value=42)],
            [
                hari_uploader.HARIAttribute(
                    id=_some_uuids[1], name="b", value="banana"
                ),
                hari_uploader.HARIAttribute(id=_some_uuids[1], name="b", value=47),
            ],
            errors.AttributeValidationInconsistentValueTypeError,
        ),
        (
            [hari_uploader.HARIAttribute(id=_some_uuids[0], name="a", value=42)],
            [
                hari_uploader.HARIAttribute(
                    id=_some_uuids[1], name="b", value=[1, 2, 42, 37]
                ),
                hari_uploader.HARIAttribute(
                    id=_some_uuids[1], name="b", value=[1, 2, 3, "four"]
                ),
            ],
            errors.AttributeValidationInconsistentListElementValueTypesError,
        ),
    ],
)
def test_attribute_validation_is_used_in_hari_uploader(
    media_attributes,
    media_object_attributes,
    expected_exception_to_raise,
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    mock_uploader: hari_uploader.HARIUploader = (
        create_configurable_mock_uploader_successful_single_batch(
            dataset_id=uuid.uuid4(), medias_cnt=1, media_objects_cnt=2, attributes_cnt=3
        )[0]
    )
    medias = [
        hari_uploader.HARIMedia(
            file_path="./img_1.jpg",
            name="media_1",
            media_type=models.MediaType.IMAGE,
            back_reference="media_1 backref",
        )
    ]
    media_object_1 = hari_uploader.HARIMediaObject(
        back_reference="media object 1 backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=100,
            y=100,
            width=200,
            height=200,
        ),
    )
    media_object_2 = hari_uploader.HARIMediaObject(
        back_reference="media object 2 backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=300,
            y=300,
            width=200,
            height=200,
        ),
    )
    for attribute in media_attributes:
        medias[0].add_attribute(attribute)
    media_object_1.add_attribute(media_object_attributes[0])
    media_object_2.add_attribute(media_object_attributes[1])
    medias[0].add_media_object(media_object_1, media_object_2)

    # Act + Assert
    mock_uploader.add_media(*medias)
    with pytest.raises(expected_exception_to_raise):
        mock_uploader.upload()

    # attribute annotatable_type was set for all attributes
    assert media_attributes[0].annotatable_type == models.DataBaseObjectType.MEDIA
    assert (
        media_object_attributes[0].annotatable_type
        == models.DataBaseObjectType.MEDIAOBJECT
    )
    assert (
        media_object_attributes[1].annotatable_type
        == models.DataBaseObjectType.MEDIAOBJECT
    )


def test_attribute_validations_successful_case():
    attributes = [
        # numeric attribute
        models.AttributeCreate(
            id=_some_uuids[0],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_number",
            value=42,
        ),
        models.AttributeCreate(
            id=_some_uuids[0],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_number",
            value=43.643,
        ),
        models.AttributeCreate(
            id=_some_uuids[0],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_number",
            value=None,
        ),
        # string attribute
        models.AttributeCreate(
            id=_some_uuids[1],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_string",
            value="hello",
        ),
        models.AttributeCreate(
            id=_some_uuids[1],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_string",
            value="world",
        ),
        models.AttributeCreate(
            id=_some_uuids[1],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_string",
            value=None,
        ),
        # boolean attribute
        models.AttributeCreate(
            id=_some_uuids[2],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_boolean",
            value=True,
        ),
        models.AttributeCreate(
            id=_some_uuids[2],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_boolean",
            value=False,
        ),
        models.AttributeCreate(
            id=_some_uuids[2],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_boolean",
            value=None,
        ),
        # numeric list attribute
        models.AttributeCreate(
            id=_some_uuids[3],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_numeric_list",
            value=[0, 1, 2, 2.55],
        ),
        models.AttributeCreate(
            id=_some_uuids[3],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_numeric_list",
            value=[3.5, 4, None, 5],
        ),
        models.AttributeCreate(
            id=_some_uuids[3],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_numeric_list",
            value=None,
        ),
        models.AttributeCreate(
            id=_some_uuids[3],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_4",
            name="my_numeric_list",
            value=[None],
        ),
        models.AttributeCreate(
            id=_some_uuids[3],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_5",
            name="my_numeric_list",
            value=[],
        ),
        # boolean list attribute
        models.AttributeCreate(
            id=_some_uuids[4],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_boolean_list",
            value=[True, False, False],
        ),
        models.AttributeCreate(
            id=_some_uuids[4],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_boolean_list",
            value=[None, False, None, None],
        ),
        models.AttributeCreate(
            id=_some_uuids[4],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_boolean_list",
            value=None,
        ),
        models.AttributeCreate(
            id=_some_uuids[4],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_4",
            name="my_boolean_list",
            value=[None],
        ),
        models.AttributeCreate(
            id=_some_uuids[4],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_5",
            name="my_boolean_list",
            value=[],
        ),
        # string list attribute
        models.AttributeCreate(
            id=_some_uuids[5],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_1",
            name="my_string_list",
            value=["hello", None, "world"],
        ),
        models.AttributeCreate(
            id=_some_uuids[5],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_2",
            name="my_string_list",
            value=["0", "1", "5.33", None, "banana"],
        ),
        models.AttributeCreate(
            id=_some_uuids[5],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_3",
            name="my_string_list",
            value=None,
        ),
        models.AttributeCreate(
            id=_some_uuids[5],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_4",
            name="my_string_list",
            value=[None],
        ),
        models.AttributeCreate(
            id=_some_uuids[5],
            annotatable_type=models.DataBaseObjectType.MEDIA,
            annotatable_id="media_5",
            name="my_string_list",
            value=[],
        ),
    ]
    validation.validate_attributes(attributes)
