# This script was written with hari-client version 2.0.3
import json
import sys
import time
import uuid

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

# Set the dataset_id here
dataset_id = uuid.UUID("YOUR_DATASET_ID")

config = Config()
hari = HARIClient(config=config)

# Check whether the dataset exists (exception raised if it's not found)
print(f"Fetching dataset {dataset_id}")
dataset = hari.get_dataset(dataset_id=dataset_id)

# 1.
# Fetch the existing initial attributes
# Why? --> attribute with the same names should reuse the same ids
initial_attributes = hari.get_attributes(
    dataset_id=dataset_id,
    archived=False,
    query=json.dumps(
        {
            "attribute": "attribute_group",
            "query_operator": "==",
            "value": models.AttributeGroup.InitialAttribute,
        }
    ),
    projection={
        "name": True,
        "id": True,
        "annotatable_type": True,
    },
)

# Build look up tables for the initial attributes.
# It's intended by HARI that attributes with the same name should reuse the same id.
# In case an attribute name is used for medias and media objects, the attribute id used
# for the medias has to be different from the one used for the media objects.
media_attribute_id_lookup: dict[str, uuid.UUID] = {}
media_attribute_lookup: dict[str, models.AttributeResponse] = {}
media_object_attribute_id_lookup: dict[str, uuid.UUID] = {}
media_object_attribute_lookup: dict[str, models.AttributeResponse] = {}
for attribute in initial_attributes:
    if attribute.annotatable_type == models.DataBaseObjectType.MEDIA:
        if attribute.name not in media_attribute_id_lookup:
            media_attribute_id_lookup[attribute.name] = attribute.id
            media_attribute_lookup[attribute.name] = attribute
    elif attribute.annotatable_type == models.DataBaseObjectType.MEDIAOBJECT:
        if attribute.name not in media_object_attribute_id_lookup:
            media_object_attribute_id_lookup[attribute.name] = attribute.id
            media_object_attribute_lookup[attribute.name] = attribute

print(
    "Found attributes:\n"
    f"  media_attribute_ids: {len(media_attribute_id_lookup)}\n"
    f"  media_object_attribute_ids: {len(media_object_attribute_id_lookup)}"
)

# 2. Set up new medias, media objects and attributes
# Just as an example: 1 new media with one 2dbbox and some attributes
new_media = hari_uploader.HARIMedia(
    file_path="../images/image_1.jpg",
    name="new image 1",
    back_reference="new image 1",
    media_type=models.MediaType.IMAGE,
)
new_media_object = hari_uploader.HARIMediaObject(
    back_reference="new media object 1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1000,
        y=1000,
        width=200,
        height=400,
    ),
)
new_media.add_media_object(new_media_object)

# Double check whether you're accidentally uploading duplicate data by checking back_references
duplicate_medias = hari.get_medias(
    dataset_id=dataset_id,
    query=json.dumps(
        {
            "attribute": "back_reference",
            "query_operator": "in",
            # add all back_references here that you're going to upload here
            "value": [new_media.back_reference],
        }
    ),
)
if len(duplicate_medias) > 0:
    duplicate_back_references = [media.back_reference for media in duplicate_medias]
    print(
        f"Stopping upload. Found {len(duplicate_medias)} duplicate medias with these back_references:"
    )
    for back_reference in duplicate_back_references:
        print(f"  {back_reference}")
    sys.exit(1)
duplicate_media_objects = hari.get_media_objects(
    dataset_id=dataset_id,
    query=json.dumps(
        {
            "attribute": "back_reference",
            "query_operator": "in",
            # add all back_references here that you're going to upload here
            "value": [new_media_object.back_reference],
        }
    ),
)
if len(duplicate_media_objects) > 0:
    duplicate_back_references = [
        media_object.back_reference for media_object in duplicate_media_objects
    ]
    print(
        f"Stopping upload. Found {len(duplicate_medias)} duplicate media_objects with these back_references:"
    )
    for back_reference in duplicate_back_references:
        print(f"  {back_reference}")
    sys.exit(1)


# The hari_uploader utility will take care of syncing with the backend to choose the correct object category subset
# if it already exists. If it doesn't exist, it will be created.
new_media_object.set_object_category_subset_name("my_new_object_category")
object_categories = {"my_new_object_category"}

# add an already known initial attribute to the media and media object, and one new attribute to each
# in the example case we know that the existing media attribute value type is number
new_media.add_attribute(
    hari_uploader.HARIAttribute(
        id=list(media_attribute_id_lookup.values())[0],
        name=list(media_attribute_id_lookup.keys())[0],
        attribute_type=list(media_attribute_lookup.values())[0].attribute_type,
        value=500,
    )
)
# the new attribute needs a new id
# remember the new attribute id for potential later reuse
media_attribute_id_lookup["new_media_attribute"] = uuid.uuid4()
new_media_attribute = hari_uploader.HARIAttribute(
    id=media_attribute_id_lookup["new_media_attribute"],
    name="new_media_attribute",
    value="hello_world",
)
new_media.add_attribute(new_media_attribute)

# add attributes to the media object
# in the example case we know that the existing media object attribute value type is boolean
new_media_object.add_attribute(
    hari_uploader.HARIAttribute(
        id=list(media_object_attribute_id_lookup.values())[0],
        name=list(media_object_attribute_id_lookup.keys())[0],
        attribute_type=list(media_object_attribute_lookup.values())[0].attribute_type,
        value=True,
    )
)
# the new attribute needs a new id
# remember the new attribute id for potential later reuse
media_object_attribute_id_lookup["new_media_object_attribute"] = uuid.uuid4()
new_media_object_attribute = hari_uploader.HARIAttribute(
    id=media_object_attribute_id_lookup["new_media_object_attribute"],
    name="new_media_object_attribute",
    value=42,
)
new_media_object.add_attribute(new_media_object_attribute)

# 3. Set existing subset_id on the new media and media object
# In the example case we know there's a subset called "All media objects" (see quickstart.py).
# We have to add its subset_id to the new media and the new media object.
all_dataset_subsets = hari.get_subsets_for_dataset(dataset_id=dataset_id)
all_media_objects_subset = list(
    filter(lambda x: x.name == "All media objects", all_dataset_subsets)
)
if len(all_media_objects_subset) == 1:
    subset_id = all_media_objects_subset[0].id
    # because we created the new media and media object from scratch, we know there are no subset_ids set on them yet.
    new_media.subset_ids = [subset_id]
    new_media_object.subset_ids = [subset_id]

# 4. Set up new empty subsets for the medias and media objects that we're going to upload
# Note: This step is the first time in this script that you add sth. to the dataset in HARI!
new_media_subset_id = hari.create_empty_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA,
    subset_name="my_new_medias_subset",
)
new_media_object_subset_id = hari.create_empty_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="my_new_media_objects_subset",
)
# assign the new subset ids to the new media and media object
new_media.subset_ids = new_media.subset_ids + [
    uuid.UUID(new_media_subset_id),
    uuid.UUID(new_media_object_subset_id),
]
new_media_object.subset_ids.append(uuid.UUID(new_media_object_subset_id))

# 5. Set up hari_uploader and trigger upload
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    object_categories=object_categories,
)
uploader.add_media(new_media)

# Note: This step actually uploads the new data to the dataset in HARI!
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
        "The data upload wasn't fully successful. Metadata rebuild is skipped. See the details below."
    )
    print(f"media upload details: {upload_results.medias.results}")
    print(f"media objects upload details: {upload_results.media_objects.results}")
    print(f"attributes upload details: {upload_results.attributes.results}")
    sys.exit(1)

# 6. Trigger metadata rebuild and wait for that to finish
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
