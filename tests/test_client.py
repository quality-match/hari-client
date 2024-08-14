import pytest

from hari_client import Config
from hari_client import HARIClient
from hari_client import models
from hari_client import errors


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
