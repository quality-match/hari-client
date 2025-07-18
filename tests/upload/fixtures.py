import typing
import uuid

import pytest

from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models


@pytest.fixture()
def mock_client(test_client, mocker) -> typing.Generator[HARIClient, list[str], None]:
    """Sets up a basic uploader using object_categories
    Mocks the create_subset method to return random subset ids in lexicographical order.
    Mocks the get_attribute_metadata method to return an empty list.
    returns
        uploader: HARIUploader instance
        object_category_vs_subsets: dict[str, str] mapping object category names to their subset ids
    """

    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    create_subset_return_val = [pedestrian_subset_id, wheel_subset_id]

    dataset_id = str(uuid.uuid4())
    scene_one = models.Scene(id=str(uuid.uuid4()), dataset_id=dataset_id)
    scene_two = models.Scene(id=str(uuid.uuid4()), dataset_id=dataset_id)
    create_scene_return_val = [scene_one, scene_two]
    mocker.patch.object(
        test_client, "create_empty_subset", side_effect=create_subset_return_val
    )
    mocker.patch.object(
        test_client, "create_scene", side_effect=create_scene_return_val
    )

    mocker.patch.object(
        test_client,
        "get_subsets_for_dataset",
        side_effect=[
            [],
        ],
    )

    mocker.patch.object(test_client, "get_scenes", return_value=[])

    mocker.patch.object(test_client, "get_attribute_metadata", return_value=[])
    yield test_client, create_subset_return_val


@pytest.fixture()
def mock_uploader_for_object_category_validation(mock_client, mocker):
    client, create_subset_return_val = mock_client
    object_categories = ["pedestrian", "wheel"]
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
        object_categories=set(object_categories),
    )

    assert uploader.object_categories == {
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

    # Mock _get_existing_scenes to return empty list
    mocker.patch.object(client, "get_scenes", return_value=[])

    assert uploader._object_category_subsets == {}
    yield uploader, object_categories_vs_subset_ids


@pytest.fixture()
def mock_uploader_for_scene_validation(mock_client, mocker):
    client, create_scene_return_val = mock_client
    scenes = ["scene_1", "scene_2"]
    uploader = hari_uploader.HARIUploader(
        client=client,
        dataset_id=uuid.UUID(int=0),
        scenes=set(scenes),
    )

    assert uploader.scenes == {"scene_1", "scene_2"}
    scene_names_vs_scene_ids = {
        scene_name: scene_id
        for scene_name, scene_id in zip(scenes, create_scene_return_val)
    }

    # Mock _get_existing_scenes to return empty list
    mocker.patch.object(client, "get_scenes", return_value=[])

    yield uploader, scene_names_vs_scene_ids


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
            ],
            status=models.ResponseStatesEnum.SUCCESS,
            summary=models.BulkUploadSuccessSummary(
                total=1100,
                successful=1100,
                failed=0,
            ),
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
            ],
            status=models.ResponseStatesEnum.SUCCESS,
            summary=models.BulkUploadSuccessSummary(
                total=2200,
                successful=2200,
                failed=0,
            ),
        ),
    )
    mocker.patch.object(client, "create_attributes", return_value=models.BulkResponse())
    mocker.patch.object(client, "get_attribute_metadata", return_value=[])

    # for state aware uploader fetching existing medias and media objects
    mocker.patch.object(test_client, "get_medias_paginated", return_value=[])
    mocker.patch.object(test_client, "get_media_objects_paginated", return_value=[])

    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    object_categories = {"pedestrian", "wheel"}

    mocker.patch.object(
        client,
        "create_empty_subset",
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

    # Mock _get_existing_scenes to return empty list
    mocker.patch.object(client, "get_scenes", return_value=[])

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

    mocker.patch.object(uploader, "_load_dataset", return_value=None)

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
            ],
            status=models.ResponseStatesEnum.SUCCESS,
            summary=models.BulkUploadSuccessSummary(
                total=1,
                successful=1,
                failed=0,
            ),
        ),
    )
    mocker.patch.object(
        client, "create_media_objects", return_value=models.BulkResponse()
    )
    mocker.patch.object(client, "get_attribute_metadata", return_value=[])

    # for state aware uploader fetching existing medias and media objects
    mocker.patch.object(client, "get_medias_paginated", return_value=[])
    mocker.patch.object(client, "get_media_objects_paginated", return_value=[])

    pedestrian_subset_id = str(uuid.uuid4())
    wheel_subset_id = str(uuid.uuid4())
    mocker.patch.object(
        client,
        "create_empty_subset",
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

    mocker.patch.object(client, "get_scenes", return_value=[])

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

    mocker.patch.object(uploader, "_load_dataset", return_value=None)

    return uploader, id_setter_spy


@pytest.fixture()
def create_configurable_mock_uploader_successful_single_batch(mocker, test_client):
    """Creates a configurable mock uploader for a successful upload of a single batch of medias, media objects and attributes.
        The number of medias, media objects and attributes can be configured, as well as the object categories and their corresponding
        subset_ids which are mocked to be created successfully.
        The first call to get_subsets_for_dataset will return an empty list, the second call will return the specified subsets.
        More complex behavior will have to be mocked in the test itself.

     mocked HARIClient methods:
     - create_medias
     - create_media_objects
     - create_attributes
     - create_subset
     - get_subsets_for_dataset
     - get_attribute_metadata (mocked to return an empty list)
     - get_medias_paginated (mocked to return an empty list)
     - get_media_objects_paginated (mocked to return an empty list)

    mocked HARIUploader methods:
     - _set_bulk_operation_annotatable_id
     - _load_dataset

    HARIUploader method spies:
     - _upload_media_batch
     - _upload_media_object_batch
     - _upload_attribute_batch
    """

    def _create_uploader(
        dataset_id: uuid.UUID,
        medias_cnt: int,
        media_objects_cnt: int,
        attributes_cnt: int,
        object_categories: set[str] | None = None,
        create_subset_side_effect: list[str] | None = None,
        get_subsets_for_dataset_side_effect: list[list[models.DatasetResponse]] = [[]],
    ) -> tuple[
        hari_uploader.HARIUploader,
        HARIClient,
        typing.Any,
        typing.Any,
        typing.Any,
        typing.Any,
    ]:
        mocker.patch.object(
            test_client,
            "create_medias",
            return_value=models.BulkResponse(
                results=[
                    models.AnnotatableCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        bulk_operation_annotatable_id=f"bulk_media_id_{i}",
                    )
                    for i in range(medias_cnt)
                ],
                status=models.ResponseStatesEnum.SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=medias_cnt,
                    successful=medias_cnt,
                    failed=0,
                ),
            ),
        )
        mocker.patch.object(
            test_client,
            "create_media_objects",
            return_value=models.BulkResponse(
                results=[
                    models.AnnotatableCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        bulk_operation_annotatable_id=f"bulk_media_object_id_{i}",
                    )
                    for i in range(media_objects_cnt)
                ],
                status=models.ResponseStatesEnum.SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=media_objects_cnt,
                    successful=media_objects_cnt,
                    failed=0,
                ),
            ),
        )
        mocker.patch.object(
            test_client,
            "create_attributes",
            return_value=models.BulkResponse(
                results=[
                    models.AttributeCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        annotatable_id=f"bulk_attribute_id_{i}",
                    )
                    for i in range(attributes_cnt)
                ],
                status=models.ResponseStatesEnum.SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=media_objects_cnt,
                    successful=media_objects_cnt,
                    failed=0,
                ),
            ),
        )
        mocker.patch.object(test_client, "get_attribute_metadata", return_value=[])
        # for state aware uploader fetching existing medias and media objects
        mocker.patch.object(test_client, "get_medias_paginated", return_value=[])
        mocker.patch.object(test_client, "get_media_objects_paginated", return_value=[])

        if create_subset_side_effect is not None:
            mocker.patch.object(
                test_client,
                "create_empty_subset",
                side_effect=create_subset_side_effect,
            )

        mocker.patch.object(
            test_client,
            "get_subsets_for_dataset",
            side_effect=get_subsets_for_dataset_side_effect,
        )

        mocker.patch.object(test_client, "get_scenes", return_value=[])

        uploader = hari_uploader.HARIUploader(
            client=test_client,
            dataset_id=dataset_id,
            object_categories=object_categories,
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
                item.bulk_operation_annotatable_id = (
                    f"bulk_media_id_{running_media_bulk_id}"
                )
                running_media_bulk_id += 1
            elif isinstance(item, hari_uploader.HARIMediaObject):
                item.bulk_operation_annotatable_id = (
                    f"bulk_media_object_id_{running_media_object_bulk_id}"
                )
                running_media_object_bulk_id += 1

        mocker.patch.object(
            uploader,
            "_set_bulk_operation_annotatable_id",
            side_effect=id_setter_mock,
        )
        mocker.patch.object(uploader, "_load_dataset", return_value=None)
        media_spy = mocker.spy(uploader, "_upload_media_batch")
        media_object_spy = mocker.spy(uploader, "_upload_media_object_batch")
        attribute_spy = mocker.spy(uploader, "_upload_attribute_batch")
        subset_create_spy = mocker.spy(test_client, "create_empty_subset")

        return (
            uploader,
            test_client,
            media_spy,
            media_object_spy,
            attribute_spy,
            subset_create_spy,
        )

    return _create_uploader


@pytest.fixture()
def create_configurable_mock_uploader_successful_single_batch_state_aware(
    mocker, test_client
):
    """Creates a configurable mock state aware uploader for a successful upload of a single batch of medias, media objects and attributes.
        The number of medias, media objects and attributes can be configured, as well as the object categories and their corresponding
        subset_ids which are mocked to be created successfully.
        The first call to get_subsets_for_dataset will return an empty list, the second call will return the specified subsets.
        More complex behavior will have to be mocked in the test itself.

     mocked HARIClient methods:
     - create_medias
     - create_media_objects
     - create_attributes
     - create_subset
     - get_subsets_for_dataset
     - get_attribute_metadata (mocked to return an empty list)
     - get_medias_paginated (mocked to return an empty list by default)
     - get_media_objects_paginated (mocked to return an empty list by default)

    mocked HARIUploader methods:
     - _set_bulk_operation_annotatable_id
     - _load_dataset
     - _update_hari_attribute_media_ids (mocked to return an empty list)
     - _update_hari_media_object_media_ids (mocked to return an empty list)
     - _update_hari_attribute_media_object_ids (mocked to return an empty list)

    HARIUploader method spies:
    - create_medias_spy
    - create_media_objects_spy
    - create_attributes_spy
    """

    def _create_uploader(
        dataset_id: uuid.UUID = uuid.UUID(int=0),
        medias_cnt: int = 0,
        media_objects_cnt: int = 0,
        attributes_cnt: int = 0,
        object_categories: set[str] | None = None,
        mock_attribute_response: models.BulkResponse | None = None,
    ) -> tuple[
        hari_uploader.HARIUploader,
        HARIClient,
        typing.Any,
        typing.Any,
        typing.Any,
        typing.Any,
    ]:
        mocker.patch.object(
            test_client,
            "create_medias",
            return_value=models.BulkResponse(
                results=[
                    models.AnnotatableCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        bulk_operation_annotatable_id=f"bulk_media_id_{i}",
                    )
                    for i in range(medias_cnt)
                ],
                status=models.ResponseStatesEnum.SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=medias_cnt,
                    successful=medias_cnt,
                    failed=0,
                ),
            ),
        )
        mocker.patch.object(
            test_client,
            "create_media_objects",
            return_value=models.BulkResponse(
                results=[
                    models.AnnotatableCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        bulk_operation_annotatable_id=f"bulk_media_object_id_{i}",
                    )
                    for i in range(media_objects_cnt)
                ],
                status=models.ResponseStatesEnum.SUCCESS,
                summary=models.BulkUploadSuccessSummary(
                    total=media_objects_cnt,
                    successful=media_objects_cnt,
                    failed=0,
                ),
            ),
        )
        create_attributes_mock = mocker.patch.object(
            test_client,
            "create_attributes",
            return_value=models.BulkResponse(
                results=[
                    models.AttributeCreateResponse(
                        status=models.ResponseStatesEnum.SUCCESS,
                        annotatable_id=f"bulk_attribute_id_{i}",
                    )
                    for i in range(attributes_cnt)
                ]
            ),
        )
        mocker.patch.object(test_client, "get_attribute_metadata", return_value=[])

        mocker.patch.object(test_client, "get_subsets_for_dataset", return_value=[])

        mocker.patch.object(test_client, "get_scenes", return_value=[])

        uploader = hari_uploader.HARIUploader(
            client=test_client,
            dataset_id=dataset_id,
            object_categories=object_categories,
        )
        mocker.patch.object(uploader, "_load_dataset", return_value=None)

        # state aware specific
        mocker.patch.object(test_client, "get_medias_paginated", return_value=[])
        mocker.patch.object(test_client, "get_media_objects_paginated", return_value=[])
        mocker.patch.object(
            uploader, "_update_hari_media_object_media_ids", return_value=[]
        )
        mocker.patch.object(
            uploader, "_update_hari_attribute_media_ids", return_value=[]
        )
        mocker.patch.object(
            uploader, "_update_hari_attribute_media_object_ids", return_value=[]
        )

        create_medias_spy = mocker.spy(test_client, "create_medias")
        create_media_objects_spy = mocker.spy(test_client, "create_media_objects")
        create_attributes_spy = mocker.spy(test_client, "create_attributes")

        return (
            uploader,
            test_client,
            create_medias_spy,
            create_media_objects_spy,
            create_attributes_spy,
            create_attributes_mock,
        )

    return _create_uploader
