import sys
import time
import uuid

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

# The Config class will look for a .env file in your script's current working directory.
# Copy the .env_example file as .env for that and store your HARI credentials in there.
config = Config()

# 1. Initialize the HARI client
hari = HARIClient(config=config)

# 2. Create a dataset
# Replace "CHANGEME" with you own user group!
user_group = "CHANGEME"
new_dataset = hari.create_dataset(name="My first dataset", customer=user_group)
print("Dataset created with id:", new_dataset.id)

# 3. Setup your medias and all of their media objects.
# In this example we use 3 images with 1 media object each.
media_1 = hari_uploader.HARIMedia(
    file_path="images/image_1.jpg",
    name="A busy street 1",
    back_reference="image_1",
    media_type=models.MediaType.IMAGE,
)
media_1.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="pedestrian_1",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1400.0,
            y=1806.0,
            width=344.0,
            height=732.0,
        ),
    )
)

media_2 = hari_uploader.HARIMedia(
    file_path="images/image_2.jpg",
    name="A busy street 2",
    back_reference="image 2",
    media_type=models.MediaType.IMAGE,
)
media_2.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="motorcycle_wheel_1",
        media_type=models.MediaType.IMAGE,
        reference_data=models.Point2DXY(x=975.0, y=2900.0),
    )
)

media_3 = hari_uploader.HARIMedia(
    file_path="images/image_3.jpg",
    name="A busy street 3",
    back_reference="image 3",
    media_type=models.MediaType.IMAGE,
)
media_3.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="road marking",
        media_type=models.MediaType.IMAGE,
        reference_data=models.PolyLine2DFlatCoordinates(
            coordinates=[1450, 1550, 1450, 1000],
            closed=False,
        ),
    )
)

# 4. Setup the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(client=hari, dataset_id=new_dataset.id)
uploader.add_media(media_1, media_2, media_3)

# 5. Trigger the upload process
upload_results = uploader.upload()

# Inspect upload results
print(f"media upload status: {upload_results.medias.status.value}")
print(f"media upload summary\n  {upload_results.medias.summary}")

print(f"media_object upload status: {upload_results.media_objects.status.value}")
print(f"media object upload summary\n  {upload_results.media_objects.summary}")

if (
    upload_results.medias.status != models.BulkOperationStatusEnum.SUCCESS
    or upload_results.media_objects.status != models.BulkOperationStatusEnum.SUCCESS
):
    print(
        "The data upload wasn't fully successful. Subset and metadata creation are skipped. See the details below."
    )
    print(f"media upload details: {upload_results.medias.results}")
    print(f"media object upload details: {upload_results.media_objects.results}")
    sys.exit(1)

# 6. Create a subset
new_subset_id = hari.create_subset(
    dataset_id=new_dataset.id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="All media objects",
)
print(f"Created new subset with id {new_subset_id}")

# 7. Trigger metadata updates
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
# give the thumbnails creation job time to start
thumbnails_job_id = ""
while thumbnails_job_id == "":
    # query all the jobs for the given trace_id
    jobs = hari.get_processing_jobs(trace_id=trace_id)
    # try to get the thumbnails creation job id
    thumbnails_job_id = next(
        (
            job.id
            for job in jobs
            if job.process_name
            == models.ProcessingJobsForMetadataUpdate.THUMBNAILS_CREATION
        ),
        "",
    )

    if thumbnails_job_id != "":
        break
    time.sleep(5)

job_status = ""
while job_status != models.ProcessingJobStatus.SUCCESS:
    status = hari.get_processing_job(processing_job_id=thumbnails_job_id)
    job_status = status.status
    print(f"waiting for thumbnails to be created, status={job_status}")
    time.sleep(10)

hari.trigger_crops_creation_job(
    dataset_id=new_dataset.id, subset_id=new_subset_id, trace_id=trace_id
)
