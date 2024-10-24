import sys
import time
import uuid
from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

# This test should upload a specified amount of media and objects with initial attributes.
n_media = 20  # Number of unique media to upload
rep_media = 10  # Number of times each media is repeated
n_objects = 4  # Number of objects per media

# The Config class will look for a .env file in your script's current working directory.
# Copy the .env_example file as .env for that and store your HARI credentials in there.
config = Config()

# 1. Initialize the HARI client
hari = HARIClient(config=config)

# 2. Create a dataset
new_dataset = hari.create_dataset(name="qa_client", user_group="QA-devs")
print("Dataset created with id:", new_dataset.id)

dataset_id = new_dataset.id

# 3. Set up your medias and all of their media objects and attributes.
media_list = []

object_categories = {"cat_1", "cat_2", "cat_3", "cat_4"}

for i in range(rep_media):
    for j in range(n_media):
        media_list.append(
            hari_uploader.HARIMedia(
                file_path=f"images/ecp{j+1}.png",
                name=f"camera_{j+1}",
                back_reference=f"image{i*n_media+j+1}",
                media_type=models.MediaType.IMAGE,
            )
        )

attribute_media_1_id = str(uuid.uuid4())
attribute_object_1_id = str(uuid.uuid4())

for i in range(n_media * rep_media):
    cur_obj_cat = list(object_categories)[i % len(object_categories)]
    object1 = hari_uploader.HARIMediaObject(
        back_reference=f"object_{i*n_objects+1}",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=200.0,
            y=206.0,
            width=84.0,
            height=62.0,
        ),
    )
    object1.add_attribute(
        hari_uploader.HARIAttribute(
            id=attribute_object_1_id,
            name="initObjectAttribute",
            attribute_type=models.AttributeType.Binary,
            value=False,
        )
    )

    media_list[i].add_media_object(object1)

    object2 = hari_uploader.HARIMediaObject(
        back_reference=f"object_{i*n_objects+2}",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=500.0,
            y=906.0,
            width=84.0,
            height=62.0,
        ),
    )

    object2.add_attribute(
        hari_uploader.HARIAttribute(
            id=attribute_object_1_id,
            name="initObjectAttribute",
            attribute_type=models.AttributeType.Binary,
            value=True,
        )
    )
    media_list[i].add_media_object(object2)

    object3 = hari_uploader.HARIMediaObject(
        back_reference=f"object_{i*n_objects+3}",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=700.0,
            y=906.0,
            width=84.0,
            height=62.0,
        ),
    )
    object3.add_attribute(
        hari_uploader.HARIAttribute(
            id=attribute_object_1_id,
            name="initObjectAttribute",
            attribute_type=models.AttributeType.Binary,
            value=True,
        )
    )

    media_list[i].add_media_object(object3)

    object4 = hari_uploader.HARIMediaObject(
        back_reference=f"object_{i*n_objects+4}",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=500.0,
            y=806.0,
            width=84.0,
            height=62.0,
        ),
    )
    object4.add_attribute(
        hari_uploader.HARIAttribute(
            id=attribute_object_1_id,
            name="initObjectAttribute",
            attribute_type=models.AttributeType.Binary,
            value=False,
        )
    )

    media_list[i].add_media_object(object4)

    media_list[i].add_attribute(
        hari_uploader.HARIAttribute(
            id=attribute_media_1_id,
            name="initMediaAttribute",
            attribute_type=models.AttributeType.Binary,
            value=True,
        )
    )
    object1.set_object_category_subset_name(cur_obj_cat)
    object2.set_object_category_subset_name(cur_obj_cat)
    object3.set_object_category_subset_name(cur_obj_cat)
    object4.set_object_category_subset_name(cur_obj_cat)


# Function to handle the upload process
def upload_media(media_chunk):
    uploader = hari_uploader.HARIUploader(
        client=hari, dataset_id=dataset_id, object_categories=object_categories
    )
    uploader.add_media(*media_chunk)
    return uploader.upload()


# Split media_list into 10 chunks
media_chunks = [media_list[i::10] for i in range(10)]

# Use ThreadPoolExecutor to parallelize the upload process
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(upload_media, chunk) for chunk in media_chunks]
    for future in as_completed(futures):
        upload_results = future.result()
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
            print(
                f"media objects upload details: {upload_results.media_objects.results}"
            )
            print(f"attributes upload details: {upload_results.attributes.results}")
            sys.exit(1)

# 6. Create a subset
print("Creating new subset...")
new_subset_id = hari.create_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="All media objects",
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
