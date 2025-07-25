import collections
import uuid
from unittest import mock

import pytest

from hari_client import hari_uploader
from hari_client import models
from hari_client.client import errors


# Helper functions for creating test objects with proper geometries
def create_test_media(
    name: str = "test_media",
    back_reference: str = "test_media_ref",
    media_type: models.MediaType = models.MediaType.IMAGE,
    file_path: str = "test_path",
    file_key: str = None,
    object_category_subset_name: str = None,
    scene_back_reference: str = None,
    frame_idx: int = None,
) -> hari_uploader.HARIMedia:
    """Create a test media with sensible defaults."""
    media = hari_uploader.HARIMedia(
        name=name,
        media_type=media_type,
        back_reference=back_reference,
        file_path=file_path,
        file_key=file_key,
        object_category_subset_name=object_category_subset_name,
        scene_back_reference=scene_back_reference,
        frame_idx=frame_idx,
    )
    return media


def create_test_media_object_2d(
    back_reference: str = "test_media_obj_ref",
    source: models.DataSource = models.DataSource.REFERENCE,
    bbox_x: float = 100.0,
    bbox_y: float = 100.0,
    bbox_width: float = 50.0,
    bbox_height: float = 50.0,
    object_category_subset_name: str = None,
    scene_back_reference: str = None,
    frame_idx: int = None,
) -> hari_uploader.HARIMediaObject:
    """Create a test media object with 2D bounding box geometry."""
    reference_data = models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=bbox_x,
        y=bbox_y,
        width=bbox_width,
        height=bbox_height,
    )

    media_object = hari_uploader.HARIMediaObject(
        source=source,
        back_reference=back_reference,
        reference_data=reference_data,
        object_category_subset_name=object_category_subset_name,
        scene_back_reference=scene_back_reference,
        frame_idx=frame_idx,
    )
    return media_object


def create_test_media_object_3d(
    back_reference: str = "test_media_obj_ref",
    source: models.DataSource = models.DataSource.REFERENCE,
    x: float = 1.0,
    y: float = 2.0,
    z: float = 3.0,
    object_category_subset_name: str = None,
    scene_back_reference: str = None,
    frame_idx: int = None,
) -> hari_uploader.HARIMediaObject:
    """Create a test media object with 3D point geometry."""
    reference_data = models.Point3DXYZ(
        type="point3d_xyz",
        x=x,
        y=y,
        z=z,
    )

    media_object = hari_uploader.HARIMediaObject(
        source=source,
        back_reference=back_reference,
        reference_data=reference_data,
        object_category_subset_name=object_category_subset_name,
        scene_back_reference=scene_back_reference,
        frame_idx=frame_idx,
    )
    return media_object


def create_test_attribute(
    name: str = "test_attribute",
    value: str = "test_value",
    id: uuid.UUID = None,
) -> hari_uploader.HARIAttribute:
    """Create a test attribute with sensible defaults."""
    if id is None:
        id = uuid.uuid4()

    return hari_uploader.HARIAttribute(
        id=id,
        name=name,
        value=value,
    )


def test_add_media(mock_uploader_for_object_category_validation):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation
    assert len(uploader._medias) == 0

    # Act
    media_with_attribute = create_test_media(name="my image", back_reference="img")
    media_with_attribute.attributes = [
        create_test_attribute(name="my attribute 1", value="value 1")
    ]
    uploader.add_media(media_with_attribute)

    # Assert
    assert len(uploader._medias) == 1

    # Act
    # add another media without attributes
    media_without_attributes = create_test_media(name="my image", back_reference="img")
    uploader.add_media(media_without_attributes)

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

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
    )
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )
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
    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2",
        object_category_subset_name="some_non-existent-subset_name",
    )
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


def test_assign_media_objects_to_object_category_subsets_sets_subset_ids_correctly(
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

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
        object_category_subset_name="pedestrian",
    )
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )
    media_1.add_media_object(media_object_1)
    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", object_category_subset_name="wheel"
    )
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


def test_validate_scene_consistency(
    mock_uploader_for_scene_validation,
):
    # Arrange

    (uploader, scene_back_references_vs_scene_ids) = mock_uploader_for_scene_validation

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
        scene_back_reference="scene_1",
        frame_idx=0,
    )
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1",
        scene_back_reference="scene_1",
        frame_idx=0,
    )
    media_1.add_media_object(media_object_1)
    uploader.add_media(media_1)
    # Act
    (
        found_object_category_subset_names,
        errors,
    ) = uploader._get_and_validate_scene_back_references()

    # Assert
    assert len(errors) == 0
    assert found_object_category_subset_names == {"scene_1"}

    # Arrange
    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2",
        scene_back_reference="some_non-existent-scene_back_reference",
        frame_idx=1,
    )
    media_1.add_media_object(media_object_2)

    # Act
    (
        found_object_category_subset_names,
        errors,
    ) = uploader._get_and_validate_scene_back_references()

    # Assert
    assert len(errors) == 1
    assert type(errors[0]) == hari_uploader.HARIUnknownSceneNameError
    assert found_object_category_subset_names == {
        "scene_1",
        "some_non-existent-scene_back_reference",
    }

    # Act
    errors = uploader._validate_consistency()

    assert len(errors) == 2
    assert type(errors[0]) == hari_uploader.HARIInconsistentFieldError
    assert type(errors[1]) == hari_uploader.HARIInconsistentFieldError


def test_assign_scenes_and_frames_correctly(mock_uploader_for_scene_validation, mocker):
    # Arrange
    (uploader, scene_back_references_vs_scene_ids) = mock_uploader_for_scene_validation

    # Mock _create_scenes to populate uploader._scenes with the expected IDs
    def mock_create_scenes(scenes):
        for scene in scenes:
            if scene in scene_back_references_vs_scene_ids:
                uploader._scenes[scene] = scene_back_references_vs_scene_ids[scene]

    mocker.patch.object(uploader, "_create_scenes", side_effect=mock_create_scenes)

    scene_back_references_vs_scenes_iter = iter(
        scene_back_references_vs_scene_ids.items()
    )
    scene_back_reference_1, scene_1 = next(scene_back_references_vs_scenes_iter)
    scene_back_reference_2, scene_2 = next(scene_back_references_vs_scenes_iter)

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
        object_category_subset_name="pedestrian",
        scene_back_reference="scene_1",
        frame_idx=0,
    )
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", frame_idx=0, scene_back_reference="scene_1"
    )
    media_1.add_media_object(media_object_1)
    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", frame_idx=0, scene_back_reference="scene_2"
    )
    media_1.add_media_object(media_object_2)
    uploader.add_media(media_1)
    scenes_to_create = ["scene_1", "scene_2"]

    # Act
    uploader._create_scenes(scenes_to_create)
    uploader._assign_property_ids()

    # Assert
    for media in uploader._medias:
        for media_object in media.media_objects:
            if media_object.scene_back_reference == scene_back_reference_1:
                assert media_object.scene_id == scene_1
            elif media_object.scene_back_reference == scene_back_reference_2:
                assert media_object.scene_id == scene_2
        assert media.scene_id in [scene_1, scene_2]


def test_update_hari_media_object_media_ids(
    mock_uploader_for_object_category_validation,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
    )
    media_1.bulk_operation_annotatable_id = "bulk_id_1"
    shared_media_object = create_test_media_object_2d(back_reference="img_1_obj_1")
    media_1.add_media_object(shared_media_object)
    uploader.add_media(media_1)
    media_2 = create_test_media(
        name="my image 2",
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_media_object(shared_media_object)
    media_2.add_media_object(create_test_media_object_2d(back_reference="img_2_obj_2"))
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

    shared_attribute = create_test_attribute(
        name="my attribute 1",
        value="value 1",
    )
    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
    )
    media_1.bulk_operation_annotatable_id = "bulk_id_1"
    media_1.add_attribute(shared_attribute)
    uploader.add_media(media_1)
    media_2 = create_test_media(
        name="my image 2",
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_attribute(shared_attribute)
    media_2.add_attribute(
        create_test_attribute(
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

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
    )
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1",
        bbox_x=1400.0,
        bbox_y=1806.0,
        bbox_width=344.0,
        bbox_height=732.0,
    )
    media_object_1.bulk_operation_annotatable_id = "bulk_id_1"
    shared_attribute_object_1 = create_test_attribute(
        name="Is human?",
        value="yes",
    )
    media_object_1.add_attribute(shared_attribute_object_1)
    media_1.add_media_object(media_object_1)

    media_2 = create_test_media(
        name="my image 2",
        back_reference="img_2",
    )
    media_object_2 = create_test_media_object_2d(
        back_reference="img_2_obj_1",
        bbox_x=1400.0,
        bbox_y=1806.0,
        bbox_width=344.0,
        bbox_height=732.0,
    )
    media_object_2.bulk_operation_annotatable_id = "bulk_id_2"
    attribute_object_2 = create_test_attribute(
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
        media = create_test_media(
            name=f"my image {i}",
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = create_test_media_object_2d(
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                create_test_attribute(
                    id=attribute_media_id,
                    name=f"attr_media",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    create_test_attribute(
                        id=attribute_media_object_id,
                        name=f"attr_media_object",
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
    assert sum(len(media.media_objects) for media in uploader._medias) == 2200

    assert attribute_spy.call_count == 66
    attribute_calls = attribute_spy.call_args_list
    for i in range(66):
        assert len(attribute_calls[i].kwargs["attributes_to_upload"]) == 100
    assert (
        sum(
            len(media.attributes)
            + sum(len(obj.attributes) for obj in media.media_objects)
            for media in uploader._medias
        )
        == 6600
    )


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
        media = create_test_media(
            name=f"my image {i}",
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = create_test_media_object_2d(
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                create_test_attribute(
                    name=f"attr_{i}_{k}",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    create_test_attribute(
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
    assert sum(len(media.media_objects) for media in uploader._medias) == 10

    assert attribute_spy.call_count == 1
    attribute_calls = attribute_spy.call_args_list
    assert len(attribute_calls[0].kwargs["attributes_to_upload"]) == 30
    assert (
        sum(
            len(media.attributes)
            + sum(len(obj.attributes) for obj in media.media_objects)
            for media in uploader._medias
        )
        == 30
    )


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
        media = create_test_media(
            name=f"my image {i}",
            back_reference=f"img_{i}",
            file_key=f"images/image_{i}.jpg",
        )
        for k in range(2):
            media_object = create_test_media_object_2d(
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                create_test_attribute(
                    name=f"attr_{i}_{k}",
                    value=f"value_{i}_{k}",
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    create_test_attribute(
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
    assert sum(len(media.media_objects) for media in uploader._medias) == 10

    assert attribute_spy.call_count == 1
    attribute_calls = attribute_spy.call_args_list
    assert len(attribute_calls[0].kwargs["attributes_to_upload"]) == 30
    assert (
        sum(
            len(media.attributes)
            + sum(len(obj.attributes) for obj in media.media_objects)
            for media in uploader._medias
        )
        == 30
    )

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
        create_test_media(
            back_reference="img_1",
        )
    )
    uploader.add_media(create_test_media(back_reference="img_1"))

    # disable state aware check that raises and error rather than warning
    uploader.skip_uploaded_medias = False

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
    media = create_test_media(name="my image 1", back_reference="img_1")
    media.add_media_object(create_test_media_object_2d(back_reference="img_1_obj_1"))
    media.add_media_object(create_test_media_object_2d(back_reference="img_1_obj_1"))
    uploader.add_media(media)

    # disable state aware check that raises and error rather than warning
    uploader.skip_uploaded_media_objects = False

    # Act
    uploader.upload()

    # Assert
    assert log_spy.call_count == 1


def test_error_for_hari_state_aware_uploader_receives_duplicate_media_back_reference(
    mock_uploader_for_batching, mocker
):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching
    uploader.add_media(
        create_test_media(
            back_reference="img_1",
        )
    )
    uploader.add_media(create_test_media(back_reference="img_1"))

    # Act + Assert
    with pytest.raises(
        ValueError, match="Back_references need to be unique across dataset"
    ):
        uploader.upload()


def test_error_for_hari_state_aware_uploader_receives_duplicate_media_object_back_reference(
    mock_uploader_for_batching,
    mocker,
):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching
    media = create_test_media(name="my image 1", back_reference="img_1")
    media.add_media_object(create_test_media_object_2d(back_reference="img_1_obj_1"))
    media.add_media_object(create_test_media_object_2d(back_reference="img_1_obj_1"))
    uploader.add_media(media)

    with pytest.raises(
        ValueError, match="Back_references need to be unique across dataset"
    ):
        uploader.upload()


def test_warning_for_media_without_back_reference(mocker):
    # Arrange
    log_spy = mocker.spy(hari_uploader.log, "warning")

    # Act
    create_test_media(name="my image 1", back_reference="")

    # Assert
    assert log_spy.call_count == 1


def test_warning_for_media_object_without_back_reference(mocker):
    # Arrange
    log_spy = mocker.spy(hari_uploader.log, "warning")

    # Act
    create_test_media_object_2d(back_reference="")

    # Assert
    assert log_spy.call_count == 1


def test_hari_uploader_sets_bulk_operation_annotatable_id_automatically_on_medias(
    mock_uploader_for_bulk_operation_annotatable_id_setter,
):
    # Arrange
    uploader, id_setter_spy = mock_uploader_for_bulk_operation_annotatable_id_setter

    # Act
    # 1 media with 1 media_object
    media = create_test_media(
        name="my image",
        back_reference="img",
        file_path="images/image.jpg",
    )
    media.add_media_object(
        create_test_media_object_2d(
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
    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )

    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", object_category_subset_name="wheel"
    )

    media_object_3 = create_test_media_object_2d(back_reference="img_1_obj_3")

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    with pytest.raises(ExceptionGroup, match="Property validation failed") as err:
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

    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )

    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", object_category_subset_name="wheel"
    )

    media_object_3 = create_test_media_object_2d(back_reference="img_1_obj_3")

    media_1 = create_test_media(
        name="my image 1",
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

    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )

    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", object_category_subset_name="wheeel"
    )

    media_object_3 = create_test_media_object_2d(back_reference="img_1_obj_3")

    media_1 = create_test_media(
        name="my image 1",
        back_reference="img_1",
        file_path="images/image_1.jpg",
    )

    # Act + Assert
    media_1.add_media_object(media_object_1, media_object_2, media_object_3)
    uploader.add_media(media_1)
    with pytest.raises(ExceptionGroup, match="Property validation failed") as err:
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

    media_object_1 = create_test_media_object_2d(
        back_reference="img_1_obj_1", object_category_subset_name="pedestrian"
    )

    media_object_2 = create_test_media_object_2d(
        back_reference="img_1_obj_2", object_category_subset_name="wheel"
    )

    media_object_3 = create_test_media_object_2d(back_reference="img_1_obj_3")

    media_1 = create_test_media(
        name="my image 1",
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
        media = create_test_media(
            name="my image",
            back_reference=f"img_{i}",
            file_path=f"images/image_{i}.jpg",
        )
        for j in range(5):
            attribute_media_id = uuid.uuid4()
            attribute_media = create_test_attribute(
                id=attribute_media_id,
                name=f"media_{i}_{j}",
                value=6912,
            )
            media.add_attribute(attribute_media)
            expected_attr_cnt += 1

        media_object = create_test_media_object_2d(
            back_reference=f"img_{i}_obj_{i}",
        )
        media.add_media_object(media_object)
        for k in range(10):
            attribute_object_id = uuid.uuid4()
            attribute_object = create_test_attribute(
                id=attribute_object_id,
                name=f"media_object{i}_{k}",
                value=True,
            )
            media_object.add_attribute(attribute_object)
            expected_attr_cnt += 1

        uploader.add_media(media)

    # Assert
    with pytest.raises(hari_uploader.HARIUniqueAttributesLimitExceeded) as e:
        uploader.upload()
    assert e.value.existing_attributes_number == 0
    assert e.value.intended_attributes_number == 1500


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
        models.AttributeMetadataResponse(id=str(uuid.UUID(int=i)), name=f"attr_{i}")
        for i in range(existing_attrs_number)
    ]
    # create a collision with new attribute
    mock_attribute_metadata.append(
        models.AttributeMetadataResponse(id=str(uuid.UUID(int=2000)), name=f"attr_0")
    )
    # rewrite the get_attribute_metadata return value
    uploader.client.get_attribute_metadata = (
        lambda *args, **kwargs: mock_attribute_metadata
    )

    media = create_test_media(
        name="my image",
        back_reference="img",
        file_path="images/image.jpg",
    )

    new_attrs_number = 2
    for k in range(new_attrs_number):
        media_object = create_test_media_object_2d(
            back_reference=f"img_obj_{k}",
        )
        media.add_media_object(media_object)
        media_object.add_attribute(
            create_test_attribute(
                id=uuid.UUID(int=k),
                name=f"attr_{k}",
                value=f"value_{k}",
            )
        )

    uploader.add_media(media)

    # Act + Assert
    with pytest.raises(hari_uploader.HARIUniqueAttributesLimitExceeded) as e:
        uploader.upload()
    assert e.value.existing_attributes_number == len(mock_attribute_metadata)
    assert (
        e.value.intended_attributes_number == 1001
    )  # (1000 existing + 2 new) - 1 new that collides with existing


def test_hari_uploader_existing_attribute_ids_are_reused(
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
        medias_cnt=1,
        media_objects_cnt=1,
        attributes_cnt=2,
    )

    existing_media_attr_id = "media_attribute_id"
    existing_media_object_attr_id = "media_object_attribute_id"

    same_attribute_name = "attribute_name"

    mock_attribute_metadata = [
        models.AttributeMetadataResponse(
            id=existing_media_attr_id,
            name=same_attribute_name,
            annotatable_type=models.DataBaseObjectType.MEDIA,
        ),
        models.AttributeMetadataResponse(
            id=existing_media_object_attr_id,
            name=same_attribute_name,
            annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
        ),
    ]

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

    media_object = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference=f"img_obj",
        reference_data=models.PolyLine2DFlatCoordinates(
            coordinates=[1450, 1550, 1450, 1000],
            closed=False,
        ),
    )
    media.add_media_object(media_object)
    media.add_attribute(
        hari_uploader.HARIAttribute(
            id=uuid.UUID(int=0),
            name=same_attribute_name,
            value=f"value",
        )
    )
    media_object.add_attribute(
        hari_uploader.HARIAttribute(
            id=uuid.UUID(int=1),
            name=same_attribute_name,
            value=f"value",
        )
    )

    uploader.add_media(media)
    uploader.upload()

    # assert that the existing attribute ids were reused by name + annotatable type
    assert uploader._medias[0].attributes[0].id == existing_media_attr_id
    assert (
        uploader._medias[0].media_objects[0].attributes[0].id
        == existing_media_object_attr_id
    )


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
        create_test_media(
            name="my_image_0",
            back_reference="my_image_backref_0",
            file_key="path/to/image_0.jpg",
        ),
        create_test_media(
            name="my_image_1",
            back_reference="my_image_backref_1",
            file_key="path/to/imag_1.jpg",
        ),
        create_test_media(
            name="my_image_2",
            back_reference="my_image_backref_2",
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
        create_test_media(
            name="my_image_0",
            back_reference="my_image_backref_0",
            file_path="path/to/image_0.jpg",
        ),
        create_test_media(
            name="my_image_1",
            back_reference="my_image_backref_1",
            file_path="path/to/image_1.jpg",
        ),
        create_test_media(
            name="my_image_2",
            back_reference="my_image_backref_2",
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


@pytest.mark.parametrize(
    "media_bulk_operation_status, media_response_status_responses, media_object_bulk_operation_status, media_object_response_status_responses, uploader_result",
    [
        # (
        #     # success
        #     models.BulkOperationStatusEnum.SUCCESS,
        #     [
        #         # 2 medias
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #     ],
        #     models.BulkOperationStatusEnum.SUCCESS,
        #     [
        #         # 3 media objects (2 for first media, 1 for second)
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #     ],
        #     {
        #         "num_failed_medias": 0,
        #         "num_failed_media_objects": 0,
        #         "num_failed_media_attributes": 0,
        #         "num_failed_media_object_attributes": 0,
        #     },
        # ),
        # (
        #     # partial_success_medias_fail
        #     models.BulkOperationStatusEnum.FAILURE,
        #     [
        #         models.ResponseStatesEnum.MISSING_DATA,
        #         models.ResponseStatesEnum.CONFLICT,
        #     ],
        #     models.BulkOperationStatusEnum.SUCCESS,
        #     [
        #         # these should not matter, since medias have failed and media objects should be skipped
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #     ],
        #     {
        #         "num_failed_medias": 2,
        #         "num_failed_media_objects": 3,
        #         "num_failed_media_attributes": 4,
        #         "num_failed_media_object_attributes": 6,
        #     },
        # ),
        # (
        #     # partial_success_media_objects_fail
        #     models.BulkOperationStatusEnum.SUCCESS,
        #     [
        #         models.ResponseStatesEnum.SUCCESS,
        #         models.ResponseStatesEnum.SUCCESS,
        #     ],
        #     models.BulkOperationStatusEnum.FAILURE,
        #     [
        #         models.ResponseStatesEnum.MISSING_DATA,
        #         models.ResponseStatesEnum.CONFLICT,
        #         models.ResponseStatesEnum.MISSING_DATA,
        #     ],
        #     {
        #         "num_failed_medias": 0,
        #         "num_failed_media_objects": 3,
        #         "num_failed_media_attributes": 0,
        #         "num_failed_media_object_attributes": 6,
        #     },
        # ),
        # (
        #     # partial_success_medias_and_media_objects_fail
        #     models.BulkOperationStatusEnum.FAILURE,
        #     [
        #         models.ResponseStatesEnum.SERVER_ERROR,
        #         models.ResponseStatesEnum.MISSING_DATA,
        #     ],
        #     models.BulkOperationStatusEnum.FAILURE,
        #     [
        #         models.ResponseStatesEnum.SERVER_ERROR,
        #         models.ResponseStatesEnum.MISSING_DATA,
        #         models.ResponseStatesEnum.MISSING_DATA,
        #     ],
        #     {
        #         "num_failed_medias": 2,
        #         "num_failed_media_objects": 3,
        #         "num_failed_media_attributes": 4,
        #         "num_failed_media_object_attributes": 6,
        #     },
        # ),
        (
            # partial_success_medias_and_media_objects_fail, already existing response are skipped
            models.BulkOperationStatusEnum.FAILURE,
            [
                models.ResponseStatesEnum.ALREADY_EXISTS,
                models.ResponseStatesEnum.SERVER_ERROR,
            ],
            models.BulkOperationStatusEnum.FAILURE,
            [
                models.ResponseStatesEnum.ALREADY_EXISTS,
                models.ResponseStatesEnum.MISSING_DATA,
                models.ResponseStatesEnum.SERVER_ERROR,
            ],
            {
                "num_failed_medias": 1,  # 1 already existing media is not a failure
                "num_failed_media_objects": 2,  # 1 already existing media object is not a failure
                "num_failed_media_attributes": 2,  # 2 attributes for already existing media are valid
                "num_failed_media_object_attributes": 4,  # 2 attributes for already existing media object are valid
            },
        ),
    ],
)
def test_hari_uploader_marks_dependencies_as_failed_when_media_object_upload_fails(
    create_configurable_mock_uploader_successful_single_batch,
    media_bulk_operation_status,
    media_response_status_responses,
    media_object_bulk_operation_status,
    media_object_response_status_responses,
    uploader_result,
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
        medias_cnt=2,
        media_objects_cnt=3,
        attributes_cnt=6,
    )

    media_1 = create_test_media(
        name="media_1",
        back_reference="media_ref_1",
        file_path="images/1.jpg",
    )

    media_obj_1 = create_test_media_object_2d(
        back_reference="media_obj_1",
    )
    media_obj_1.add_attribute(
        create_test_attribute(
            name="attr1_1",
            value="value1_1",
        )
    )
    media_obj_1.add_attribute(
        create_test_attribute(
            name="attr1_2",
            value="value1_2",
        )
    )

    media_obj_2 = create_test_media_object_2d(
        back_reference="media_obj_2",
    )
    media_obj_2.add_attribute(
        create_test_attribute(
            name="attr2_1",
            value="value2_1",
        )
    )
    media_obj_2.add_attribute(
        create_test_attribute(
            name="attr2_2",
            value="value2_2",
        )
    )

    media_1.add_media_object(media_obj_1, media_obj_2)
    media_1.add_attribute(
        create_test_attribute(
            name="media_attr1_1",
            value="media_value1_1",
        )
    )
    media_1.add_attribute(
        create_test_attribute(
            name="media_attr1_2",
            value="media_value1_2",
        )
    )

    media_2 = create_test_media(
        name="media_2",
        back_reference="media_ref_2",
        file_path="images/2.jpg",
    )

    media_obj_3 = create_test_media_object_2d(
        back_reference="media_obj_3",
    )
    media_obj_3.add_attribute(
        create_test_attribute(
            name="attr3_1",
            value="value3_1",
        )
    )
    media_obj_3.add_attribute(
        create_test_attribute(
            name="attr3_2",
            value="value3_2",
        )
    )

    media_2.add_media_object(media_obj_3)
    media_2.add_attribute(
        create_test_attribute(
            name="media_attr2_1",
            value="media_value2_1",
        )
    )
    media_2.add_attribute(
        create_test_attribute(
            name="media_attr2",
            value="media_value2_2",
        )
    )

    # Mock the create_medias response to return specified response
    def mock_create_medias(*args, **kwargs):
        medias = kwargs.get("medias", [])
        results = []
        for media in medias:
            if media.name == "media_1":
                results.append(
                    models.AnnotatableCreateResponse(
                        item_id="id_0"
                        if media_response_status_responses[0]
                        == models.BulkOperationStatusEnum.SUCCESS
                        else None,
                        status=media_response_status_responses[0],
                        bulk_operation_annotatable_id=media.bulk_operation_annotatable_id,
                    )
                )
            else:
                results.append(
                    models.AnnotatableCreateResponse(
                        item_id="id_1"
                        if media_response_status_responses[1]
                        == models.BulkOperationStatusEnum.SUCCESS
                        else None,
                        status=media_response_status_responses[1],
                        bulk_operation_annotatable_id=media.bulk_operation_annotatable_id,
                    )
                )
        return models.BulkResponse(
            results=results,
            status=media_bulk_operation_status,
            summary=models.BulkUploadSuccessSummary(
                total=len(results),
                successful=len(
                    [
                        x
                        for x in results
                        if x.status == models.ResponseStatesEnum.SUCCESS
                    ]
                ),
                failed=len(
                    [
                        x
                        for x in results
                        if x.status != models.ResponseStatesEnum.SUCCESS
                    ]
                ),
            ),
        )

    client.create_medias = mock_create_medias

    # Mock the create_media_objects response to make the first media object fail
    def mock_create_media_objects(*args, **kwargs):
        media_objects = kwargs.get("media_objects", [])
        results = []
        for media_object in media_objects:
            if media_object.back_reference == "media_obj_1":
                results.append(
                    models.AnnotatableCreateResponse(
                        item_id="id_0"
                        if media_object_response_status_responses[0]
                        == models.BulkOperationStatusEnum.SUCCESS
                        else None,
                        status=media_object_response_status_responses[0],
                        bulk_operation_annotatable_id=media_object.bulk_operation_annotatable_id,
                    )
                )
            elif media_object.back_reference == "media_obj_2":
                results.append(
                    models.AnnotatableCreateResponse(
                        item_id="id_1"
                        if media_object_response_status_responses[1]
                        == models.BulkOperationStatusEnum.SUCCESS
                        else None,
                        status=media_object_response_status_responses[1],
                        bulk_operation_annotatable_id=media_object.bulk_operation_annotatable_id,
                    )
                )
            else:
                results.append(
                    models.AnnotatableCreateResponse(
                        item_id="id_2"
                        if media_object_response_status_responses[2]
                        == models.BulkOperationStatusEnum.SUCCESS
                        else None,
                        status=media_object_response_status_responses[2],
                        bulk_operation_annotatable_id=media_object.bulk_operation_annotatable_id,
                    )
                )
        return models.BulkResponse(
            results=results,
            status=media_object_bulk_operation_status,
            summary=models.BulkUploadSuccessSummary(
                total=len(results),
                successful=len(
                    [
                        x
                        for x in results
                        if x.status == models.ResponseStatesEnum.SUCCESS
                    ]
                ),
                failed=len(
                    [
                        x
                        for x in results
                        if x.status != models.ResponseStatesEnum.SUCCESS
                    ]
                ),
            ),
        )

    client.create_media_objects = mock_create_media_objects

    # Add both medias to uploader
    uploader.add_media(media_1, media_2)

    # Act
    results = uploader.upload()

    # Assert
    assert len(results.failures.failed_medias) == uploader_result["num_failed_medias"]
    assert (
        len(results.failures.failed_media_objects)
        == uploader_result["num_failed_media_objects"]
    )
    assert (
        len(results.failures.failed_media_attributes)
        == uploader_result["num_failed_media_attributes"]
    )
    assert (
        len(results.failures.failed_media_object_attributes)
        == uploader_result["num_failed_media_object_attributes"]
    )
    assert uploader._media_upload_progress.total == uploader._media_upload_progress.n
    assert (
        uploader._media_object_upload_progress.total
        == uploader._media_object_upload_progress.n
    )
    assert (
        uploader._attribute_upload_progress.total
        == uploader._attribute_upload_progress.n
    )


def test_validate_media_object_compatible_with_media_with_none_media_object_type():
    """Test behavior when media_object_type is None."""
    media = models.MediaCreate(
        name="test_image", media_type=models.MediaType.IMAGE, back_reference="img_ref"
    )

    media_object = models.MediaObjectCreate(
        media_id="test_media_id", back_reference="obj_ref", media_object_type=None
    )

    with pytest.raises(ValueError) as exc_info:
        hari_uploader.HARIUploader._validate_media_object_compatible_with_media(
            media, media_object
        )

    expected_msg = f"MediaObject type must be specified."
    assert str(exc_info.value) == expected_msg


@pytest.mark.parametrize(
    "media_type,valid_object_geometries,invalid_object_geometries,expected_error_msg",
    [
        (
            models.MediaType.IMAGE,
            [
                models.PolyLine2DFlatCoordinates(coordinates=[1.0, 2.0, 3.0, 4.0]),
                models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1.0,
                    y=2.0,
                    width=10.0,
                    height=20.0,
                ),
                models.BoundingBox2DAggregation(
                    type="bbox2d_center_point_aggregation",
                    x=1.0,
                    y=2.0,
                    width=10.0,
                    height=20.0,
                ),
                models.Point2DXY(x=1.0, y=2.0),
                models.Point2DAggregation(type="point2d_xy_aggregation", x=1.0, y=2.0),
                models.SegmentRLECompressed(size=[100, 100], counts="1a2b3c4d"),
            ],
            [
                models.Point3DXYZ(type="point3d_xyz", x=1.0, y=2.0, z=3.0),
                models.Point3DAggregation(
                    type="point3d_xyz_aggregation", x=1.0, y=2.0, z=3.0
                ),
                models.CuboidCenterPoint(
                    position=(1.0, 2.0, 3.0),
                    heading=(0.0, 0.0, 0.0, 1.0),
                    dimensions=(1.0, 1.0, 1.0),
                ),
            ],
            "Images can only contain 2D geometries",
        ),
        (
            models.MediaType.POINT_CLOUD,
            [
                models.Point3DXYZ(type="point3d_xyz", x=1.0, y=2.0, z=3.0),
                models.Point3DAggregation(
                    type="point3d_xyz_aggregation", x=1.0, y=2.0, z=3.0
                ),
                models.CuboidCenterPoint(
                    position=(1.0, 2.0, 3.0),
                    heading=(0.0, 0.0, 0.0, 1.0),
                    dimensions=(1.0, 1.0, 1.0),
                ),
            ],
            [
                models.PolyLine2DFlatCoordinates(coordinates=[1.0, 2.0, 3.0, 4.0]),
                models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1.0,
                    y=2.0,
                    width=10.0,
                    height=20.0,
                ),
                models.BoundingBox2DAggregation(
                    type="bbox2d_center_point_aggregation",
                    x=1.0,
                    y=2.0,
                    width=10.0,
                    height=20.0,
                ),
                models.Point2DXY(x=1.0, y=2.0),
                models.Point2DAggregation(type="point2d_xy_aggregation", x=1.0, y=2.0),
                models.SegmentRLECompressed(size=[100, 100], counts="1a2b3c4d"),
            ],
            "Point clouds can only contain 3D geometries",
        ),
        (
            models.MediaType.VIDEO,
            [],  # No valid geometries for video
            [
                # All geometry types should be invalid for video
                models.PolyLine2DFlatCoordinates(coordinates=[1.0, 2.0, 3.0, 4.0]),
                models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1.0,
                    y=2.0,
                    width=10.0,
                    height=20.0,
                ),
                models.Point2DXY(x=1.0, y=2.0),
                models.Point3DXYZ(type="point3d_xyz", x=1.0, y=2.0, z=3.0),
                models.CuboidCenterPoint(
                    position=(1.0, 2.0, 3.0),
                    heading=(0.0, 0.0, 0.0, 1.0),
                    dimensions=(1.0, 1.0, 1.0),
                ),
                models.SegmentRLECompressed(size=[100, 100], counts="1a2b3c4d"),
            ],
            "Videos can not contian media objects.",
        ),
    ],
)
def test_validate_media_object_compatible_with_media_parametrized(
    media_type, valid_object_geometries, invalid_object_geometries, expected_error_msg
):
    """Parametrized test for media object compatibility validation."""
    media = models.MediaCreate(
        name="test_media", media_type=media_type, back_reference="media_ref"
    )

    # Test valid types - should not raise
    for geometry in valid_object_geometries:
        media_object = models.MediaObjectCreate(
            media_id="test_media_id",
            back_reference="obj_ref",
            media_object_type=geometry.type,
        )

        hari_uploader.HARIUploader._validate_media_object_compatible_with_media(
            media, media_object
        )

    # Test invalid types - should raise ValueError
    for geometry in invalid_object_geometries:
        media_object = models.MediaObjectCreate(
            media_id="test_media_id",
            back_reference="obj_ref",
            media_object_type=geometry.type,
        )

        with pytest.raises(ValueError) as exc_info:
            hari_uploader.HARIUploader._validate_media_object_compatible_with_media(
                media, media_object
            )

        # Check that the error message contains the expected text
        assert expected_error_msg in str(exc_info.value)


@pytest.mark.parametrize(
    "entity_name,return_value_bulk_item_result",
    [
        (
            "medias",
            {
                "item_id": str(uuid.UUID(int=0)),
                "status": "conflict",
                "bulk_operation_annotatable_id": "bulk_media_id_0",  # comes from the fixture
                "errors": ["Conflict"],
            },
        ),
        (
            "media_objects",
            {
                "item_id": str(uuid.UUID(int=0)),
                "status": "conflict",
                "bulk_operation_annotatable_id": "bulk_media_id_0",  # comes from the fixture
                "errors": ["Conflict"],
            },
        ),
        (
            "attributes",
            {
                "item_id": str(uuid.UUID(int=0)),
                "status": "conflict",
                "annotatable_id": str(uuid.UUID(int=1)),
                "errors": ["Conflict"],
            },
        ),
    ],
)
def test_hari_uploader_bulk_failure_is_parsed(
    entity_name,
    return_value_bulk_item_result,
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
        medias_cnt=1,
        media_objects_cnt=1,
        attributes_cnt=1,
    )

    mock_response = mock.Mock()
    mock_response.status_code = 409
    mock_response.json.return_value = {
        "status": "failure",
        "summary": {"total": 1, "successful": 0, "failed": 1},
        "results": [return_value_bulk_item_result],
    }

    with mock.patch.object(
        uploader.client,
        f"create_{entity_name}",
        side_effect=errors.APIError(mock_response),
    ):
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
                reference_data=models.PolyLine2DFlatCoordinates(
                    coordinates=[1450, 1550, 1450, 1000],
                    closed=False,
                ),
            )
        )
        media.add_attribute(
            hari_uploader.HARIAttribute(
                id=uuid.UUID(int=0),
                name="attr",
                value="value",
            )
        )
        uploader.add_media(media)

        # Act + Assert
        results = uploader.upload()

        match entity_name:
            case "medias":
                assert results.medias.results[0].status == "conflict"
            case "media_objects":
                assert results.media_objects.results[0].status == "conflict"
            case "attributes":
                assert results.attributes.results[0].status == "conflict"


def test_hari_uploader_skips_uploaded_entities(
    create_configurable_mock_uploader_successful_single_batch_state_aware,
):
    # This test checks that the uploader correctly skips already uploaded medias and objects when they are trying to get uploaded again,
    # for that uploader fetches existing entities from the server and if back reference of media/object matches the existing entity,
    # mock the client to return existing entities and then try to upload them again.
    # uploader sets "uploaded" field to True. During the upload of the batch, it checks if the entity is already uploaded and skips it,
    # assigning ALREADY_EXISTS status to the item response, and treats the response as successful.
    # In the test, we mock getting existing medias and media objects from the server, returning entities that would be overlapping
    # with entities that we try to upload (1 media and 1 object), so the uploader should skip them and not try to upload again.

    # For attributes, we don't check existing ones on the server, we just check which one have ALREADY_EXISTS status
    # and treat them as successful. In test mock the response for attributes to return some existing ones and some new ones.
    # In the test, we mock the response to return some existing attributes and some new ones, and check that the uploader
    # treats existing ones as successful.

    # Arrange
    (
        uploader,
        client,
        create_medias_spy,
        create_media_objects_spy,
        create_attributes_spy,
        create_attributes_mock,
    ) = create_configurable_mock_uploader_successful_single_batch_state_aware(
        dataset_id=uuid.UUID(int=0),
        medias_cnt=1,  # only 1 is really uploaded
        media_objects_cnt=1,  # only 1 is really uploaded
        attributes_cnt=0,  # method that creates attributes is overwritten in the test, we don't need responses generated by the mock, so can pass any random value
    )

    # mock 2 existing medias (media_ref_0 and media_ref_1)
    # mock 2 existing media objects (media_obj_ref_0 and media_obj_ref_1)
    mock_existing_medias = [
        models.MediaResponse(
            id=str(uuid.UUID(int=i)), name=f"media_{i}", back_reference=f"media_ref_{i}"
        )
        for i in range(2)
    ]
    uploader.client.get_medias_paginated = lambda *args, **kwargs: mock_existing_medias
    mock_existing_media_objects = [
        models.MediaObjectResponse(
            id=str(uuid.UUID(int=i)),
            back_reference=f"media_obj_ref_{i}",
        )
        for i in range(2)
    ]
    uploader.client.get_media_objects_paginated = (
        lambda *args, **kwargs: mock_existing_media_objects
    )

    # create medias and objects to be uploaded
    # 2 medias - 1 already uploaded (with back ref media_ref_1), 1 new
    # 2 media objects - 1 already uploaded (with back ref media_obj_ref_1), 1 new
    already_uploaded_media = create_test_media(back_reference="media_ref_1")
    new_media = create_test_media(back_reference="media_ref_2")

    already_uploaded_media_object = create_test_media_object_2d(
        back_reference="media_obj_ref_1"
    )
    new_media_object = create_test_media_object_2d(back_reference="media_obj_ref_2")

    already_uploaded_media.add_media_object(new_media_object)
    new_media.add_media_object(already_uploaded_media_object)

    # create attributes to be uploaded
    # 1 existing media attribute (with id media_attr_id), 1 new media attribute
    # 1 existing media object attribute (with id media_object_attr_id), 1 new media object attribute
    media_attr_id = uuid.UUID(int=0)
    media_object_attr_id = uuid.UUID(int=2)

    already_uploaded_media_attribute = create_test_attribute(
        id=media_attr_id, name="media_attr_1"
    )
    new_media_attribute = create_test_attribute(
        id=uuid.UUID(int=1), name="media_attr_1"
    )
    already_uploaded_media.add_attribute(already_uploaded_media_attribute)
    new_media.add_attribute(new_media_attribute)

    already_uploaded_media_object_attribute = create_test_attribute(
        id=media_attr_id, name="media_attr_2"
    )
    new_media_object_attribute = create_test_attribute(
        id=uuid.UUID(int=3), name="media_attr_2"
    )
    already_uploaded_media_object.add_attribute(already_uploaded_media_object_attribute)
    new_media_object.add_attribute(new_media_object_attribute)

    # mock attribute response (already existing and success)
    mock_create_attribute_response = models.BulkResponse(
        status=models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
        summary=models.BulkUploadSuccessSummary(
            total=4,
            successful=2,
            failed=2,
        ),
        results=[
            # already exist
            models.AttributeCreateResponse(
                item_id=str(media_attr_id),
                status=models.ResponseStatesEnum.ALREADY_EXISTS,
                annotatable_id="some_media_id",
                errors=["already exists"],
            ),
            models.AttributeCreateResponse(
                item_id=str(media_object_attr_id),
                status=models.ResponseStatesEnum.ALREADY_EXISTS,
                annotatable_id="some_media_object_id",
                errors=["already exists"],
            ),
            # new
            models.AttributeCreateResponse(
                item_id=str(media_attr_id),
                status=models.ResponseStatesEnum.SUCCESS,
                annotatable_id="some_media_id_2",
            ),
            models.AttributeCreateResponse(
                item_id=str(media_object_attr_id),
                status=models.ResponseStatesEnum.SUCCESS,
                annotatable_id="some_media_object_id_2",
            ),
        ],
    )
    create_attributes_mock.return_value = mock_create_attribute_response

    # Act
    uploader.add_media(already_uploaded_media, new_media)
    results = uploader.upload()

    # Assert
    assert create_medias_spy.call_count == 1
    media_calls = create_medias_spy.call_args_list
    assert len(media_calls[0].kwargs["medias"]) == 1  # we create only 1 new media
    assert (
        len(results.medias.results) == 2
    )  # but 2 results as we also include already existing media
    assert results.medias.results[0].status == models.ResponseStatesEnum.SUCCESS
    assert results.medias.results[1].status == models.ResponseStatesEnum.ALREADY_EXISTS
    assert results.medias.status == models.ResponseStatesEnum.SUCCESS
    assert results.medias.summary == models.BulkUploadSuccessSummary(
        total=2,
        successful=2,
        failed=0,  # no failed medias as existing one we treat as successful
    )

    assert create_media_objects_spy.call_count == 1
    media_object_calls = create_media_objects_spy.call_args_list
    assert (
        len(media_object_calls[0].kwargs["media_objects"]) == 1
    )  # we create only 1 new media object
    assert (
        len(results.media_objects.results) == 2
    )  # but 2 results as we also include already existing media object
    assert results.medias.results[0].status == models.ResponseStatesEnum.SUCCESS
    assert results.medias.results[1].status == models.ResponseStatesEnum.ALREADY_EXISTS
    assert results.media_objects.status == models.ResponseStatesEnum.SUCCESS
    assert results.media_objects.summary == models.BulkUploadSuccessSummary(
        total=2,
        successful=2,
        failed=0,  # no failed media objects as existing one we treat as successful
    )

    assert create_attributes_spy.call_count == 1
    attribute_calls = create_attributes_spy.call_args_list
    assert (
        len(attribute_calls[0].kwargs["attributes"])
        == 4  # for attribute we try to upload all of them
    )  # we create all attributes anyway
    assert len(results.attributes.results) == 4
    assert results.attributes.status == models.ResponseStatesEnum.SUCCESS
    assert results.attributes.summary == models.BulkUploadSuccessSummary(
        total=4,
        successful=4,
        failed=0,  # no failed attributes as existing one we treat as successful
    )

    # assert progress bars are full
    assert uploader._media_upload_progress.n == uploader._media_upload_progress.total
    assert (
        uploader._media_object_upload_progress.n
        == uploader._media_object_upload_progress.total
    )
    assert (
        uploader._attribute_upload_progress.n
        == uploader._attribute_upload_progress.total
    )


@pytest.mark.parametrize(
    "statuses, summary, expected_status, expected_summary",
    [
        (
            # All successful → success
            [models.ResponseStatesEnum.SUCCESS, models.ResponseStatesEnum.SUCCESS],
            {"total": 2, "successful": 2, "failed": 0},
            models.BulkOperationStatusEnum.SUCCESS,
            {"total": 2, "successful": 2, "failed": 0},
        ),
        (
            # All already exists → success
            [
                models.ResponseStatesEnum.ALREADY_EXISTS,
                models.ResponseStatesEnum.ALREADY_EXISTS,
            ],
            {"total": 2, "successful": 0, "failed": 2},
            models.BulkOperationStatusEnum.SUCCESS,
            {"total": 2, "successful": 2, "failed": 0},
        ),
        (
            # All successful or already exist → overall success
            [
                models.ResponseStatesEnum.SUCCESS,
                models.ResponseStatesEnum.ALREADY_EXISTS,
            ],
            {"total": 2, "successful": 1, "failed": 1},
            models.BulkOperationStatusEnum.SUCCESS,
            {"total": 2, "successful": 2, "failed": 0},
        ),
        (
            # Mixed success + failure → partial success
            [
                models.ResponseStatesEnum.ALREADY_EXISTS,
                models.ResponseStatesEnum.SERVER_ERROR,
                models.ResponseStatesEnum.SUCCESS,
            ],
            {"total": 3, "successful": 1, "failed": 2},
            models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
            {"total": 3, "successful": 2, "failed": 1},
        ),
        (
            # All failed → failure
            [
                models.ResponseStatesEnum.CONFLICT,
                models.ResponseStatesEnum.SERVER_ERROR,
            ],
            {"total": 2, "successful": 0, "failed": 2},
            models.BulkOperationStatusEnum.FAILURE,
            {"total": 2, "successful": 0, "failed": 2},
        ),
    ],
)
def test_reevaluate_bulk_status_for_already_existing_entities(
    statuses, summary, expected_status, expected_summary, mock_uploader_for_batching
):
    uploader, _, _, _ = mock_uploader_for_batching

    response = models.BulkResponse(
        summary=models.BulkUploadSuccessSummary(
            total=summary["total"],
            successful=summary["successful"],
            failed=summary["failed"],
        ),
        results=[
            models.AttributeCreateResponse(
                item_id=str(uuid.uuid4()),
                status=status,
                annotatable_id=str(uuid.uuid4()),
            )
            for status in statuses
        ],
    )

    uploader._reevaluate_bulk_response_for_already_existing_entities(response)

    assert response.status == expected_status
    assert response.summary.total == expected_summary["total"]
    assert response.summary.successful == expected_summary["successful"]
    assert response.summary.failed == expected_summary["failed"]
