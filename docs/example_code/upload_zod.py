import copy
import json
import os
import random
import time
import uuid

from qm_utils.filesystems import base_filesystem

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

s3_file_system = base_filesystem.S3FileSystem()


def get_s3_file_list_from_bucket(bucket_name: str, limit: int = 15000) -> list[str]:
    s3_files = []
    for idx, file in enumerate(s3_file_system.glob("s3://zod-external/*")):
        s3_files.append(str(file))
        if idx > limit:
            break
    return s3_files


def write_s3_file_list_to_file(bucket_name: str, s3_file_list: list[str]) -> None:
    with open("s3_file_list.json", "w") as f:
        json.dump(s3_file_list, f)


def load_s3_file_list_from_txt() -> list[str]:
    with open("s3_file_list.json", "r") as f:
        s3_file_list = json.load(f)
    return s3_file_list


def get_s3_file_list(limit: int = 15000) -> list[str]:
    if "s3_file_list.json" not in os.listdir():
        s3_file_list = get_s3_file_list_from_bucket("zod-external", limit)
        write_s3_file_list_to_file("zod-external", s3_file_list)
    else:
        s3_file_list = load_s3_file_list_from_txt()
    if len(s3_file_list) < limit:
        s3_file_list = get_s3_file_list_from_bucket("zod-external", limit)
        write_s3_file_list_to_file("zod-external", s3_file_list)
    return s3_file_list


s3_file_list = get_s3_file_list()


def generate_random_media_objects(number_of_objects: int) -> list[str]:
    media_objects = []
    scaling_factor = random.random() * 6
    for idx in range(round(number_of_objects / 2)):
        media_object = hari_uploader.HARIMediaObject(
            back_reference=f"pedestrian_{idx}",
            reference_data=models.BBox2DCenterPoint(
                type=models.BBox2DType.BBOX2D_CENTER_POINT,
                x=1400.0 + random.randint(0, 500),
                y=900.0 + random.randint(0, 500),
                width=20 * scaling_factor,
                height=120.0 * scaling_factor,
            ),
        )
        media_object.set_object_category_subset_name("pedestrian")
        media_objects.append(media_object)
    for idx in range(round(number_of_objects / 2)):
        media_object = hari_uploader.HARIMediaObject(
            back_reference=f"car_{idx}",
            reference_data=models.BBox2DCenterPoint(
                type=models.BBox2DType.BBOX2D_CENTER_POINT,
                x=1400.0 + random.randint(0, 600),
                y=900.0 + random.randint(0, 600),
                width=200 * scaling_factor,
                height=50 * scaling_factor,
            ),
        )
        media_object.set_object_category_subset_name("car")
        media_objects.append(media_object)

    return media_objects


media_objects = generate_random_media_objects(12)
attribute_media_id = uuid.uuid4()


def generate_medias(
    media_objects: list[hari_uploader.HARIMediaObject], s3_files_list: list[str]
) -> list[hari_uploader.HARIMedia]:
    medias = []
    for item in s3_files_list:
        media = hari_uploader.HARIMedia(
            file_key=item.split("/")[-1],
            name=item,
            back_reference=item,
            media_type=models.MediaType.IMAGE,
        )
        new_media_objects = copy.deepcopy(media_objects)
        attribute_media_1 = hari_uploader.HARIAttribute(
            id=attribute_media_id,
            name="weather_condition",
            value=random.choice(["sunny", "rainy", "cloudy", "snowy", "thunderstorm"]),
        )
        for media_object in new_media_objects:
            media.add_media_object(media_object)
        medias.append(media)
    return medias


medias = generate_medias(media_objects, s3_file_list)

config = Config()

# 1. Initialize the HARI client
hari = HARIClient(config=config)

# 2. Create a dataset
new_dataset = hari.create_dataset(
    name="performance_test_1",
    user_group="QM-ops",
    external_media_source=models.ExternalMediaSourceAPICreate(
        credentials=models.ExternalMediaSourceS3CrossAccountAccessInfo(
            bucket_name="zod-external", region="eu-central-1"
        )
    ),
)
print("Dataset created with id:", new_dataset.id)

dataset_id = new_dataset.id
start_time = time.time()
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    object_categories={"pedestrian", "car"},
)
uploader.add_media(*medias)

# 5. Trigger the upload process
upload_results = uploader.upload()
total_time = time.time() - start_time
print(f"Upload took {total_time} seconds")
print(uploader.client.timings)
# print average time per endpoint
average_client_times = {
    key: sum(endpoint_timing) / len(endpoint_timing)
    for key, endpoint_timing in uploader.client.timings.items()
}
print(f"Average time per endpoint: {average_client_times}")
# print total client time
total_client_time = sum(
    [sum(endpoint_timing) for endpoint_timing in uploader.client.timings.values()]
)
print(total_client_time)
print(
    f"Difference between total client time and total time: {total_time - total_client_time}"
)
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
