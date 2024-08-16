import pytest

from hari_client import Config
from hari_client import errors
from hari_client import HARIClient
from hari_client import models


def test_create_medias_with_missing_file_paths():
    # Arrange
    hari = HARIClient(config=Config(hari_username="abc", hari_password="123"))
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
    )

    # Act + Assert
    with pytest.raises(errors.MediaCreateMissingFilePathError):
        hari.create_medias(dataset_id="1234", medias=[media_create])


def test_create_medias_with_different_file_extensions():
    # Arrange
    hari = HARIClient(config=Config(hari_username="abc", hari_password="123"))
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

    # Act + Assert
    with pytest.raises(errors.UploadingFilesWithDifferentFileExtensionsError):
        hari.create_medias(dataset_id="1234", medias=[media_create_1, media_create_2])


def test_create_medias_with_too_many_objects():
    # Arrange
    hari = HARIClient(config=Config(hari_username="abc", hari_password="123"))
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media.jpg",
    )

    # Act + Assert
    with pytest.raises(errors.BulkUploadSizeRangeError):
        hari.create_medias(
            dataset_id="1234",
            medias=[media_create for i in range(HARIClient.BULK_UPLOAD_LIMIT + 1)],
        )


def test_create_media_objects_with_too_many_objects():
    # Arrange
    hari = HARIClient(config=Config(hari_username="abc", hari_password="123"))
    media_object_create = models.MediaObjectCreate(
        media_id="1234",
        source=models.DataSource.REFERENCE,
        back_reference="obj 1 - backref",
    )

    # Act + Assert
    with pytest.raises(errors.BulkUploadSizeRangeError):
        hari.create_media_objects(
            dataset_id="1234",
            media_objects=[
                media_object_create for i in range(HARIClient.BULK_UPLOAD_LIMIT + 1)
            ],
        )
