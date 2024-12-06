import argparse
import time
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def trigger_metadata_rebuild(
    hari: HARIClient, dataset_id: uuid.UUID, subset_id: uuid.UUID | None
):
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


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create subsets in a HARI dataset based on an attribute."
    )

    # Add command-line arguments.

    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to recreate", required=True
    )

    parser.add_argument(
        "-s", "--subset_id", type=str, help="Subset ID to recreate", required=True
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.UUID = uuid.UUID(args.dataset_id)
    subset_id: uuid.UUID | None = (
        uuid.UUID(args.subset_id) if args.subset_id is not None else None
    )
    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    trigger_metadata_rebuild(hari, dataset_id, subset_id)
