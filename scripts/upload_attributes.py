import uuid

import numpy as np
import pandas as pd
from tqdm import tqdm

from hari_client import Config
from hari_client import HARIClient
from hari_client import models
from hari_client.client.errors import APIError
from hari_client.models.models import AttributeCreate
from hari_client.models.models import DataBaseObjectType
from hari_client.utils.upload import check_and_create_subset_for_all
from hari_client.utils.upload import trigger_and_display_metadata_update

DATASET_ID = uuid.UUID("ca5870ff-17bc-4ed1-bf1e-f86283c6341e")  # kitti
labels = [
    "close_to_road",
    "crossing",
    "waiting_to_cross",
    "no_interfering_pedestrian",
    "cant_solve",
]
question = "Can you see any pedestrian that is relevant for your driving behavior?"
AINT_NAME = "AINT - Relevant Pedestrian"

data_split_labels = ["none", "train", "val", "test"]

BATCH_SIZE = 500

REPEATS = 1000

CSV_FILE = f"./predictions-{DATASET_ID}_turn_left.csv"

if __name__ == "__main__":
    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # load data -> extract annotatable_id to soft labe
    df = pd.read_csv(CSV_FILE)  # replace with your actual file path

    # Convert to desired format
    annotatable_id_to_soft_label = {
        row["image_object_id"]: (
            row["confidence_score"],
            [row[f"{lab}_prob"] for lab in labels],
            row["split"],
        )
        for _, row in df.iterrows()
    }

    # annotatable_id_to_soft_label = {
    #     '44f5d9c8-77b4-48ee-8a42-27050d219281':(0.89, [0.1, 0.2, 0.6, 0.0, 0.1]),
    #     '08448c93-ab7b-4371-a082-17ca19343799':(0.23, [0.6, 0.3, 0.1, 0.0, 0.0]),
    # }

    attribute_uuid = uuid.uuid4()
    data_split_uuid = uuid.uuid4()

    # iterate over all items and upload
    attributes = []
    for anno_id, (
        confidence,
        soft_label,
        data_split,
    ) in annotatable_id_to_soft_label.items():
        assert len(soft_label) == len(labels)

        fake_frequency = [int(prob * REPEATS) for prob in soft_label]

        max_arg = np.argmax(fake_frequency)  # TODo not optimal if multiple highest
        max_value = labels[max_arg]

        # print(confidence, soft_label, fake_frequency, max_value)

        # Add ml attribute
        att = AttributeCreate(
            id=str(attribute_uuid),
            annotatable_id=anno_id,
            annotatable_type=DataBaseObjectType.MEDIA,
            name=AINT_NAME,
            attribute_group=models.AttributeGroup.MlAnnotationAttribute,
            attribute_type=models.AttributeType.Categorical,
            question=question,
            possible_values=labels,
            value=max_value,
            ambiguity=confidence,
            frequency=dict(zip(labels, fake_frequency)),
        )

        attributes.append(att)  # already uploaded

        # add init datasplit attribute
        att = AttributeCreate(
            id=str(data_split_uuid),
            annotatable_id=anno_id,
            annotatable_type=DataBaseObjectType.MEDIA,
            name=f"init_data_split-{AINT_NAME}",
            attribute_group=models.AttributeGroup.InitialAttribute,
            attribute_type=models.AttributeType.Categorical,
            possible_values=data_split_labels,
            value=data_split,
        )

        attributes.append(att)

    # batching of upload
    print("Uploading aints")
    for idx in tqdm(range(0, len(attributes), BATCH_SIZE)):
        attributes_to_upload = attributes[idx : idx + BATCH_SIZE]
        try:
            response = hari.create_attributes(
                dataset_id=DATASET_ID, attributes=attributes_to_upload
            )
        except APIError as e:
            print(e)

    new_subset_id, reused = check_and_create_subset_for_all(
        hari, DATASET_ID, AINT_NAME, models.SubsetType.MEDIA
    )

    if reused:
        print(
            "WARNING: You did not create a new subset since the name already exists. "
            "If you added new images during upload the metadata update will be skipped for the new images. "
            "If you added new images please provide a new subset name or delete the old one."
        )

    # Trigger metadata updates
    trigger_and_display_metadata_update(
        hari, dataset_id=DATASET_ID, subset_id=new_subset_id
    )
