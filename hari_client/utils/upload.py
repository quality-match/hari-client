import time
import uuid
from typing import Tuple

from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.models.models import Media


def trigger_and_display_metedata_update(
    hari: HARIClient, dataset_id: uuid.UUID, subset_id: uuid.UUID | None
):
    """
    Trigger and wait for the metadata update jobs to finish, then print their statuses.

    :param hari: An instance of HARIClient to interact with the HARI API.
    :param dataset_id: The UUID of the dataset for which the metadata should be rebuilt.
    :param subset_id: The UUID of a specific subset, or None to rebuild metadata for the entire dataset.
    """
    print("Triggering metadata updates...")
    # create a trace_id to track triggered metadata update jobs
    metadata_rebuild_trace_id = uuid.uuid4()
    print(f"metadata_rebuild jobs trace_id: {metadata_rebuild_trace_id}")
    metadata_rebuild_jobs = hari.trigger_dataset_metadata_rebuild_job(
        dataset_id=dataset_id, trace_id=metadata_rebuild_trace_id, subset_id=subset_id
    )

    # track the status of all metadata rebuild jobs and wait for them to finish
    job_statuses = []
    jobs_are_still_running = True
    while jobs_are_still_running:
        jobs = hari.get_processing_jobs(trace_id=metadata_rebuild_trace_id)
        job_statuses = [(job.process_name, job.status.value, job.id) for job in jobs]

        jobs_are_still_running = any(
            [
                status[1]
                in [
                    models.ProcessingJobStatus.CREATED,
                    models.ProcessingJobStatus.RUNNING,
                ]
                for status in job_statuses
            ]
        )
        if jobs_are_still_running:
            print(f"waiting for metadata_rebuild jobs to finish, {job_statuses=}")
            time.sleep(10)

    print(f"metadata_rebuild jobs finished with status {job_statuses=}")


def check_and_create_dataset(
    hari: HARIClient, dataset_name: str, user_group: str, is_anonymized: bool
) -> uuid.UUID:
    """
    Check if a dataset with the given name exists. If not, create it.

    :param hari: An instance of HARIClient to interact with the HARI API.
    :param dataset_name: The name of the dataset to check or create.
    :param user_group: The user group under which the dataset should be created.
    :param is_anonymized: Whether the dataset should be created with anonymized data.
    :return: The UUID of the found or created dataset.
    """
    datasets = hari.get_datasets()
    dataset_names = [dataset.name for dataset in datasets]

    assert user_group is not None, "User group is required."

    if dataset_name not in dataset_names:
        new_dataset = hari.create_dataset(
            name=dataset_name, user_group=user_group, is_anonymized=is_anonymized
        )
        print("Dataset created with id:", new_dataset.id)
        return new_dataset.id
    else:
        dataset_id = datasets[dataset_names.index(dataset_name)].id
        print("Found existing dataset with id:", dataset_id)

        return dataset_id


def check_and_create_subset_for_all(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    subset_name: str,
    subset_type: models.SubsetType,
) -> Tuple[uuid.UUID, bool]:
    """
    Check if a subset with the given name exists within a dataset. If not, create it.

    :param hari: An instance of HARIClient to interact with the HARI API.
    :param dataset_id: The UUID of the dataset.
    :param subset_name: The name of the subset to check or create.
    :param subset_type: The type of the subset to create if it doesn't exist.
    :return: A tuple containing:
        - The UUID of the found or created subset.
        - A boolean indicating whether the subset with the given name already exists.
    """
    subsets = hari.get_subsets_for_dataset(dataset_id)
    subset_names = [subset.name for subset in subsets]
    if subset_name not in subset_names:
        new_subset_id = hari.create_subset(
            dataset_id=dataset_id,
            subset_type=subset_type,
            subset_name=subset_name,
        )
        print(f"Created new subset with id {new_subset_id}")
        return new_subset_id, False
    else:
        subset = subsets[subset_names.index(subset_name)]
        new_subset_id = subset.id
        print("Found subset with id:", new_subset_id)

        return new_subset_id, True


def check_and_upload_dataset(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    object_categories: list[str],
    medias: list[Media],
    new_subset_name: str = "All media objects",
    subset_type: models.SubsetType = models.SubsetType.MEDIA_OBJECT,
):
    """
    Check and upload data to an existing or new dataset, optionally creating a new subset.
    If new data is uploaded, trigger a metadata rebuild.

    :param hari: An instance of HARIClient to interact with the HARI API.
    :param dataset_id: The UUID of the dataset to upload data to.
    :param object_categories: A list of object categories to be associated with the data.
    :param medias: A list of media objects to be uploaded.
    :param new_subset_name: The name of the subset to create or use.
    :param subset_type: The type of subset (e.g., MEDIA_OBJECT).
    """
    print("Prepare Upload to HARI...")

    uploader = hari_uploader.HARIUploader(
        client=hari, dataset_id=dataset_id, object_categories=object_categories
    )

    uploaded_medias = hari.get_medias(dataset_id)
    uploaded_back_references = [m.back_reference for m in uploaded_medias]

    elements_to_upload = 0
    for media in medias:
        if media.back_reference not in uploaded_back_references:
            uploader.add_media(media)
            elements_to_upload += 1

    if elements_to_upload > 0:
        upload_results = uploader.upload()

        # Inspect upload results
        print(f"media upload status: {upload_results.medias.status.value}")
        print(f"media upload summary\n  {upload_results.medias.summary}")

        print(
            f"media object upload status: {upload_results.media_objects.status.value}"
        )
        print(f"media object upload summary\n  {upload_results.media_objects.summary}")

        print(f"attribute upload status: {upload_results.attributes.status.value}")
        print(f"attribute upload summary\n  {upload_results.attributes.summary}")

        if (
            upload_results.medias.status != models.BulkOperationStatusEnum.SUCCESS
            or upload_results.media_objects.status
            != models.BulkOperationStatusEnum.SUCCESS
            or upload_results.attributes.status
            != models.BulkOperationStatusEnum.SUCCESS
        ):
            print(
                "The data upload wasn't fully successful. Subset and metadata creation are skipped. See the details below."
            )
            print(f"media upload details: {upload_results.medias.results}")

    else:
        print("WARNING: No data for upload specified which is not already uploaded.")

    new_subset_id, reused = check_and_create_subset_for_all(
        hari, dataset_id, new_subset_name, subset_type
    )

    if reused:
        print(
            "WARNING: You did not create a new subset since the name already exists. "
            "If you added new images during upload the metadata update will be skipped for the new images. "
            "If you added new images please provide a new subset name or delete the old one."
        )

    # Trigger metadata updates
    trigger_and_display_metedata_update(
        hari, dataset_id=dataset_id, subset_id=new_subset_id
    )
