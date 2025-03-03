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
new_dataset = hari.create_dataset(name="BB_ds_video", user_group="QM-ops")
print("Dataset created with id:", new_dataset.id)

dataset_id = new_dataset.id

# 3. Set up your medias and all of their media objects and attributes.
# In this example we use 3 images with 1 media object each.
# The first media and media object have 1 attribute each.
media_1 = hari_uploader.HARIMedia(
    # note: the file_path won't be saved in HARI, it's only used during uploading
    file_path="images/ThumbnailsMov_netw_opt.mov",
    name="camera 1",
    back_reference="video 1",
    media_type=models.MediaType.VIDEO,
)

media_2 = hari_uploader.HARIMedia(
    # note: the file_path won't be saved in HARI, it's only used during uploading
    file_path="images/ThumbnailsMP4_netw_opt.mp4",
    name="camera 2",
    back_reference="video 2",
    media_type=models.MediaType.VIDEO,
)

attribute_id = uuid.uuid4()
media_1.add_attribute(
    hari_uploader.HARIAttribute(
        id=attribute_id,
        name=f"media_attr_working",
        value="yes",
))
media_2.add_attribute(
    hari_uploader.HARIAttribute(
        id=attribute_id,
        name=f"media_attr_working",
        value="no",
))

# 4. Set up the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
)
uploader.add_media(media_1, media_2)

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
