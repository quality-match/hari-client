from hari_client import models


def test_media_create_ignores_file_path_when_parsed_or_serialized():
    # Arrange
    media_create = models.MediaCreate(
        name="my test media",
        back_reference="my test media backref",
        media_type=models.MediaType.IMAGE,
        file_path="./my_test_media.jpg",
    )

    # Act
    media_create_dict = media_create.model_dump()
    media_create_from_dict = models.MediaCreate(**media_create_dict)

    # Assert
    assert "file_path" not in media_create_dict
    assert media_create_from_dict.file_path is None
