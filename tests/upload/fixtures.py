import uuid

import pytest

from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models


@pytest.fixture()
def mock_client(
    test_client, mocker
) -> tuple[hari_uploader.HARIUploader, HARIClient, dict[str, str]]:
    """Sets up a basic uploader using object_categories
    Mocks the create_subset method to return random subset ids in lexicographical order
    returns
        uploader: HARIUploader instance
        object_category_vs_subsets: dict[str, str] mapping object category names to their subset ids
    """

    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    create_subset_return_val = [pedestrian_subset_id, wheel_subset_id]
    mocker.patch.object(
        test_client, "create_subset", side_effect=create_subset_return_val
    )
    yield test_client, create_subset_return_val


@pytest.fixture()
def mock_uploader_for_object_category_validation(mock_client):
    client, create_subset_return_val = mock_client
    object_categories = ["pedestrian", "wheel"]
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
        object_categories_to_validate=set(object_categories),
    )

    assert uploader.object_categories_to_validate == {
        "pedestrian",
        "wheel",
    }
    # lexigraphically sorted object categories vs subset ids
    object_categories_vs_subset_ids = {
        object_category_name: subset_id
        for object_category_name, subset_id in zip(
            object_categories, create_subset_return_val
        )
    }

    assert uploader._object_category_subsets == {}
    yield uploader, object_categories_vs_subset_ids


@pytest.fixture()
def mock_uploader_for_batching(test_client, mocker):
    client = test_client

    # setup mock_client and mock_uploader that allow for testing the full upload method
    mocker.patch.object(
        client,
        "create_medias",
        return_value=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    status=models.ResponseStatesEnum.SUCCESS,
                    bulk_operation_annotatable_id=f"bulk_id_{i}",
                )
                for i in range(1100)
            ]
        ),
    )
    mocker.patch.object(
        client,
        "create_media_objects",
        return_value=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    status=models.ResponseStatesEnum.SUCCESS,
                    bulk_operation_annotatable_id=f"bulk_id_{i}",
                )
                for i in range(2200)
            ]
        ),
    )
    mocker.patch.object(client, "create_attributes", return_value=models.BulkResponse())
    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    object_categories = {"pedestrian", "wheel"}

    mocker.patch.object(
        client,
        "create_subset",
        side_effect=[pedestrian_subset_id, wheel_subset_id],
    )
    dataset_response = models.DatasetResponse(
        id=uuid.UUID(int=0),
        name="my dataset",
        num_medias=1,
        num_media_objects=1,
        num_instances=1,
        mediatype=models.MediaType.IMAGE,
    )
    mocker.patch.object(
        client,
        "get_subsets_for_dataset",
        side_effect=[
            [dataset_response],
        ],
    )
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
    )

    # there are multiple batches of medias and media objects, but the bulk_ids for the medias are expected to be continuous
    # as implemented in the create_medias mock above.
    global running_media_bulk_id
    running_media_bulk_id = 0
    global running_media_object_bulk_id
    running_media_object_bulk_id = 0

    def id_setter_mock(
        item: hari_uploader.HARIMedia | hari_uploader.HARIMediaObject,
    ):
        global running_media_bulk_id
        global running_media_object_bulk_id
        if isinstance(item, hari_uploader.HARIMedia):
            item.bulk_operation_annotatable_id = f"bulk_id_{running_media_bulk_id}"
            running_media_bulk_id += 1
        elif isinstance(item, hari_uploader.HARIMediaObject):
            item.bulk_operation_annotatable_id = (
                f"bulk_id_{running_media_object_bulk_id}"
            )
            running_media_object_bulk_id += 1

    media_spy = mocker.spy(uploader, "_upload_media_batch")
    media_object_spy = mocker.spy(uploader, "_upload_media_object_batch")
    attribute_spy = mocker.spy(uploader, "_upload_attribute_batch")

    mocker.patch.object(
        uploader,
        "_set_bulk_operation_annotatable_id",
        side_effect=id_setter_mock,
    )
    yield uploader, media_spy, media_object_spy, attribute_spy


@pytest.fixture()
def mock_uploader_for_single_batch(test_client, mocker):
    client = test_client

    # setup mock_client and mock_uploader that allow for testing the full upload method
    mocker.patch.object(
        client,
        "create_medias",
        return_value=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    status=models.ResponseStatesEnum.SUCCESS,
                    bulk_operation_annotatable_id=f"bulk_id_{i}",
                )
                for i in range(5)
            ]
        ),
    )
    mocker.patch.object(
        client,
        "create_media_objects",
        return_value=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    status=models.ResponseStatesEnum.SUCCESS,
                    bulk_operation_annotatable_id=f"bulk_id_{i}",
                )
                for i in range(10)
            ]
        ),
    )

    mocker.patch.object(client, "create_attributes", return_value=models.BulkResponse())

    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    mocker.patch.object(
        client,
        "create_subset",
        side_effect=[pedestrian_subset_id, wheel_subset_id],
    )
    dataset_response = models.DatasetResponse(
        id=uuid.UUID(int=0),
        name="my dataset",
        num_medias=1,
        num_media_objects=1,
        num_instances=1,
        mediatype=models.MediaType.IMAGE,
    )
    mocker.patch.object(
        client,
        "get_subsets_for_dataset",
        side_effect=[
            [dataset_response],
        ],
    )
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
    )

    global running_media_bulk_id
    running_media_bulk_id = 0
    global running_media_object_bulk_id
    running_media_object_bulk_id = 0

    def id_setter_mock(
        item: hari_uploader.HARIMedia | hari_uploader.HARIMediaObject,
    ):
        global running_media_bulk_id
        global running_media_object_bulk_id
        if isinstance(item, hari_uploader.HARIMedia):
            item.bulk_operation_annotatable_id = f"bulk_id_{running_media_bulk_id}"
            running_media_bulk_id += 1
        elif isinstance(item, hari_uploader.HARIMediaObject):
            item.bulk_operation_annotatable_id = (
                f"bulk_id_{running_media_object_bulk_id}"
            )
            running_media_object_bulk_id += 1

    mocker.patch.object(
        uploader,
        "_set_bulk_operation_annotatable_id",
        side_effect=id_setter_mock,
    )
    media_spy = mocker.spy(uploader, "_upload_media_batch")
    media_object_spy = mocker.spy(uploader, "_upload_media_object_batch")
    attribute_spy = mocker.spy(uploader, "_upload_attribute_batch")

    yield uploader, media_spy, media_object_spy, attribute_spy


@pytest.fixture()
def mock_uploader_for_bulk_operation_annotatable_id_setter(test_client, mocker):
    client = test_client

    mocker.patch.object(
        client,
        "create_medias",
        return_value=models.BulkResponse(
            results=[
                models.AnnotatableCreateResponse(
                    status=models.ResponseStatesEnum.SUCCESS,
                    item_id="server_side_media_id",
                    bulk_operation_annotatable_id="bulk_id",
                )
            ]
        ),
    )
    mocker.patch.object(
        client, "create_media_objects", return_value=models.BulkResponse()
    )
    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    mocker.patch.object(
        client,
        "create_subset",
        side_effect=[pedestrian_subset_id, wheel_subset_id],
    )
    dataset_response = models.DatasetResponse(
        id=uuid.UUID(int=0),
        name="my dataset",
        num_medias=1,
        num_media_objects=1,
        num_instances=1,
        mediatype=models.MediaType.IMAGE,
    )
    mocker.patch.object(
        client,
        "get_subsets_for_dataset",
        side_effect=[
            [dataset_response],
        ],
    )
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
    )

    def id_setter_mock(
        item: hari_uploader.HARIMedia | hari_uploader.HARIMediaObject,
    ):
        item.bulk_operation_annotatable_id = "bulk_id"

    mocker.patch.object(
        uploader,
        "_set_bulk_operation_annotatable_id",
        side_effect=id_setter_mock,
    )
    id_setter_spy = mocker.spy(uploader, "_set_bulk_operation_annotatable_id")

    return uploader, id_setter_spy
