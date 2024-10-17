import collections

import pytest

from hari_client import hari_uploader
from hari_client import models


# TODO:
#  - Add tests for the following methods:
#    - object_categories in client initialization unset
#       - media objects with object category name set
#           - and without
#    - object_categories in client initialization set
#       - media objects with object category name set
#           - and without
# - starting an upload with non-eixstent object_categories on server - fail it, continue the upload


def test_add_media(mock_uploader_for_object_category_validation):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation
    assert len(uploader._medias) == 0
    assert uploader._attribute_cnt == 0

    # Act
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image",
            media_type=models.MediaType.IMAGE,
            back_reference="img",
            attributes=[
                hari_uploader.HARIAttribute(
                    id="attr_1",
                    name="my attribute 1",
                    attribute_type=models.AttributeType.Categorical,
                    value="value 1",
                    attribute_group=models.AttributeGroup.InitialAttribute,
                )
            ],
        )
    )

    # Assert
    assert len(uploader._medias) == 1
    assert uploader._attribute_cnt == 1

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
    assert uploader._attribute_cnt == 1


def test_create_object_category_subset(mock_uploader_for_object_category_validation):
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
        object_category_subset_name="pedestrian",
    )
    media_object_1 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
    )
    media_object_1.set_object_category_subset_name("pedestrian")
    media_1.add_media_object(media_object_1)
    uploader.add_media(media_1)
    # Act
    errors = uploader._validate_media_objects_object_category_subsets_consistency()

    # Assert
    assert len(errors) == 0

    # Arrange
    media_object_2 = hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE, back_reference="img_1_obj_2"
    )
    media_object_2.set_object_category_subset_name("some_non-existent-subset_name")
    media_1.add_media_object(media_object_2)

    # Act

    # Assert
    errors = uploader._validate_media_objects_object_category_subsets_consistency()
    assert len(errors) == 1
    assert (
        type(errors[0])
        == hari_uploader.HARIMediaObjectUnknownObjectCategorySubsetNameError
    )


def test_assign_media_objects_to_object_category_subsets(
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
    media_1.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
        )
    )
    uploader.add_media(media_1)
    media_2 = hari_uploader.HARIMedia(
        name="my image 2",
        media_type=models.MediaType.IMAGE,
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_2_obj_1"
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


def test_update_hari_attribute_media_ids(mock_uploader_for_object_category_validation):
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
    media_1.add_attribute(
        hari_uploader.HARIAttribute(
            id="attr_1",
            name="my attribute 1",
            attribute_type=models.AttributeType.Categorical,
            value="value 1",
            attribute_group=models.AttributeGroup.InitialAttribute,
        )
    )
    uploader.add_media(media_1)
    media_2 = hari_uploader.HARIMedia(
        name="my image 2",
        media_type=models.MediaType.IMAGE,
        back_reference="img_2",
    )
    media_2.bulk_operation_annotatable_id = "bulk_id_2"
    media_2.add_attribute(
        hari_uploader.HARIAttribute(
            id="attr_1",
            name="my attribute 2",
            attribute_type=models.AttributeType.Categorical,
            value="value 2",
            attribute_group=models.AttributeGroup.InitialAttribute,
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
    assert uploader._attribute_cnt == 2


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
    attribute_object_1 = hari_uploader.HARIAttribute(
        id="attr_1",
        name="Is human?",
        attribute_type=models.AttributeType.Categorical,
        value="yes",
        attribute_group=models.AttributeGroup.InitialAttribute,
    )
    media_object_1.add_attribute(attribute_object_1)
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
        id="attr_1",
        name="Is human?",
        attribute_type=models.AttributeType.Categorical,
        value="yes",
        attribute_group=models.AttributeGroup.InitialAttribute,
    )
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


def test_hari_uploader_creates_batches_correctly(mock_uploader_for_batching):
    # Arrange
    uploader, media_spy, media_object_spy, attribute_spy = mock_uploader_for_batching

    # 1100 medias --> 3 batches
    # 2200 media_objects --> 5 batches
    # 6600 attributes --> 14 batches
    for i in range(1100):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
        )
        for k in range(2):
            media_object = hari_uploader.HARIMediaObject(
                source=models.DataSource.REFERENCE,
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                hari_uploader.HARIAttribute(
                    id=f"attr_{i}_{k}",
                    name=f"attr_{i}_{k}",
                    attribute_type=models.AttributeType.Categorical,
                    value=f"value_{i}_{k}",
                    attribute_group=models.AttributeGroup.InitialAttribute,
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    hari_uploader.HARIAttribute(
                        id=f"attr_{i}_{k}_{l}",
                        name=f"attr_{i}_{k}_{l}",
                        attribute_type=models.AttributeType.Categorical,
                        value=f"value_{i}_{k}_{l}",
                        attribute_group=models.AttributeGroup.InitialAttribute,
                    )
                )
        uploader.add_media(media)

    # Act
    uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 3
    media_calls = media_spy.call_args_list
    assert len(media_calls[0].kwargs["medias_to_upload"]) == 500
    assert len(media_calls[1].kwargs["medias_to_upload"]) == 500
    assert len(media_calls[2].kwargs["medias_to_upload"]) == 100
    assert len(uploader._medias) == 1100

    assert media_object_spy.call_count == 5
    media_object_calls = media_object_spy.call_args_list
    assert len(media_object_calls[0].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[1].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[2].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[3].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[4].kwargs["media_objects_to_upload"]) == 200
    assert uploader._media_object_cnt == 2200

    assert attribute_spy.call_count == 14
    attribute_calls = attribute_spy.call_args_list
    assert len(attribute_calls[0].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[1].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[2].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[3].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[4].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[5].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[6].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[7].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[8].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[9].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[10].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[11].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[12].kwargs["attributes_to_upload"]) == 500
    assert len(attribute_calls[13].kwargs["attributes_to_upload"]) == 100
    assert uploader._attribute_cnt == 6600


def test_hari_uploader_creates_single_batch_correctly(mock_uploader_for_single_batch):
    # Arrange
    (
        uploader,
        media_spy,
        media_object_spy,
        attribute_spy,
    ) = mock_uploader_for_single_batch

    # 5 medias --> 1 batch
    # 10 media_objects --> 1 batch
    # 30 attributes --> 1 batch
    for i in range(5):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
        )
        for k in range(2):
            media_object = hari_uploader.HARIMediaObject(
                source=models.DataSource.REFERENCE,
                back_reference=f"img_{i}_obj_{k}",
            )
            media.add_media_object(media_object)
            media.add_attribute(
                hari_uploader.HARIAttribute(
                    id=f"attr_{i}_{k}",
                    name=f"attr_{i}_{k}",
                    attribute_type=models.AttributeType.Categorical,
                    value=f"value_{i}_{k}",
                    attribute_group=models.AttributeGroup.InitialAttribute,
                )
            )
            for l in range(2):
                media_object.add_attribute(
                    hari_uploader.HARIAttribute(
                        id=f"attr_{i}_{k}_{l}",
                        name=f"attr_{i}_{k}_{l}",
                        attribute_type=models.AttributeType.Categorical,
                        value=f"value_{i}_{k}_{l}",
                        attribute_group=models.AttributeGroup.InitialAttribute,
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


def test_warning_for_hari_uploader_receives_duplicate_media_back_reference(
    mock_uploader_for_object_category_validation, mocker
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation
    log_spy = mocker.spy(hari_uploader.log, "warning")
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image 1",
            media_type=models.MediaType.IMAGE,
            back_reference="img_1",
        )
    )

    # Act
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image 2",
            media_type=models.MediaType.IMAGE,
            back_reference="img_1",
        )
    )

    # Assert
    assert log_spy.call_count == 1


def test_warning_for_hari_uploader_receives_duplicate_media_object_back_reference(
    mock_uploader_for_object_category_validation,
    mocker,
):
    # Arrange
    (
        uploader,
        object_categories_vs_subsets,
    ) = mock_uploader_for_object_category_validation
    log_spy = mocker.spy(hari_uploader.log, "warning")
    media = hari_uploader.HARIMedia(
        name="my image 1", media_type=models.MediaType.IMAGE, back_reference="img_1"
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

    # Act
    uploader.add_media(media)

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
