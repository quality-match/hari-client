import collections
import uuid

import pytest

from hari_client import hari_uploader
from hari_client import models


def test_add_media(mock_uploader_for_object_category_validation):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation
    assert len(uploader._medias) == 0

    # Act
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image",
            media_type=models.MediaType.IMAGE,
            back_reference="img",
            attributes=[
                hari_uploader.HARIAttribute(
                    id=uuid.uuid4(),
                    name="my attribute 1",
                    value="value 1",
                )
            ],
        )
    )

    # Assert
    assert len(uploader._medias) == 1

    # Act
    # add another media without attributes
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image",
            media_type=models.MediaType.IMAGE,
            back_reference="img",
        )
    )
    # Assert
    assert len(uploader._medias) == 2


def test_create_object_category_subset_sets_uploader_attribute_correctly(
    mock_uploader_for_object_category_validation,
):
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    # Act
    obj_categories_to_create = [
        obj_cat for obj_cat in object_categories_vs_subsets.keys()
    ]
    uploader._create_object_category_subsets(obj_categories_to_create)

    # Assert
    assert uploader._object_category_subsets == object_categories_vs_subsets


def test_validate_media_objects_object_category_subsets_consistency(
    mock_uploader_for_object_category_validation,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
    )
    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")
    media_1.add_media_object(media_object_1)
    uploader.add_media(media_1)
    # Act
    (
        found_object_category_subset_names,
        errors,
    ) = uploader._get_and_validate_media_objects_object_category_subset_names()

    # Assert
    assert len(errors) == 0
    assert found_object_category_subset_names == {"pedestrian"}

    # Arrange
    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("some_non-existent-subset_name")
    media_1.add_media_object(media_object_2)

    # Act
    (
        found_object_category_subset_names,
        errors,
    ) = uploader._get_and_validate_media_objects_object_category_subset_names()

    # Assert
    assert len(errors) == 1
    assert (
        type(errors[0])
        == hari_uploader.HARIMediaObjectUnknownObjectCategorySubsetNameError
    )
    assert found_object_category_subset_names == {
        "pedestrian",
        "some_non-existent-subset_name",
    }


def test_assign_media_objects_to_object_category_subsets_sets_subset_ids_corectly(
    mock_uploader_for_object_category_validation,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    obj_cat_vs_subs_iter = iter(object_categories_vs_subsets.items())
    object_category_1, subset_1 = next(obj_cat_vs_subs_iter)
    object_category_2, subset_2 = next(obj_cat_vs_subs_iter)

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        object_category_subset_name="pedestrian",
    )
    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")
    media_1.add_media_object(media_object_1)
    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("wheel")
    media_1.add_media_object(media_object_2)
    uploader.add_media(media_1)

    # Act
    obj_categories_to_create = [
        obj_cat for obj_cat in object_categories_vs_subsets.keys()
    ]
    uploader._create_object_category_subsets(obj_categories_to_create)
    uploader._assign_object_category_subsets()

    # Assert
    for media in uploader._medias:
        for media_object in media.media_objects:
            if media_object.object_category_subset_name == object_category_1:
                assert media_object.subset_ids == [subset_1]
            elif media_object.object_category_subset_name == object_category_2:
                assert media_object.subset_ids == [subset_2]
        assert collections.Counter(media.subset_ids) == collections.Counter(
            [subset_1, subset_2]
        )


def test_update_hari_media_object_media_ids(
    mock_uploader_for_object_category_validation,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
    )
    media_1.bulk_operation_annotatable_id = "bulk_id_1"
    shared_media_object = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_1.add_media_object(shared_media_object)
    uploader.add_media(media_1)
    media_2 = hari_uploader.HARIMedia(
        name="my image 2",
        media_type=models.MediaType.IMAGE,
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_media_object(shared_media_object)
    media_2.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_2_obj_2"
        )
    )
    uploader.add_media(media_2)
    media_upload_bulk_response = models.BulkResponse(
        results=[
            models.AnnotatableCreateResponse(
                item_id="new_media_id_1",
                back_reference="img_1",
                bulk_operation_annotatable_id="bulk_id_1",
                status=models.ResponseStatesEnum.SUCCESS,
            ),
            models.AnnotatableCreateResponse(
                item_id="new_media_id_2",
                back_reference="img_2",
                bulk_operation_annotatable_id="bulk_id_2",
                status=models.ResponseStatesEnum.SUCCESS,
            ),
        ]
    )

    # Act
    uploader._update_hari_media_object_media_ids(
        medias_to_upload=[media_1, media_2],
        media_upload_bulk_response=media_upload_bulk_response,
    )

    # Assert
    assert uploader._medias[0].media_objects[0].media_id == "new_media_id_1"
    assert uploader._medias[1].media_objects[0].media_id == "new_media_id_2"
    assert uploader._medias[1].media_objects[1].media_id == "new_media_id_2"
    uploader._media_object_cnt = 3


def test_update_hari_attribute_media_ids(mock_uploader_for_object_category_validation):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    shared_attribute = hari_uploader.HARIAttribute(
        id=uuid.uuid4(),
        name="my attribute 1",
        value="value 1",
    )
    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
    )
    media_1.bulk_operation_annotatable_id = "bulk_id_1"
    media_1.add_attribute(shared_attribute)
    uploader.add_media(media_1)
    media_2 = hari_uploader.HARIMedia(
        name="my image 2",
        media_type=models.MediaType.IMAGE,
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_attribute(shared_attribute)
    media_2.add_attribute(
        hari_uploader.HARIAttribute(
            id=uuid.uuid4(),
            name="my attribute 2",
            value="value 2",
        )
    )
    uploader.add_media(media_2)

    # Act
    uploader._update_hari_attribute_media_ids(
        medias_to_upload=[media_1, media_2],
        media_upload_bulk_response=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    item_id="new_media_id_1",
                    back_reference="img_1",
                    bulk_operation_annotatable_id="bulk_id_1",
                    status=models.ResponseStatesEnum.SUCCESS,
                ),
                models.AnnotatableCreateResponse(
                    item_id="new_media_id_2",
                    back_reference="img_2",
                    bulk_operation_annotatable_id="bulk_id_2",
                    status=models.ResponseStatesEnum.SUCCESS,
                ),
            ]
        ),
    )

    # Assert
    assert media_1.attributes[0].annotatable_id == "new_media_id_1"
    assert media_1.attributes[0].annotatable_type == models.DataBaseObjectType.MEDIA
    assert media_2.attributes[0].annotatable_id == "new_media_id_2"
    assert media_2.attributes[0].annotatable_type == models.DataBaseObjectType.MEDIA
    assert media_2.attributes[1].annotatable_id == "new_media_id_2"
    assert media_2.attributes[1].annotatable_type == models.DataBaseObjectType.MEDIA


def test_update_hari_attribute_media_object_ids(
    mock_uploader_for_object_category_validation,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
    )
    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img_1_obj_1",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1400.0,
            y=1806.0,
            width=344.0,
            height=732.0,
        ),
    )
    media_object_1.bulk_operation_annotatable_id = "bulk_id_1"
    shared_attribute_object_1 = hari_uploader.HARIAttribute(
        id=uuid.uuid4(),
        name="Is human?",
        value="yes",
    )
    media_object_1.add_attribute(shared_attribute_object_1)
    media_1.add_media_object(media_object_1)

    media_2 = hari_uploader.HARIMedia(
        name="my image 2",
        media_type=models.MediaType.IMAGE,
        back_reference="img_2",
    )
    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img_2_obj_1",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1400.0,
            y=1806.0,
            width=344.0,
            height=732.0,
        ),
    )
    media_object_2.bulk_operation_annotatable_id = "bulk_id_2"
    attribute_object_2 = hari_uploader.HARIAttribute(
        id=uuid.uuid4(),
        name="Is human?",
        value="yes",
    )
    media_object_2.add_attribute(shared_attribute_object_1)
    media_object_2.add_attribute(attribute_object_2)
    media_2.add_media_object(media_object_2)

    # Act
    uploader._update_hari_attribute_media_object_ids(
        media_objects_to_upload=[media_object_1, media_object_2],
        media_object_upload_bulk_response=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    item_id="new_media_object_id_1",
                    back_reference="img_1_obj_1",
                    bulk_operation_annotatable_id="bulk_id_1",
                    status=models.ResponseStatesEnum.SUCCESS,
                ),
                models.AnnotatableCreateResponse(
                    item_id="new_media_object_id_2",
                    back_reference="img_2_obj_1",
                    bulk_operation_annotatable_id="bulk_id_2",
                    status=models.ResponseStatesEnum.SUCCESS,
                ),
            ]
        ),
    )

    # Assert
    assert media_object_1.attributes[0].annotatable_id == "new_media_object_id_1"
    assert (
        media_object_1.attributes[0].annotatable_type
        == models.DataBaseObjectType.MEDIAOBJECT
    )
    assert media_object_2.attributes[0].annotatable_id == "new_media_object_id_2"
    assert (
        media_object_2.attributes[0].annotatable_type
        == models.DataBaseObjectType.MEDIAOBJECT
    )
    assert media_object_2.attributes[1].annotatable_id == "new_media_object_id_2"
    assert (
        media_object_2.attributes[1].annotatable_type
        == models.DataBaseObjectType.MEDIAOBJECT
    )
    uploader._attribute_cnt = 3


def test_hari_uploader_creates_batches_correctly(mock_uploader_for_batching):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching

    attribute_media_id = uuid.uuid4()
    attribute_media_object_id = uuid.uuid4()

    uploader._config.media_upload_batch_size = 100
    uploader._config.media_object_upload_batch_size = 150
    uploader._config.attribute_upload_batch_size = 100
    # Amount of batches according to the batch size configuration:
    # 1100 medias--> 11 batches
    # 2200 media_objects --> 22 batches
    #   - two media objects per media --> two media object batches per media batch
    # 6600 attributes --> 66 batches
    #   - 2 attributes per media
    #   - 2 attributes per media object and two media objects per media
    #   - --> 6 attribute batches per media batch
    for i in range(1100):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = hari_uploader.HARIMediaObject(
                source=models.DataSource.REFERENCE,
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                hari_uploader.HARIAttribute(
                    id=attribute_media_id,
                    name=f"attr_{i}_{k}",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    hari_uploader.HARIAttribute(
                        id=attribute_media_object_id,
                        name=f"attr_{i}_{k}_{l}",
                        value=f"value_{i}_{k}_{l}",
                    )
                )
        uploader.add_media(media)

    # Act
    uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 11
    media_calls = media_spy.call_args_list
    for i in range(11):
        assert len(media_calls[i].kwargs["medias_to_upload"]) == 100
    assert len(uploader._medias) == 1100

    assert media_object_spy.call_count == 22
    media_object_calls = media_object_spy.call_args_list
    for i in range(22):
        if i % 2 == 0:
            assert len(media_object_calls[i].kwargs["media_objects_to_upload"]) == 150
        else:
            assert len(media_object_calls[i].kwargs["media_objects_to_upload"]) == 50
    assert uploader._media_object_cnt == 2200

    assert attribute_spy.call_count == 66
    attribute_calls = attribute_spy.call_args_list
    for i in range(66):
        assert len(attribute_calls[i].kwargs["attributes_to_upload"]) == 100
    assert uploader._attribute_cnt == 6600


def test_hari_uploader_creates_single_batch_correctly(
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    (
        uploader,
        client,
        media_spy,
        media_object_spy,
        attribute_spy,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=5,
        media_objects_cnt=10,
        attributes_cnt=30,
    )

    # 5 medias --> 1 batch
    # 10 media_objects --> 1 batch
    # 30 attributes --> 1 batch
    for i in range(5):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = hari_uploader.HARIMediaObject(
                source=models.DataSource.REFERENCE,
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                hari_uploader.HARIAttribute(
                    id=uuid.uuid4(),
                    name=f"attr_{i}_{k}",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    hari_uploader.HARIAttribute(
                        id=uuid.uuid4(),
                        name=f"attr_{i}_{k}_{l}",
                        value=f"value_{i}_{k}_{l}",
                    )
                )

        uploader.add_media(media)

    # Act
    uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 1
    media_calls = media_spy.call_args_list
    assert len(media_calls[0].kwargs["medias_to_upload"]) == 5
    assert len(uploader._medias) == 5

    assert media_object_spy.call_count == 1
    media_object_calls = media_object_spy.call_args_list
    assert len(media_object_calls[0].kwargs["media_objects_to_upload"]) == 10
    assert uploader._media_object_cnt == 10

    assert attribute_spy.call_count == 1
    attribute_calls = attribute_spy.call_args_list
    assert len(attribute_calls[0].kwargs["attributes_to_upload"]) == 30
    assert uploader._attribute_cnt == 30


def test_hari_uploader_creates_single_batch_correctly_without_uploading_media_files(
    create_configurable_mock_uploader_successful_single_batch, mocker
):
    # Arrange
    (
        uploader,
        client,
        media_spy,
        media_object_spy,
        attribute_spy,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=5,
        media_objects_cnt=10,
        attributes_cnt=30,
    )

    mocker.patch.object(
        uploader, "_dataset_uses_external_media_source", return_value=True
    )
    client_create_medias_spy = mocker.spy(client, "create_medias")

    # 5 medias --> 1 batch
    # 10 media_objects --> 1 batch
    # 30 attributes --> 1 batch
    for i in range(5):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
            file_key=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = hari_uploader.HARIMediaObject(
                source=models.DataSource.REFERENCE,
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                hari_uploader.HARIAttribute(
                    id=uuid.uuid4(),
                    name=f"attr_{i}_{k}",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    hari_uploader.HARIAttribute(
                        id=uuid.uuid4(),
                        name=f"attr_{i}_{k}_{l}",
                        value=f"value_{i}_{k}_{l}",
                    )
                )

        uploader.add_media(media)

    # Act
    uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 1
    media_calls = media_spy.call_args_list
    assert len(media_calls[0].kwargs["medias_to_upload"]) == 5
    assert len(uploader._medias) == 5

    assert media_object_spy.call_count == 1
    media_object_calls = media_object_spy.call_args_list
    assert len(media_object_calls[0].kwargs["media_objects_to_upload"]) == 10
    assert uploader._media_object_cnt == 10

    assert attribute_spy.call_count == 1
    attribute_calls = attribute_spy.call_args_list
    assert len(attribute_calls[0].kwargs["attributes_to_upload"]) == 30
    assert uploader._attribute_cnt == 30

    # check client method spies
    assert client_create_medias_spy.call_count == 1
    create_medias_calls = client_create_medias_spy.call_args_list
    assert create_medias_calls[0].kwargs["with_media_files_upload"] == False


def test_warning_for_hari_uploader_receives_duplicate_media_back_reference(
    mock_uploader_for_batching, mocker
):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching
    log_spy = mocker.spy(hari_uploader.log, "warning")
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image 1",
            media_type=models.MediaType.IMAGE,
            back_reference="img_1",
            file_path="images/image_1.jpg",
        )
    )
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image 2",
            media_type=models.MediaType.IMAGE,
            back_reference="img_1",
            file_path="images/image_2.jpg",
        )
    )

    # Act
    uploader.upload()

    # Assert
    assert log_spy.call_count == 1


def test_warning_for_hari_uploader_receives_duplicate_media_object_back_reference(
    mock_uploader_for_batching,
    mocker,
):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching
    log_spy = mocker.spy(hari_uploader.log, "warning")
    media = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )
    media.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
        )
    )
    media.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
        )
    )
    uploader.add_media(media)

    # Act
    uploader.upload()

    # Assert
    assert log_spy.call_count == 1


def test_warning_for_media_without_back_reference(mocker):
    # Arrange
    log_spy = mocker.spy(hari_uploader.log, "warning")

    # Act
    hari_uploader.HARIMedia(
        name="my image 1", media_type=models.MediaType.IMAGE, back_reference=""
    )

    # Assert
    assert log_spy.call_count == 1


def test_warning_for_media_object_without_back_reference(mocker):
    # Arrange
    log_spy = mocker.spy(hari_uploader.log, "warning")

    # Act
    hari_uploader.HARIMediaObject(source=models.DataSource.REFERENCE, back_reference="")

    # Assert
    assert log_spy.call_count == 1


def test_hari_uploader_sets_bulk_operation_annotatable_id_automatically_on_medias(
    mock_uploader_for_bulk_operation_annotatable_id_setter,
):
    # Arrange
    uploader, id_setter_spy = mock_uploader_for_bulk_operation_annotatable_id_setter

    # Act
    # 1 media with 1 media_object
    media = hari_uploader.HARIMedia(
        name="my image",
        media_type=models.MediaType.IMAGE,
        back_reference="img",
        file_path="images/image.jpg",
    )
    media.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE,
            back_reference="img_obj",
        )
    )
    uploader.add_media(media)
    uploader.upload()

    # Assert
    # the bulk_operation_annotatable_id must be set on the media and media_object
    assert id_setter_spy.call_count == 2
    assert media.bulk_operation_annotatable_id == "bulk_id"
    # it's ok that media and media object have the same bulk_id, because they're uploaded in separate batch operations
    assert media.media_objects[0].bulk_operation_annotatable_id == "bulk_id"

    # the media_id of the media_object must match the one provided by the create_medias
    assert media.media_objects[0].media_id == "server_side_media_id"


def test_hari_uploader_upload_without_specified_object_categories(mock_client, mocker):
    # Arrange
    uploader = hari_uploader.HARIUploader(mock_client[0], dataset_id=uuid.UUID(int=0))
    mocker.patch.object(uploader, "_load_dataset", return_value=None)
    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")

    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("wheel")

    media_object_3 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_3"
    )

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    with pytest.raises(ExceptionGroup, match="(2 sub-exceptions)") as err:
        uploader.upload()
    assert len(err.value.exceptions) == 2
    for sub_exception in err.value.exceptions:
        assert isinstance(
            sub_exception,
            hari_uploader.HARIMediaObjectUnknownObjectCategorySubsetNameError,
        )


def test_hari_uploader_upload_with_known_specified_object_categories(
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    create_subset_side_effect = [str(uuid.uuid4()), str(uuid.uuid4())]
    (
        uploader,
        _,
        _,
        _,
        _,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=1,
        media_objects_cnt=3,
        attributes_cnt=0,
        object_categories={"pedestrian", "wheel"},
        create_subset_side_effect=create_subset_side_effect,
    )

    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")

    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("wheel")

    media_object_3 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_3"
    )

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    uploader.upload()
    assert subset_create_spy.call_count == 2


def test_hari_uploader_upload_with_unknown_specified_object_categories(
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    create_subset_side_effect = []
    (
        uploader,
        _,
        _,
        _,
        _,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=1,
        media_objects_cnt=3,
        attributes_cnt=0,
        object_categories={"pedestrian", "wheel"},
        create_subset_side_effect=create_subset_side_effect,
    )

    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")

    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("wheeel")

    media_object_3 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_3"
    )

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    with pytest.raises(ExceptionGroup, match="(1 sub-exception)") as err:
        uploader.upload()
    assert len(err.value.exceptions) == 1
    assert isinstance(
        err.value.exceptions[0],
        hari_uploader.HARIMediaObjectUnknownObjectCategorySubsetNameError,
    )
    assert subset_create_spy.call_count == 0


def test_hari_uploader_upload_with_already_existing_backend_category_subsets(
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    create_subset_side_effect = [str(uuid.uuid4()), str(uuid.uuid4())]
    get_subsets_for_dataset_side_effect = [
        [
            models.DatasetResponse(
                id=uuid.UUID(subset_id),
                name=subset_name,
                object_category=True,
                mediatype=models.MediaType.IMAGE,
                # default nums to zero
                num_medias=0,
                num_media_objects=0,
                num_instances=0,
            )
            for subset_id, subset_name in zip(
                create_subset_side_effect, ["pedestrian", "wheel"]
            )
        ],
    ]
    (
        uploader,
        client,
        _,
        _,
        _,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=1,
        media_objects_cnt=3,
        attributes_cnt=0,
        object_categories={"pedestrian", "wheel"},
        create_subset_side_effect=create_subset_side_effect,
        get_subsets_for_dataset_side_effect=get_subsets_for_dataset_side_effect,
    )

    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")

    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("wheel")

    media_object_3 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_3"
    )

    media_1 = hari_uploader.HARIMedia(
        name="my image 1",
        media_type=models.MediaType.IMAGE,
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    uploader.upload()
    assert subset_create_spy.call_count == 0


@pytest.mark.parametrize(
    "bulk_responses, expected_merged_response",
    [
        ([], models.BulkResponse(status=models.BulkOperationStatusEnum.SUCCESS)),
        ([models.BulkResponse()], models.BulkResponse()),
        (
            [
                models.BulkResponse(status=models.BulkOperationStatusEnum.SUCCESS),
                models.BulkResponse(status=models.BulkOperationStatusEnum.SUCCESS),
            ],
            models.BulkResponse(status=models.BulkOperationStatusEnum.SUCCESS),
        ),
        (
            [
                models.BulkResponse(
                    status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS
                ),
                models.BulkResponse(
                    status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS
                ),
            ],
            models.BulkResponse(status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS),
        ),
        (
            [
                models.BulkResponse(status=models.BulkOperationStatusEnum.FAILURE),
                models.BulkResponse(status=models.BulkOperationStatusEnum.FAILURE),
            ],
            models.BulkResponse(status=models.BulkOperationStatusEnum.FAILURE),
        ),
        (
            [
                models.BulkResponse(status=models.BulkOperationStatusEnum.FAILURE),
                models.BulkResponse(
                    status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS
                ),
            ],
            models.BulkResponse(status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS),
        ),
        (
            [
                models.BulkResponse(status=models.BulkOperationStatusEnum.FAILURE),
                models.BulkResponse(status=models.BulkOperationStatusEnum.SUCCESS),
            ],
            models.BulkResponse(status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS),
        ),
        (
            [
                models.BulkResponse(
                    status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
                    summary=models.BulkUploadSuccessSummary(
                        total=5000, successful=4000, failed=1000
                    ),
                ),
                models.BulkResponse(
                    status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
                    summary=models.BulkUploadSuccessSummary(
                        total=3000, successful=1000, failed=2000
                    ),
                ),
            ],
            models.BulkResponse(
                status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=8000, successful=5000, failed=3000
                ),
            ),
        ),
        (
            [
                models.BulkResponse(
                    results=[
                        models.AnnotatableCreateResponse(
                            item_id="1",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_1",
                            bulk_operation_annotatable_id="bulk_id_1",
                        ),
                        models.AnnotatableCreateResponse(
                            item_id="2",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_2",
                            bulk_operation_annotatable_id="bulk_id_2",
                        ),
                    ]
                ),
                models.BulkResponse(
                    results=[
                        models.AnnotatableCreateResponse(
                            item_id="3",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_3",
                            bulk_operation_annotatable_id="bulk_id_3",
                        ),
                        models.AnnotatableCreateResponse(
                            item_id="4",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_4",
                            bulk_operation_annotatable_id="bulk_id_4",
                        ),
                    ]
                ),
            ],
            models.BulkResponse(
                results=[
                    models.AnnotatableCreateResponse(
                        item_id="1",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_1",
                        bulk_operation_annotatable_id="bulk_id_1",
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="2",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_2",
                        bulk_operation_annotatable_id="bulk_id_2",
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="3",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_3",
                        bulk_operation_annotatable_id="bulk_id_3",
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="4",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_4",
                        bulk_operation_annotatable_id="bulk_id_4",
                    ),
                ]
            ),
        ),
    ],
)
def test_merge_bulk_responses(
    bulk_responses: list[models.BulkResponse],
    expected_merged_response: models.BulkResponse,
):
    actual_merged_response = hari_uploader._merge_bulk_responses(*bulk_responses)
    assert actual_merged_response.status == expected_merged_response.status

    assert (
        actual_merged_response.summary.total == expected_merged_response.summary.total
    )
    assert (
        actual_merged_response.summary.successful
        == expected_merged_response.summary.successful
    )
    assert (
        actual_merged_response.summary.failed == expected_merged_response.summary.failed
    )

    assert len(actual_merged_response.results) == len(expected_merged_response.results)
    for actual_result, expected_result in zip(
        actual_merged_response.results, expected_merged_response.results
    ):
        assert actual_result.item_id == expected_result.item_id
        assert actual_result.back_reference == expected_result.back_reference
        assert actual_result.status == expected_result.status


def test_hari_uploader_unique_attributes_number_limit_error(
    mock_uploader_for_bulk_operation_annotatable_id_setter,
):
    # Arrange
    uploader, id_setter_spy = mock_uploader_for_bulk_operation_annotatable_id_setter

    expected_attr_cnt = 0
    # Act
    for i in range(100):
        media = hari_uploader.HARIMedia(
            name="my image",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for j in range(5):
            attribute_media_id = uuid.uuid4()
            attribute_media = hari_uploader.HARIAttribute(
                id=attribute_media_id,
                name="area",
                value=6912,
            )
            media.add_attribute(attribute_media)
            expected_attr_cnt += 1

        media_object = hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE,
            back_reference=f"img_{i}_obj_{i}",
        )
        media.add_media_object(media_object)
        for k in range(10):
            attribute_object_id = uuid.uuid4()
            attribute_object = hari_uploader.HARIAttribute(
                id=attribute_object_id,
                name="Is this a human being?",
                value=True,
            )
            media_object.add_attribute(attribute_object)
            expected_attr_cnt += 1

        uploader.add_media(media)

    # Assert
    with pytest.raises(hari_uploader.HARIUniqueAttributesLimitExceeded) as e:
        uploader.upload()
    assert e.value.existing_attributes_number == 0
    assert e.value.new_attributes_number == expected_attr_cnt


def test_hari_uploader_unique_attributes_number_limit_error_with_existing_attributes(
    create_configurable_mock_uploader_successful_single_batch,
):
    # Arrange
    (
        uploader,
        client,
        media_spy,
        media_object_spy,
        attribute_spy,
        subset_create_spy,
    ) = create_configurable_mock_uploader_successful_single_batch(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=5,
        media_objects_cnt=10,
        attributes_cnt=30,
    )

    existing_attrs_number = 999
    mock_attribute_metadata = [
        models.AttributeMetadataResponse(id=str(i))
        for i in range(existing_attrs_number)
    ]
    # create a collision with new attribute
    mock_attribute_metadata.append(
        models.AttributeMetadataResponse(id=str(uuid.UUID(int=0)))
    )
    # rewrite the get_attribute_metadata return value
    uploader.client.get_attribute_metadata = (
        lambda *args, **kwargs: mock_attribute_metadata
    )

    media = hari_uploader.HARIMedia(
        name="my image",
        media_type=models.MediaType.IMAGE,
        back_reference="img",
        file_path="images/image.jpg",
    )

    new_attrs_number = 2
    for k in range(new_attrs_number):
        media_object = hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE,
            back_reference=f"img_obj_{k}",
        )
        media.add_media_object(media_object)
        media_object.add_attribute(
            hari_uploader.HARIAttribute(
                id=uuid.UUID(int=k),
                name=f"attr_{k}",
                value=f"value_{k}",
            )
        )

    uploader.add_media(media)

    # Act + Assert
    with pytest.raises(hari_uploader.HARIUniqueAttributesLimitExceeded) as e:
        uploader.upload()
    assert e.value.new_attributes_number == new_attrs_number
    assert e.value.existing_attributes_number == len(mock_attribute_metadata)
    assert (
        e.value.intended_attributes_number == 1001
    )  # (1000 existing + 2 new) - 1 new that collides with existing


@pytest.mark.parametrize(
    "file_key, is_valid",
    [
        # valid
        (None, True),
        ("path/to/my_file.png", True),
        ("my_file.jpg", True),
        # invalid
        ("/path/to/my_file.png", False),
        ("s3://my-bucket/path/to/file.jpg", False),
        ("https://mybucket.s3.eu-central-1.amazonaws.com/path/to/file.jpg", False),
        ("https://myaccount.blob.core.windows.net/container/path/to/blob.png", False),
        ("https://my-custom-domain.com/path/to/file.png", False),
        ("http://my-custom-domain.com/path/to/file.png", False),
    ],
)
def test_hari_media_file_key_validation(file_key, is_valid):
    if is_valid:
        media = hari_uploader.HARIMedia(
            name="my image",
            back_reference="my_image_backref",
            media_type=models.MediaType.IMAGE,
            file_key=file_key,
        )
        assert media.file_key == file_key
    else:
        with pytest.raises(ValueError):
            hari_uploader.HARIMedia(
                name="my image",
                back_reference="my_image_backref",
                media_type=models.MediaType.IMAGE,
                file_key=file_key,
            )


def test_determine_media_files_upload_behavior_without_upload(test_client, mocker):
    # Arrange
    uploader = hari_uploader.HARIUploader(client=test_client, dataset_id=uuid.uuid4())
    mocker.patch.object(
        uploader, "_dataset_uses_external_media_source", return_value=True
    )

    medias = [
        hari_uploader.HARIMedia(
            name="my_image_0",
            back_reference="my_image_backref_0",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/image_0.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_1",
            back_reference="my_image_backref_1",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/imag_1.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_2",
            back_reference="my_image_backref_2",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/image_2.jpg",
        ),
    ]
    uploader.add_media(*medias)

    # Act
    uploader._determine_media_files_upload_behavior()

    # Assert
    assert not uploader._with_media_files_upload


def test_determine_media_files_upload_behavior_with_upload(test_client, mocker):
    # Arrange
    uploader = hari_uploader.HARIUploader(client=test_client, dataset_id=uuid.uuid4())
    mocker.patch.object(
        uploader, "_dataset_uses_external_media_source", return_value=False
    )

    medias = [
        hari_uploader.HARIMedia(
            name="my_image_0",
            back_reference="my_image_backref_0",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_0.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_1",
            back_reference="my_image_backref_1",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_1.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_2",
            back_reference="my_image_backref_2",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_2.jpg",
        ),
    ]
    uploader.add_media(*medias)

    # Act
    uploader._determine_media_files_upload_behavior()

    # Assert
    assert uploader._with_media_files_upload


def test_determine_media_files_upload_behavior_throws_exception_for_missing_file_path(
    test_client, mocker
):
    # Arrange
    uploader = hari_uploader.HARIUploader(client=test_client, dataset_id=uuid.uuid4())
    mocker.patch.object(
        uploader, "_dataset_uses_external_media_source", return_value=True
    )

    medias = [
        hari_uploader.HARIMedia(
            name="my_image_0",
            back_reference="my_image_backref_0",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_0.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_1",
            back_reference="my_image_backref_1",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/image_1.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_2",
            back_reference="my_image_backref_2",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_2.jpg",
        ),
    ]
    uploader.add_media(*medias)

    # Act + Assert
    with pytest.raises(hari_uploader.HARIMediaValidationError):
        uploader._determine_media_files_upload_behavior()


def test_determine_media_files_upload_behavior_throws_exception_for_missing_file_key(
    test_client, mocker
):
    # Arrange
    uploader = hari_uploader.HARIUploader(client=test_client, dataset_id=uuid.uuid4())
    mocker.patch.object(
        uploader, "_dataset_uses_external_media_source", return_value=False
    )

    medias = [
        hari_uploader.HARIMedia(
            name="my_image_0",
            back_reference="my_image_backref_0",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/image_0.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_1",
            back_reference="my_image_backref_1",
            media_type=models.MediaType.IMAGE,
            file_path="path/to/image_1.jpg",
        ),
        hari_uploader.HARIMedia(
            name="my_image_2",
            back_reference="my_image_backref_2",
            media_type=models.MediaType.IMAGE,
            file_key="path/to/image_2.jpg",
        ),
    ]
    uploader.add_media(*medias)

    # Act + Assert
    with pytest.raises(hari_uploader.HARIMediaValidationError):
        uploader._determine_media_files_upload_behavior()
