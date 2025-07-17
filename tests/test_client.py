import json
import uuid

import pytest

from hari_client import errors
from hari_client import models
from hari_client.client import client
from hari_client.config import config


def test_create_medias_with_missing_file_paths(test_client):
    # Arrange
    client = test_client
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
    )

    # Act + Assert
    with pytest.raises(errors.MediaCreateMissingFilePathError):
        client.create_medias(dataset_id="1234", medias=[media_create])


def test_create_medias_with_missing_file_keys(test_client):
    # Arrange
    client = test_client
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
    )

    # Act + Assert
    with pytest.raises(errors.MediaCreateMissingFileKeyError):
        client.create_medias(
            dataset_id="1234", medias=[media_create], with_media_files_upload=False
        )


def test_create_medias_without_media_files_upload(test_client_mocked, mocker):
    # Arrange
    upload_media_files_spy = mocker.spy(
        test_client_mocked, "_upload_media_files_with_presigned_urls"
    )
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_key="path/to/image_1.jpg",
    )

    # Act
    test_client_mocked.create_medias(
        dataset_id=uuid.uuid4(), medias=[media_create], with_media_files_upload=False
    )

    # Assert
    assert upload_media_files_spy.call_count == 0


def test_create_medias_with_media_files_upload(test_client_mocked, mocker):
    # Arrange
    mocker.patch.object(test_client_mocked, "_upload_media_files_with_presigned_urls")
    upload_media_files_spy = mocker.spy(
        test_client_mocked, "_upload_media_files_with_presigned_urls"
    )
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="path/to/image_1.jpg",
    )

    # Act
    test_client_mocked.create_medias(
        dataset_id=uuid.uuid4(), medias=[media_create], with_media_files_upload=True
    )

    # Assert
    assert upload_media_files_spy.call_count == 1


def test_create_media_with_missing_file_path(test_client_mocked, mocker):
    with pytest.raises(errors.MediaCreateMissingFilePathError):
        test_client_mocked.create_media(
            dataset_id=uuid.uuid4(),
            name="my test media",
            back_reference="my test media backref",
            media_type=models.MediaType.IMAGE,
            file_path=None,
            with_media_files_upload=True,
        )


def test_create_media_with_missing_file_key(test_client_mocked, mocker):
    with pytest.raises(errors.MediaCreateMissingFileKeyError):
        test_client_mocked.create_media(
            dataset_id=uuid.uuid4(),
            name="my test media",
            back_reference="my test media backref",
            media_type=models.MediaType.IMAGE,
            file_path=None,
            with_media_files_upload=False,
        )


def test_create_media_with_media_file_upload(test_client_mocked, mocker):
    # Arrange
    mocker.patch.object(test_client_mocked, "_upload_media_files_with_presigned_urls")
    upload_media_files_spy = mocker.spy(
        test_client_mocked, "_upload_media_files_with_presigned_urls"
    )

    # Act
    test_client_mocked.create_media(
        dataset_id=uuid.uuid4(),
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="path/to/image_1.jpg",
        with_media_files_upload=True,
    )

    # Assert
    assert upload_media_files_spy.call_count == 1


def test_create_media_without_media_file_upload(test_client_mocked, mocker):
    # Arrange
    mocker.patch.object(test_client_mocked, "_upload_media_files_with_presigned_urls")
    upload_media_files_spy = mocker.spy(
        test_client_mocked, "_upload_media_files_with_presigned_urls"
    )

    # Act
    test_client_mocked.create_media(
        dataset_id=uuid.uuid4(),
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path=None,
        file_key="path/to/image_1.jpg",
        with_media_files_upload=False,
    )

    # Assert
    assert upload_media_files_spy.call_count == 0


def test_create_medias_with_different_file_extensions_works(test_client, mocker):
    # Arrange
    media_create_1 = models.MediaCreate(
        name="my test media 1",
        back_reference="my test media 1 backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media_1.jpg",
    )
    media_create_2 = models.MediaCreate(
        name="my test media 2",
        back_reference="my test media 2 backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media_2.png",
    )
    media_create_3 = models.MediaCreate(
        name="my test media 3",
        back_reference="my test media 3 backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media_3.jpg",
    )
    mocker.patch.object(test_client, "_upload_file")
    mocker.patch.object(
        test_client,
        "get_presigned_media_upload_url",
        side_effect=[
            # first call: the two jpg files for media_create_1 and media_create_3
            [mocker.MagicMock(media_url="url_1"), mocker.MagicMock(media_url="url_3")],
            # second call: the png file for media_create_2
            [mocker.MagicMock(media_url="url_2")],
        ],
    )
    mocker.patch.object(test_client, "_request")

    get_presigned_media_upload_url_spy = mocker.spy(
        test_client, "get_presigned_media_upload_url"
    )
    upload_file_spy = mocker.spy(test_client, "_upload_file")
    request_spy = mocker.spy(test_client, "_request")

    # Act
    test_client.create_medias(
        dataset_id="1234", medias=[media_create_1, media_create_2, media_create_3]
    )

    # Assert
    # called twice, because every group of files with the same extension is uploaded in a separate batch
    assert get_presigned_media_upload_url_spy.call_count == 2
    # called once every file to upload (there are three files)
    assert upload_file_spy.call_count == 3
    # called once by create_medias. The call from get_presigned_media_upload_url is mocked out
    assert request_spy.call_count == 1

    # check that each media received the correct url
    assert media_create_1.media_url == "url_1"
    assert media_create_2.media_url == "url_2"
    assert media_create_3.media_url == "url_3"

    # check order of _upload_file calls
    assert (
        upload_file_spy.call_args_list[0].kwargs["file_path"] == "./my_test_media_1.jpg"
    )
    assert (
        upload_file_spy.call_args_list[1].kwargs["file_path"] == "./my_test_media_3.jpg"
    )
    assert (
        upload_file_spy.call_args_list[2].kwargs["file_path"] == "./my_test_media_2.png"
    )


def test_create_medias_with_unidentifiable_file_extension(test_client):
    # Arrange
    client = test_client
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media.jpg",
    )
    media_create_broken = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media",
    )

    # Act + Assert
    with pytest.raises(errors.MediaFileExtensionNotIdentifiedDuringUploadError):
        client.create_medias(
            dataset_id="1234", medias=[media_create, media_create_broken]
        )


def test_create_too_many_medias(test_client):
    # Arrange
    client = test_client
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media.jpg",
    )

    # Act + Assert
    with pytest.raises(errors.BulkUploadSizeRangeError):
        client.create_medias(
            dataset_id="1234",
            medias=[media_create for i in range(config.MEDIA_BULK_UPLOAD_LIMIT + 1)],
        )


def test_create_too_many_media_objects(test_client):
    # Arrange
    client = test_client
    media_object_create = models.MediaObjectCreate(
        media_id="1234",
        source=models.DataSource.REFERENCE,
        back_reference="obj 1 - backref",
    )

    # Act + Assert
    with pytest.raises(errors.BulkUploadSizeRangeError):
        client.create_media_objects(
            dataset_id="1234",
            media_objects=[
                media_object_create
                for i in range(config.MEDIA_OBJECT_BULK_UPLOAD_LIMIT + 1)
            ],
        )


def test_create_too_many_attributes(test_client):
    # Arrange
    client = test_client
    attribute_create = models.AttributeCreate(
        id=uuid.uuid4(),
        annotatable_id="id",
        annotatable_type="Media",
        name="name",
        value="value",
    )

    # Act + Assert
    with pytest.raises(errors.BulkUploadSizeRangeError):
        client.create_attributes(
            dataset_id="1234",
            attributes=[
                attribute_create for i in range(config.ATTRIBUTE_BULK_UPLOAD_LIMIT + 1)
            ],
        )


def test_get_presigned_media_upload_url_batch_size_range(test_client):
    # Arrange
    client = test_client

    # Act + Assert
    with pytest.raises(errors.ParameterNumberRangeError, match="value=0"):
        client.get_presigned_media_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            batch_size=0,
        )

    with pytest.raises(
        errors.ParameterNumberRangeError,
        match=f"value={config.PRESIGNED_URL_MAX_BATCH_SIZE + 1}",
    ):
        client.get_presigned_media_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            batch_size=config.PRESIGNED_URL_MAX_BATCH_SIZE + 1,
        )


def test_get_presigned_visualisation_upload_url_batch_size_range(test_client):
    # Arrange
    client = test_client

    # Act + Assert
    with pytest.raises(errors.ParameterNumberRangeError, match="value=0"):
        client.get_presigned_visualisation_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            visualisation_config_id="1234",
            batch_size=0,
        )

    with pytest.raises(
        errors.ParameterNumberRangeError,
        match=f"value={config.PRESIGNED_URL_MAX_BATCH_SIZE + 1}",
    ):
        client.get_presigned_visualisation_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            visualisation_config_id="1234",
            batch_size=config.PRESIGNED_URL_MAX_BATCH_SIZE + 1,
        )


def test_upload_media_files_with_presigned_urls_with_multiple_file_extensions(
    test_client, mocker
):
    # Arrange
    mocker.patch.object(test_client, "_upload_file")
    # there are two different file extensions in the test with two files each so two presigned urls are returned
    # for every call
    file_paths = {
        0: "./my_test_media_1.jpg",
        1: "./my_test_media_2.png",
        2: "./my_test_media_3.jpg",
        3: "./my_test_media_4.png",
    }

    def get_presigned_media_upload_url_side_effect_function(
        dataset_id, file_extension, batch_size
    ):
        response = []
        for i in range(batch_size):
            # creates idx 1, 2 in the first call, and 3, 4 in the second call of the method
            idx = i + get_presigned_media_upload_url_spy.call_count
            if get_presigned_media_upload_url_spy.call_count > 1:
                idx += 1
            response.append(
                models.MediaUploadUrlInfo(
                    media_id=f"id_{idx}",
                    media_url=f"media_url_{idx}{file_extension}",
                    upload_url=f"upload_url_{idx}",
                )
            )

        return response

    mocker.patch.object(
        test_client,
        "get_presigned_media_upload_url",
        side_effect=get_presigned_media_upload_url_side_effect_function,
    )
    upload_file_spy = mocker.spy(test_client, "_upload_file")
    get_presigned_media_upload_url_spy = mocker.spy(
        test_client, "get_presigned_media_upload_url"
    )

    # Act
    presign_responses = test_client._upload_media_files_with_presigned_urls(
        dataset_id=uuid.uuid4(),
        file_paths=file_paths,
    )

    # Assert
    assert upload_file_spy.call_count == 4
    assert get_presigned_media_upload_url_spy.call_count == 2
    assert len(presign_responses) == 4

    # the order of file_paths is the same as the order of presign_responses
    # but the _upload_file method is called in a different order, because of the
    # different file extensions
    assert presign_responses[0].media_url.endswith("1.jpg")
    assert upload_file_spy.call_args_list[0].kwargs["file_path"] == file_paths[0]
    assert presign_responses[1].media_url.endswith("3.png")
    assert upload_file_spy.call_args_list[1].kwargs["file_path"] == file_paths[2]
    assert presign_responses[2].media_url.endswith("2.jpg")
    assert upload_file_spy.call_args_list[2].kwargs["file_path"] == file_paths[1]
    assert presign_responses[3].media_url.endswith("4.png")
    assert upload_file_spy.call_args_list[3].kwargs["file_path"] == file_paths[3]


def test_upload_media_files_with_presigned_urls_with_single_file_extension(
    test_client, mocker
):
    # Arrange
    mocker.patch.object(test_client, "_upload_file")
    # there's only one file extension in the test with four files so four presigned urls are returned
    # for the call
    mocker.patch.object(
        test_client,
        "get_presigned_media_upload_url",
        return_value={
            0: mocker.MagicMock(),
            1: mocker.MagicMock(),
            2: mocker.MagicMock(),
            3: mocker.MagicMock(),
        },
    )
    upload_file_spy = mocker.spy(test_client, "_upload_file")
    get_presigned_media_upload_url_spy = mocker.spy(
        test_client, "get_presigned_media_upload_url"
    )
    presign_responses = test_client._upload_media_files_with_presigned_urls(
        dataset_id=uuid.uuid4(),
        file_paths={
            0: "./my_test_media_1.jpg",
            1: "./my_test_media_2.jpg",
            2: "./my_test_media_3.jpg",
            3: "./my_test_media_4.jpg",
        },
    )
    assert upload_file_spy.call_count == 4
    assert get_presigned_media_upload_url_spy.call_count == 1
    assert len(presign_responses) == 4


def test_trigger_metadata_rebuild_validation_for_dataset_ids_list(test_client):
    # Arrange
    client = test_client

    # Act + Assert
    with pytest.raises(errors.ParameterListLengthError, match="length=0"):
        client.trigger_metadata_rebuild_job(
            dataset_ids=[],
        )

    with pytest.raises(errors.ParameterListLengthError, match="length=11"):
        client.trigger_metadata_rebuild_job(
            dataset_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        )


@pytest.mark.parametrize(
    "params, expected",
    [
        # None stays None
        ({"query": None, "other": None}, {"query": None, "other": None}),
        (
            {"projection": {"name": False, "url": False}},
            {"projection": '{"name": false, "url": false}'},
        ),
        # multiple typical query parameters (not related to QueryList)
        (
            {
                "limit": 100,
                "offset": 5.45,
                "with_filter": True,
                "id": "abcd-0123",
                "my_none": None,
                "my_list": [0, 1, 2, "three", 4.5, None, False, True],
            },
            {
                "limit": 100,
                "offset": 5.45,
                "with_filter": True,
                "id": "abcd-0123",
                "my_none": None,
                "my_list": [0, 1, 2, "three", 4.5, None, False, True],
            },
        ),
        # single stringified QueryParameter
        (
            {
                "query": json.dumps(
                    {
                        "attribute": "attribute_group",
                        "query_operator": "==",
                        "value": models.AttributeGroup.InitialAttribute,
                    }
                )
            },
            {
                "query": '{"attribute": "attribute_group", "query_operator": "==", "value": "initial_attribute"}'
            },
        ),
        # list of two stringified QueryParameters
        (
            {
                "query": [
                    json.dumps(
                        {
                            "attribute": "attribute_group",
                            "query_operator": "==",
                            "value": models.AttributeGroup.InitialAttribute,
                        }
                    ),
                    json.dumps(
                        {
                            "attribute": "id",
                            "query_operator": "==",
                            "value": "banana",
                        }
                    ),
                ]
            },
            {
                "query": [
                    '{"attribute": "attribute_group", "query_operator": "==", "value": "initial_attribute"}',
                    '{"attribute": "id", "query_operator": "==", "value": "banana"}',
                ]
            },
        ),
        # QueryList with one QueryParameter
        (
            {
                "query": [
                    models.QueryParameter(
                        attribute="attribute_group",
                        query_operator="==",
                        value=models.AttributeGroup.InitialAttribute,
                    )
                ]
            },
            {
                "query": [
                    '{"attribute": "attribute_group", "query_operator": "==", "value": "initial_attribute"}'
                ]
            },
        ),
        # QueryList with two QueryParameters
        (
            {
                "query": [
                    models.QueryParameter(
                        attribute="attribute_group",
                        query_operator="==",
                        value=models.AttributeGroup.InitialAttribute,
                    ),
                    models.QueryParameter(
                        attribute="id",
                        query_operator="==",
                        value="banana",
                    ),
                ]
            },
            {
                "query": [
                    '{"attribute": "attribute_group", "query_operator": "==", "value": "initial_attribute"}',
                    '{"attribute": "id", "query_operator": "==", "value": "banana"}',
                ]
            },
        ),
        # QueryList with one LogicParameter that contains two QueryParameters
        (
            {
                "query": [
                    models.LogicParameter(
                        operator="and",
                        queries=[
                            models.QueryParameter(
                                attribute="attribute_group",
                                query_operator="==",
                                value=models.AttributeGroup.InitialAttribute,
                            ),
                            models.QueryParameter(
                                attribute="id",
                                query_operator="==",
                                value="banana",
                            ),
                        ],
                    )
                ]
            },
            {
                "query": [
                    '{"operator": "and", "queries": [{"attribute": "attribute_group", "query_operator": "==", "value": "initial_attribute"},'
                    + ' {"attribute": "id", "query_operator": "==", "value": "banana"}]}'
                ]
            },
        ),
    ],
)
def test_request_query_params_are_prepared_correctly(params, expected):
    # Arrange + Act
    prepared_params = client._prepare_request_query_params(params)

    # Assert
    assert expected == prepared_params
    for param_name, param_value in expected.items():
        if isinstance(param_value, list):
            for prepared_param_value, expected_param_value in zip(
                prepared_params[param_name], param_value
            ):
                assert expected_param_value == prepared_param_value


@pytest.mark.parametrize(
    "params, expected_exception, expected_message",
    [
        ({"projection": {"name": True, "id": True}}, None, None),
        ({"projection": True}, TypeError, "Projection should be a dictionary"),
        (
            {"projection": {"name": 0, "id": 1}},
            TypeError,
            "Invalid projection value for field 'name': expected boolean, got int",
        ),
        (
            {"projection": {"name": True, "id": False}},
            ValueError,
            "Mixing of True and False values in projection is not allowed",
        ),
    ],
)
def test_validate_request_query_params(params, expected_exception, expected_message):
    if expected_exception:
        with pytest.raises(expected_exception) as exc_info:
            client._validate_request_query_params(params)
        assert expected_message in str(exc_info.value)
    else:
        client._validate_request_query_params(params)
