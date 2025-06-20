import argparse
import time
import uuid

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.models.models import BulkAttributeCreate

config = Config()
hari = HARIClient(config=config)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",
    "--dataset_id",
    type=uuid.UUID,
    help="Dataset ID to work on.",
    required=True,
)

args = parser.parse_args()

dataset_id = args.dataset_id

# 4. Set up the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    object_categories={"pedestrian", "wheel", "road_marking"},
)

all_media = hari.get_medias(dataset_id=dataset_id)
all_media_objects = hari.get_media_objects_paginated(dataset_id=dataset_id)


attrs = []
attr_id = uuid.uuid4()
for media in all_media[:1000]:
    for i in range(1):
        attr = BulkAttributeCreate(
            id=attr_id,
            annotatable_id=media.id,
            annotatable_type="Media",
            attribute_type=models.AttributeType.Binary,
            name=f"weather_condition",
            value="sunny",
        )
        attrs.append(attr)

attr_id2 = uuid.uuid4()
for media_object in all_media_objects[:1000]:
    for i in range(1):
        attr = BulkAttributeCreate(
            id=attr_id2,
            annotatable_id=media_object.id,
            annotatable_type="MediaObject",
            attribute_type=models.AttributeType.Binary,
            name=f"weather_condition",
            value="sunny",
        )
        attrs.append(attr)

now = time.time()
hari.create_attributes(dataset_id=dataset_id, attributes=attrs)
print(f"Time to create {len(attrs)} media attrs: {time.time()-now}")
print(f"average time to create one media attrs: {(time.time()-now)/len(attrs)}")
