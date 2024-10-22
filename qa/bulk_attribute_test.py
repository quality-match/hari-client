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
# Replace "CHANGEME" with your own user group!
new_dataset = hari.create_dataset(name="BB_local_client", user_group="QM-ops")
dataset_id = new_dataset.id
print("Dataset created with id:", new_dataset.id)

from qa.qa_setup import image_dir

# 3. Set up a media and somemedia objects

media_1 = hari_uploader.HARIMedia(
    file_path=str(image_dir / "ecp1.png"),
    name="cam 1",
    back_reference="image 1",
    media_type=models.MediaType.IMAGE,
)
media_object_1 = hari_uploader.HARIMediaObject(
    back_reference="object_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=100.0,
        y=104.0,
        width=56.0,
        height=42.0,
    ),
)

n_media_attributes = 200
n_object_attributes = 308

# add initial attributes with the same type to media and media objects
init_attribute_media_1_id = str(uuid.uuid4())
init_attribute_object_1_id = str(uuid.uuid4())

for i in range(n_media_attributes):
    media_1.add_attribute(
        hari_uploader.HARIAttribute(
            id=str(uuid.uuid4()),
            name=f"initMediaAttributeCat_{i}",
            attribute_type=models.AttributeType.Categorical,
            value=f"string{i}",
        )
    )

for i in range(n_object_attributes):
    media_object_1.add_attribute(
        hari_uploader.HARIAttribute(
            id=str(uuid.uuid4()),
            name=f"initObjectAttributeSlid_{i}",
            attribute_type=models.AttributeType.Slider,
            value=i,
        )
    )


media_1.add_media_object(media_object_1)

# 4. Set up the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(client=hari, dataset_id=dataset_id)
uploader.add_media(media_1)

# 5. Trigger the upload process
upload_results = uploader.upload()

# Inspect upload results
print(f"media upload status: {upload_results.medias.status.value}")
print(f"media upload summary\n  {upload_results.medias.summary}")

print(f"media object upload status: {upload_results.media_objects.status.value}")
print(f"media object upload summary\n  {upload_results.media_objects.summary}")

print(f"attribute upload status: {upload_results.attributes.status.value}")
print(f"attribute upload summary\n  {upload_results.attributes.summary}")

if (
    upload_results.medias.status != models.BulkOperationStatusEnum.SUCCESS
    or upload_results.media_objects.status != models.BulkOperationStatusEnum.SUCCESS
    or upload_results.attributes.status != models.BulkOperationStatusEnum.SUCCESS
):
    print(
        "The data upload wasn't fully successful. Subset and metadata creation are skipped. See the details below."
    )
    print(f"media upload details: {upload_results.medias.results}")
    print(f"media objects upload details: {upload_results.media_objects.results}")
    print(f"attributes upload details: {upload_results.attributes.results}")
    sys.exit(1)

# 6. Create a subset
print("Creating new subset...")
new_subset_id = hari.create_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="All media objects 3",
)
print(f"Created new subset with id {new_subset_id}")

# 7. Trigger metadata updates
print("Triggering metadata updates...")
# create a trace_id to track triggered metadata update jobs
metadata_rebuild_trace_id = uuid.uuid4()
print(f"metadata_rebuild jobs trace_id: {metadata_rebuild_trace_id}")
metadata_rebuild_jobs = hari.trigger_dataset_metadata_rebuild_job(
    dataset_id=dataset_id, trace_id=metadata_rebuild_trace_id
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
            in [models.ProcessingJobStatus.CREATED, models.ProcessingJobStatus.RUNNING]
            for status in job_statuses
        ]
    )
    if jobs_are_still_running:
        print(f"waiting for metadata_rebuild jobs to finish, {job_statuses=}")
        time.sleep(10)

print(f"metadata_rebuild jobs finished with status {job_statuses=}")
