import pytest

from hari_client import errors
from hari_client import HARIClient
from hari_client import models


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
    mocker.patch.object(test_client, "_upload_file")
    mocker.patch.object(
        test_client,
        "get_presigned_media_upload_url",
        return_value=[mocker.MagicMock(), mocker.MagicMock()],
    )
    mocker.patch.object(test_client, "_request")

    get_presigned_media_upload_url_spy = mocker.spy(
        test_client, "get_presigned_media_upload_url"
    )
    upload_file_spy = mocker.spy(test_client, "_upload_file")
    request_spy = mocker.spy(test_client, "_request")

    # Act
    test_client.create_medias(
        dataset_id="1234", medias=[media_create_1, media_create_2]
    )

    # Assert
    # called twice, because every group of files with the same extension is uploaded in a separate batch
    assert get_presigned_media_upload_url_spy.call_count == 2
    # called once every file to upload (there are two files)
    assert upload_file_spy.call_count == 2
    # called once by create_medias. The call from get_presigned_media_upload_url is mocked out
    assert request_spy.call_count == 1


def test_create_medias_with_too_many_objects(test_client):
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
            medias=[media_create for i in range(HARIClient.BULK_UPLOAD_LIMIT + 1)],
        )


def test_create_media_objects_with_too_many_objects(test_client):
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
                media_object_create for i in range(HARIClient.BULK_UPLOAD_LIMIT + 1)
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
        match=f"value={HARIClient.BULK_UPLOAD_LIMIT + 1}",
    ):
        client.get_presigned_media_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            batch_size=HARIClient.BULK_UPLOAD_LIMIT + 1,
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
        match=f"value={HARIClient.BULK_UPLOAD_LIMIT + 1}",
    ):
        client.get_presigned_visualisation_upload_url(
            dataset_id="1234",
            file_extension=".jpg",
            visualisation_config_id="1234",
            batch_size=HARIClient.BULK_UPLOAD_LIMIT + 1,
        )


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
