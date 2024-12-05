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
# new_dataset = hari.create_dataset(name="BB_upload_ann_attributes", user_group="QM-ops")
# print("Dataset created with id:", new_dataset.id)

dataset_id = "2d90a495-8aa4-4176-bc71-5279129dd84c"

# 3. Set up your medias and all of their media objects and attributes.
# In this example we use 3 images with 1 media object each.
# The first media and media object have 1 attribute each.
media_1 = hari_uploader.HARIMedia(
    # note: the file_path won't be saved in HARI, it's only used during uploading
    file_path="/Users/benjaminbentner/repos/hari-client/docs/example_code/images/image_3.jpg",
    name="A busy street 3",
    back_reference="image 3",
    media_type=models.MediaType.IMAGE,
)
media_object_1 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1400.0,
        y=1806.0,
        width=344.0,
        height=732.0,
    ),
)

media_object_2 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_2",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1300.0,
        y=1806.0,
        width=344.0,
        height=732.0,
    ),
)

annotation_attribute_id = uuid.uuid4()
print(annotation_attribute_id)

attribute_object_1 = hari_uploader.HARIAttribute(
    id=annotation_attribute_id,
    name="human being uploaded attribute categorical?",
    attribute_type=models.AttributeType.Categorical,
    attribute_group=models.AttributeGroup.AnnotationAttribute,
    value="oneormore",
    repeats=1,
    possible_values=["one/zero", "two", "three"],
    frequency={"one/zero": 1, "two": 5},
    cant_solves=0,

)
media_object_1.add_attribute(attribute_object_1)
media_1.add_media_object(media_object_1)

attribute_object_2 = hari_uploader.HARIAttribute(
    id=annotation_attribute_id,
    name="human being uploaded attribute categorical?",
    attribute_type=models.AttributeType.Categorical,
    attribute_group=models.AttributeGroup.AnnotationAttribute,
    value="one",
    repeats=1,
    possible_values=["one/zero", "two", "three"],
    frequency={"one/zero": 100, "two": 0, "three": 0, "four": 0},
    cant_solves=0,

)

media_object_2.add_attribute(attribute_object_2)
media_1.add_media_object(media_object_2)

# 4. Set up the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
)
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
# print("Creating new subset...")
# new_subset_id = hari.create_subset(
#     dataset_id=dataset_id,
#     subset_type=models.SubsetType.MEDIA_OBJECT,
#     subset_name="All media objects new",
# )
# print(f"Created new subset with id {new_subset_id}")

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
