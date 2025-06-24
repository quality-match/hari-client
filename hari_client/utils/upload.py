import time
import uuid
from typing import Tuple

import hari_client.upload.state_aware_hari_uploader as hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.upload.hari_uploader import HARIMedia
from hari_client.utils import logger

log = logger.setup_logger(__name__)


def trigger_and_display_metadata_update(
    hari: HARIClient, dataset_id: uuid.UUID, subset_id: uuid.UUID | None = None
):
    """
    Trigger and wait for the metadata update jobs to finish, then print their statuses.

    Args:
        hari: An instance of HARIClient to interact with the HARI API.
        dataset_id: The UUID of the dataset for which the metadata should be rebuilt.
        subset_id: The UUID of a specific subset, or None to rebuild metadata for the entire dataset.
    """
    log.info("Triggering metadata updates...")
    # create a trace_id to track triggered metadata update jobs
    metadata_rebuild_trace_id = uuid.uuid4()
    log.info(f"metadata_rebuild jobs trace_id: {metadata_rebuild_trace_id}")
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
            log.info(f"waiting for metadata_rebuild jobs to finish, {job_statuses=}")
            time.sleep(10)

    log.info(f"metadata_rebuild jobs finished with status {job_statuses=}")


def get_or_create_dataset(
    hari: HARIClient,
    dataset_name: str,
    user_group: str,
    is_anonymized: bool,
    external_media_source: models.ExternalMediaSourceAPICreate | None = None,
) -> uuid.UUID:
    """
    Check if a dataset with the given name exists. If not, create it.

    Args:
        hari: An instance of HARIClient to interact with the HARI API.
        dataset_name: The name of the dataset to check or create.
        user_group: The user group under which the dataset should be created.
        is_anonymized: Whether the dataset should be created with anonymized data.
        external_media_source: The external media source to use for the dataset if needed, defaults to None.
    Returns:
         uuid: The UUID of the found or created dataset.
    """
    if user_group is None:
        raise ValueError("User group is required.")

    datasets = hari.get_datasets()
    dataset_names = [dataset.name for dataset in datasets]

    if dataset_name not in dataset_names:
        new_dataset = hari.create_dataset(
            name=dataset_name,
            user_group=user_group,
            is_anonymized=is_anonymized,
            external_media_source=external_media_source,
        )
        log.info(f"Dataset created with id: {new_dataset.id}")
        return new_dataset.id
    else:
        dataset_id = datasets[dataset_names.index(dataset_name)].id
        log.info(f"Found existing dataset with id: {dataset_id}")

        return dataset_id


def get_or_create_subset_for_all(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    subset_name: str,
    subset_type: models.SubsetType,
) -> Tuple[uuid.UUID, bool]:
    """
    Check if a subset with the given name exists within a dataset. If not, create it.

    Args:
        hari: An instance of HARIClient to interact with the HARI API.
        dataset_id: The UUID of the dataset.
        subset_name: The name of the subset to check or create.
        subset_type: The type of the subset to create if it doesn't exist.
    Returns:
        Tuple[uuid.UUID, bool] : tuple containing:
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
        log.info(f"Created new subset with id {new_subset_id}")
        return uuid.UUID(new_subset_id), False
    else:
        subset = subsets[subset_names.index(subset_name)]
        new_subset_id = subset.id
        log.info(f"Found existing subset with id: {new_subset_id}")

        return new_subset_id, True


def check_and_upload_dataset(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    medias: list[HARIMedia],
    object_categories: set[str] | None = None,
    new_subset_name: str = "All media objects",
    subset_type: models.SubsetType = models.SubsetType.MEDIA_OBJECT,
):
    """
    Check and upload data to an existing or new dataset, optionally creating a new subset.
    If new data is uploaded, trigger a metadata rebuild.

    Args:
        hari: An instance of HARIClient to interact with the HARI API.
        dataset_id: The UUID of the dataset to upload data to.
        object_categories: A list of object categories to be associated with the data.
        medias: A list of media objects to be uploaded.
        new_subset_name: The name of the subset to create or use.
        subset_type: The type of subset (e.g., MEDIA_OBJECT).
    """
    log.info("Prepare Upload to HARI...")

    uploader = hari_uploader.HARIUploader(
        client=hari, dataset_id=dataset_id, object_categories=object_categories
    )

    for media in medias:
        uploader.add_media(media)

    upload_results = uploader.upload()

    # Inspect upload results
    num_conflict_media = len(
        [
            r.status
            for r in upload_results.medias.results
            if r.status == models.ResponseStatesEnum.CONFLICT
        ]
    )
    num_conflict_media_objects = len(
        [
            r.status
            for r in upload_results.media_objects.results
            if r.status == models.ResponseStatesEnum.CONFLICT
        ]
    )
    num_conflict_attributes = len(
        [
            r.status
            for r in upload_results.attributes.results
            if r.status == models.ResponseStatesEnum.CONFLICT
        ]
    )
    print(f"media upload status: {upload_results.medias.status.value}")
    print(
        f"media upload summary\n  {upload_results.medias.summary} due to skipped {num_conflict_media}"
    )

    print(f"media object upload status: {upload_results.media_objects.status.value}")
    print(
        f"media object upload summary\n  {upload_results.media_objects.summary} due to skipped {num_conflict_media_objects}"
    )

    print(f"attribute upload status: {upload_results.attributes.status.value}")
    print(
        f"attribute upload summary\n  {upload_results.attributes.summary} due to skipped {num_conflict_attributes}"
    )

    # check if any failed (not due to skipping/conflict)
    if (
        upload_results.medias.summary.failed - num_conflict_media > 0
        or upload_results.media_objects.summary.failed - num_conflict_media_objects > 0
        or upload_results.attributes.summary.failed - num_conflict_attributes > 0
    ):
        print("The data upload wasn't fully successful. See the details below.")
        print(f"media upload details: {upload_results.medias.results}")
        print(f"media objects upload details: {upload_results.media_objects.results}")
        print(f"attributes upload details: {upload_results.attributes.results}")

    new_subset_id, exists = get_or_create_subset_for_all(
        hari, dataset_id, new_subset_name, subset_type
    )

    if exists:
        # TODO This is not optimal, if data is appended to a dataset
        #  The subset is not updated and only this error message is shown
        log.warning(
            "You did not create a new subset since the name already exists. "
            "If you added new images during upload the metadata update will be skipped for the new images. "
            "If you added new images please provide a new subset name or delete the old one."
        )

    # Trigger metadata updates
    trigger_and_display_metadata_update(
        hari, dataset_id=dataset_id, subset_id=new_subset_id
    )
