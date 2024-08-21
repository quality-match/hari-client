import time
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client import models

# Replace by your own credentials!
config = Config(hari_username="jane.doe@gmail.com", hari_password="SuperSecretPassword")

if __name__ == "__main__":
    # 1. Initialize the HARI client
    hari = HARIClient(config=config)

    # 2. Create a dataset
    # Replace "CHANGEME" with you own user group!
    user_group = "CHANGEME"
    new_dataset = hari.create_dataset(name="My first dataset", customer=user_group)
    print("Dataset created with id:", new_dataset.id)

    # 3. Upload an image
    file_path = "busy_street.jpg"
    new_media = hari.create_media(
        dataset_id=new_dataset.id,
        file_path=file_path,
        name="A busy street",
        media_type=models.MediaType.IMAGE,
        back_reference=file_path,
    )
    print("New media created with id: ", new_media.id)

    # 4. Create a geometry on the image
    geometry = models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1600.0,
        y=2106.0,
        width=344.0,
        height=732.0,
    )
    new_media_object = hari.create_media_object(
        dataset_id=new_dataset.id,
        media_id=new_media.id,
        back_reference="Pedestrian-1",
        source=models.DataSource.REFERENCE,
        reference_data=geometry,
    )
    print("New media object created with id:", new_media_object.id)

    # 5. Create a subset
    new_subset_id = hari.create_subset(
        dataset_id=new_dataset.id,
        subset_type=models.SubsetType.MEDIA_OBJECT,
        subset_name="All media objects",
    )
    print(f"Created new subset with id {new_subset_id}")

    # 6. Trigger metadata updates
    print("Triggering metadata updates...")
    # create a trace_id to track triggered metadata update jobs
    trace_id = str(uuid.uuid4())

    hari.trigger_thumbnails_creation_job(
        dataset_id=new_dataset.id, subset_id=new_subset_id, trace_id=trace_id
    )
    hari.trigger_histograms_update_job(
        new_dataset.id, compute_for_all_subsets=True, trace_id=trace_id
    )

    # in order to trigger crops creation, thumbnails should be created first.
    time.sleep(5)  # give jobs time to start
    jobs = hari.get_processing_jobs(
        trace_id=trace_id
    )  # query all the jobs for the given trace_id
    # get the thumbnails job id
    thumbnails_job_id = next(
        (
            job.id
            for job in jobs
            if job.process_name
            == models.ProcessingJobsForMetadataUpdate.THUMBNAILS_CREATION
        ),
        "",
    )

    job_status = ""
    while job_status != models.ProcessingJobStatus.SUCCESS:
        status = hari.get_processing_job(processing_job_id=thumbnails_job_id)
        job_status = status.status
        print(f"waiting for thumbnails to be created, status={job_status}")
        time.sleep(10)

    hari.trigger_crops_creation_job(
        dataset_id=new_dataset.id, subset_id=new_subset_id, trace_id=trace_id
    )
