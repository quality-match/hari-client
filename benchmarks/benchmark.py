import copy
import datetime
import json
import os
import pathlib
import random
import time
import uuid

import network_monitor
from qm_utils.filesystems import base_filesystem

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

user_results_dir = pathlib.Path(__file__).parent / "user_results"
user_results_dir.mkdir(exist_ok=True)
results_dir = pathlib.Path(__file__).parent / "results"


def get_latest_benchmark_file(results_dir: pathlib.Path) -> pathlib.Path | None:
    json_file_paths = sorted(
        results_dir.glob("benchmark_result_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return json_file_paths[0] if json_file_paths else None


REUSE_SAME_MEDIA_BINARY = False
NUM_MEDIAS = 15000
NUM_MEDIA_OBJECTS_BY_MEDIA = 10
NUM_ATTRIBUTES_BY_MEDIA = 5
NUM_ATTRIBUTES_BY_MEDIA_OBJECT = 5
REUSE_PREVIOUS_CONFIGURATION = False

if REUSE_PREVIOUS_CONFIGURATION:
    latest_benchmark_file_path = get_latest_benchmark_file(results_dir)
    if latest_benchmark_file_path:
        with open(latest_benchmark_file_path, "r") as f:
            benchmark_result = json.load(f)
        NUM_MEDIAS = benchmark_result["config"]["NUM_MEDIAS"]
        NUM_MEDIA_OBJECTS_BY_MEDIA = benchmark_result["config"][
            "NUM_MEDIA_OBJECTS_BY_MEDIA"
        ]
        NUM_ATTRIBUTES_BY_MEDIA = benchmark_result["config"]["NUM_ATTRIBUTES_BY_MEDIA"]
        NUM_ATTRIBUTES_BY_MEDIA_OBJECT = benchmark_result["config"][
            "NUM_ATTRIBUTES_BY_MEDIA_OBJECT"
        ]
        REUSE_SAME_MEDIA_BINARY = benchmark_result["config"]["REUSE_SAME_MEDIA_BINARY"]


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


def generate_random_media_objects(number_of_objects: int) -> list[str]:
    media_objects = []
    scaling_factor = random.random() * 6
    for idx in range(number_of_objects):
        if idx % 2 == 0:
            media_object = hari_uploader.HARIMediaObject(
                back_reference=f"pedestrian_{idx}",
                reference_data=models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1.0 + random.randint(0, 1),
                    y=1.0 + random.randint(0, 1),
                    width=1 * scaling_factor,
                    height=1.0 * scaling_factor,
                ),
            )
            media_object.set_object_category_subset_name("pedestrian")
        else:
            media_object = hari_uploader.HARIMediaObject(
                back_reference=f"car_{idx}",
                reference_data=models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1.0 + random.randint(0, 1),
                    y=1.0 + random.randint(0, 1),
                    width=1 * scaling_factor,
                    height=1 * scaling_factor,
                ),
            )
            media_object.set_object_category_subset_name("car")
        media_objects.append(media_object)

    # generate 100 different attributes
    attr_ids = [uuid.uuid4() for _ in range(100)]
    names = [f"media_object_attribute_{i}" for i in range(100)]
    attr_ids_vs_names = [(_id, name) for _id, name in zip(attr_ids, names)]
    attributes = [
        hari_uploader.HARIAttribute(
            id=_id,
            name=name,
            value=random.randint(0, 100),
            annotatable_type=models.DataBaseObjectType.MEDIAOBJECT,
        )
        for _id, name in attr_ids_vs_names
    ]

    for media_object in media_objects:
        for attr in random.sample(attributes, NUM_ATTRIBUTES_BY_MEDIA_OBJECT):
            media_object.add_attribute(attr)

    return media_objects


def generate_medias(
    media_objects: list[hari_uploader.HARIMediaObject],
    s3_files_list: list[str],
    limit: int | None = None,
) -> list[hari_uploader.HARIMedia]:
    medias = []
    attr_ids = [uuid.uuid4() for _ in range(100)]
    names = [f"media_attribute_{i}" for i in range(100)]
    attr_ids_vs_names = [(_id, name) for _id, name in zip(attr_ids, names)]
    attributes = [
        hari_uploader.HARIAttribute(
            id=_id,
            name=name,
            value=random.randint(0, 100),
            annotatable_type=models.DataBaseObjectType.MEDIA,
        )
        for _id, name in attr_ids_vs_names
    ]
    for idx, item in enumerate(s3_files_list):
        media = hari_uploader.HARIMedia(
            file_key=item.split("/")[-1],
            file_path=str(
                (
                    pathlib.Path(__file__).parent.parent
                    / "docs/example_code/2694ea70-9b4e-47c0-8e85-b3c18050be2b/anonymized/2694ea70-9b4e-47c0-8e85-b3c18050be2b_0a0a600c-5410-42b3-b77a-9a2cf772716f.jpg"
                ).absolute()
            ),
            # file_path=item,
            name=str(idx),
            back_reference=str(idx),
            media_type=models.MediaType.IMAGE,
        )
        new_media_objects = copy.deepcopy(media_objects)
        for media_object in new_media_objects:
            media.add_media_object(media_object)

        # generate 100 different attributes

        for attr in random.sample(attributes, NUM_ATTRIBUTES_BY_MEDIA):
            media.add_attribute(attr)
        medias.append(media)
        if limit and idx >= limit - 1:
            break
    return medias


s3_file_list = get_s3_file_list()
if REUSE_SAME_MEDIA_BINARY:
    s3_file_key = s3_file_list[0].split("/")[-1]
    s3_file_list = [s3_file_key for _ in range(len(s3_file_list))]
else:
    s3_file_list = [item.split("/")[-1] for item in s3_file_list]
s3_file_list = s3_file_list[:NUM_MEDIAS]


media_objects = generate_random_media_objects(NUM_MEDIA_OBJECTS_BY_MEDIA)
medias = generate_medias(media_objects, s3_file_list, 15000)
# files = []
# s3_file_list = []
# for file in (pathlib.Path(__file__).parent / "images").iterdir():
#     s3_file_list.append(str(file.absolute()))
# s3_file_list = s3_file_list[:NUM_MEDIAS]
# medias = generate_medias(media_objects, s3_file_list, 5000)

config = Config()

# 1. Initialize the HARI client
hari = HARIClient(config=config)

# 2. Create a dataset
new_dataset = hari.create_dataset(
    name="final_test",
    user_group="QM-ops",
    external_media_source=models.ExternalMediaSourceAPICreate(
        credentials=models.ExternalMediaSourceS3CrossAccountAccessInfo(
            bucket_name="zod-external", region="eu-central-1"
        )
    ),
)
dataset_id = new_dataset.id
print(dataset_id)
start_time = time.time()
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    object_categories={"pedestrian", "car"},
)
uploader.add_media(*medias)
monitor = network_monitor.NetworkMonitor(interval=1)
monitor.start()
# 5. Trigger the upload process
upload_results = uploader.upload()
monitor.stop()
avg_upload_speed = monitor.get_average_upload_speed()
avg_download_speed = monitor.get_average_download_speed()

total_time = time.time() - start_time
average_client_times = {
    key: sum(endpoint_timing) / len(endpoint_timing)
    for key, endpoint_timing in uploader.client.timings.items()
}
total_client_time = sum(
    [sum(endpoint_timing) for endpoint_timing in uploader.client.timings.values()]
)
time_per_media = sum(
    uploader.client.timings[f"POST /datasets/{dataset_id}/medias:bulk"]
) / len(medias)
time_per_media_object = sum(
    uploader.client.timings[f"POST /datasets/{dataset_id}/mediaObjects:bulk"]
) / (len(media_objects) * len(medias))
time_per_attribute = sum(
    uploader.client.timings[f"POST /datasets/{dataset_id}/attributes:bulk"]
) / (
    len(media_objects) * NUM_ATTRIBUTES_BY_MEDIA_OBJECT
    + len(medias * NUM_ATTRIBUTES_BY_MEDIA)
)

benchmark_results = {
    "config": {
        "REUSE_SAME_MEDIA_BINARY": True,
        "NUM_MEDIAS": NUM_MEDIAS,
        "NUM_MEDIA_OBJECTS_BY_MEDIA": NUM_MEDIA_OBJECTS_BY_MEDIA,
        "NUM_ATTRIBUTES_BY_MEDIA": NUM_ATTRIBUTES_BY_MEDIA,
        "NUM_ATTRIBUTES_BY_MEDIA_OBJECT": NUM_ATTRIBUTES_BY_MEDIA_OBJECT,
    },
    "network": {
        "average_upload_speed_in_byte_per_s": avg_upload_speed,
        "average_download_speed_in_byte_per_s": avg_download_speed,
    },
    "upload_results": {
        "medias": str(upload_results.medias.summary),
        "media_objects": str(upload_results.media_objects.summary),
        "attributes": str(upload_results.attributes.summary),
    },
    "dataset_id": str(dataset_id),
    "Total upload time": total_time,
    "Average time per endpoint": average_client_times,
    "Timer per media": time_per_media,
    "Timer per media object": time_per_media_object,
    "Timer per attribute": time_per_attribute,
    "endpoint_timings": uploader.client.timings,
    "upload_failures": str(upload_results.failures),
    "upload_results_attributes": str(
        upload_results.attributes.results
    ),  # because failures don't include failed attrs yet
}
print(json.dumps(benchmark_results, indent=2))
with open(
    user_results_dir
    / f"benchmark_result_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json",
    "w+",
) as f:
    json.dump(benchmark_results, f)
