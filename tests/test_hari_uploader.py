import pytest

from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models


def test_update_hari_media_object_media_ids():
    # Arrange
    uploader = hari_uploader.HARIUploader(client=None, dataset_id="")
    media_1 = hari_uploader.HARIMedia(
        name="my image 1", media_type=models.MediaType.IMAGE, back_reference="img_1"
    )
    media_1.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference="img_1_obj_1"
        )
    )
    uploader.add_media(media_1)
    media_2 = hari_uploader.HARIMedia(
        name="my image 2", media_type=models.MediaType.IMAGE, back_reference="img_2"
    )
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
                status=models.ResponseStatesEnum.SUCCESS,
            ),
            models.AnnotatableCreateResponse(
                item_id="new_media_id_2",
                back_reference="img_2",
                status=models.ResponseStatesEnum.SUCCESS,
            ),
        ]
    )

    # Act
    uploader._update_hari_media_object_media_ids(media_upload_bulk_response)

    # Assert
    assert uploader._medias["img_1"].media_objects[0].media_id == "new_media_id_1"
    assert uploader._medias["img_2"].media_objects[0].media_id == "new_media_id_2"


def test_hari_uploader_creates_batches_correctly(mocker):
    # Arrange
    # setup mock_client and mock_uploader that allow for testing the full upload method
    mock_client = HARIClient(config=None)
    mocker.patch.object(
        mock_client, "create_medias", return_value=models.BulkResponse()
    )
    mocker.patch.object(
        mock_client, "create_media_objects", return_value=models.BulkResponse()
    )

    mock_uploader = hari_uploader.HARIUploader(client=mock_client, dataset_id="")
    media_spy = mocker.spy(mock_uploader, "_upload_media_batch")
    media_object_spy = mocker.spy(mock_uploader, "_upload_media_object_batch")

    # 1100 medias --> 3 batches
    # 2200 media_objects --> 5 batches
    for i in range(1100):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
        )
        for k in range(2):
            media.add_media_object(
                hari_uploader.HARIMediaObject(
                    source=models.DataSource.REFERENCE,
                    back_reference=f"img_{i}_obj_{k}",
                )
            )
        mock_uploader.add_media(media)

    # Act
    mock_uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 3
    media_calls = media_spy.call_args_list
    assert len(media_calls[0].kwargs["medias_to_upload"]) == 500
    assert len(media_calls[1].kwargs["medias_to_upload"]) == 500
    assert len(media_calls[2].kwargs["medias_to_upload"]) == 100

    assert media_object_spy.call_count == 5
    media_object_calls = media_object_spy.call_args_list
    assert len(media_object_calls[0].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[1].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[2].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[3].kwargs["media_objects_to_upload"]) == 500
    assert len(media_object_calls[4].kwargs["media_objects_to_upload"]) == 200


def test_hari_uploader_creates_single_batch_correctly(mocker):
    # Arrange
    # setup mock_client and mock_uploader that allow for testing the full upload method
    mock_client = HARIClient(config=None)
    mocker.patch.object(
        mock_client, "create_medias", return_value=models.BulkResponse()
    )
    mocker.patch.object(
        mock_client, "create_media_objects", return_value=models.BulkResponse()
    )

    mock_uploader = hari_uploader.HARIUploader(client=mock_client, dataset_id="")
    media_spy = mocker.spy(mock_uploader, "_upload_media_batch")
    media_object_spy = mocker.spy(mock_uploader, "_upload_media_object_batch")

    # 5 medias --> 1 batch
    # 10 media_objects --> 1 batch
    for i in range(5):
        media = hari_uploader.HARIMedia(
            name=f"my image {i}",
            media_type=models.MediaType.IMAGE,
            back_reference=f"img_{i}",
        )
        for k in range(2):
            media.add_media_object(
                hari_uploader.HARIMediaObject(
                    source=models.DataSource.REFERENCE,
                    back_reference=f"img_{i}_obj_{k}",
                )
            )
        mock_uploader.add_media(media)

    # Act
    mock_uploader.upload()

    # Assert
    # check every batch upload method's call
    assert media_spy.call_count == 1
    media_calls = media_spy.call_args_list
    assert len(media_calls[0].kwargs["medias_to_upload"]) == 5

    assert media_object_spy.call_count == 1
    media_object_calls = media_object_spy.call_args_list
    assert len(media_object_calls[0].kwargs["media_objects_to_upload"]) == 10


def test_hari_uploader_receives_duplicate_media_back_reference():
    # Arrange
    uploader = hari_uploader.HARIUploader(client=None, dataset_id="")
    uploader.add_media(
        hari_uploader.HARIMedia(
            name="my image 1",
            media_type=models.MediaType.IMAGE,
            back_reference="img_1",
        )
    )
    with pytest.raises(hari_uploader.DuplicateHARIMediaBackReferenceError):
        uploader.add_media(
            hari_uploader.HARIMedia(
                name="my image 2",
                media_type=models.MediaType.IMAGE,
                back_reference="img_1",
            )
        )


def test_hari_uploader_receives_duplicate_media_object_back_reference():
    # Arrange
    uploader = hari_uploader.HARIUploader(client=None, dataset_id="")
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
    with pytest.raises(hari_uploader.DuplicateHARIMediaObjectBackReferenceError):
        uploader.add_media(media)


def test_hari_uploader_receives_media_without_back_reference():
    # Arrange
    uploader = hari_uploader.HARIUploader(client=None, dataset_id="")
    with pytest.raises(hari_uploader.HARIMediaMissingBackReferenceError):
        uploader.add_media(
            hari_uploader.HARIMedia(
                name="my image 1", media_type=models.MediaType.IMAGE, back_reference=""
            )
        )


def test_hari_uploader_receives_media_object_without_back_reference():
    # Arrange
    uploader = hari_uploader.HARIUploader(client=None, dataset_id="")
    media = hari_uploader.HARIMedia(
        name="my image 1", media_type=models.MediaType.IMAGE, back_reference="img_1"
    )
    media.add_media_object(
        hari_uploader.HARIMediaObject(
            source=models.DataSource.REFERENCE, back_reference=""
        )
    )
    with pytest.raises(hari_uploader.HARIMediaObjectMissingBackReferenceError):
        uploader.add_media(media)


@pytest.mark.parametrize(
    "bulk_responses, expected_merged_response",
    [
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
                        ),
                        models.AnnotatableCreateResponse(
                            item_id="2",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_2",
                        ),
                    ]
                ),
                models.BulkResponse(
                    results=[
                        models.AnnotatableCreateResponse(
                            item_id="3",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_3",
                        ),
                        models.AnnotatableCreateResponse(
                            item_id="4",
                            status=models.ResponseStatesEnum.SUCCESS,
                            back_reference="back_ref_4",
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
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="2",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_2",
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="3",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_3",
                    ),
                    models.AnnotatableCreateResponse(
                        item_id="4",
                        status=models.ResponseStatesEnum.SUCCESS,
                        back_reference="back_ref_4",
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
