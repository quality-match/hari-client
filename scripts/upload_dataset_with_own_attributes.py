import argparse
import os
import random
import uuid
from os.path import join

import pandas as pd
from PIL import Image
from sklearn.utils import Bunch

import hari_client as hc
from hari_client import Config
from hari_client import HARIClient
from hari_client.utils.upload import check_and_upload_dataset
from hari_client.utils.upload import get_or_create_dataset


def load_data(root_directory, source_dataset_name: str):
    # This is the place where you need to specify the data, for the purpose of this example we will use random data

    # ----- Configuration -----
    num_images = 128
    categories = ["cat", "dog", "car"]  # Example class labels
    min_box_size = 20  # Minimal size of a bounding box in pixels
    dataset_folder = join(root_directory, source_dataset_name)

    # ----- Generate Dummy Images and Save Them -----

    # Ensure the dataset folder exists
    os.makedirs(dataset_folder, exist_ok=True)

    image_sizes = {}
    for i in range(1, num_images + 1):
        # Construct image path, e.g., "dummy_dataset/image_001.png"
        image_path = join(dataset_folder, f"image_{i:03d}.png")
        # Random image size (width and height between 200 and 800 pixels)
        width = random.randint(200, 800)
        height = random.randint(200, 800)
        image_sizes[str(image_path)] = (width, height)

        # Create a dummy image with a random background color
        img = Image.new(
            "RGB",
            (width, height),
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        )

        # Save the image to disk
        img.save(image_path)

    # ----- Generate Random Annotations with Bounding Boxes -----
    annotations = []
    for image_path_str, (width, height) in image_sizes.items():
        num_bboxes = random.randint(1, 3)
        for bbox_count in range(num_bboxes):
            # Generate a random bounding box within the image dimensions
            x1 = random.randint(0, width - min_box_size)
            y1 = random.randint(0, height - min_box_size)
            box_width = random.randint(min_box_size, width - x1)
            box_height = random.randint(min_box_size, height - y1)

            # Calculate the center
            x_center = x1 + box_width / 2
            y_center = y1 + box_height / 2
            norm_width = box_width
            norm_height = box_height
            bbox = [x_center, y_center, norm_width, norm_height]

            bbox_id = f"{image_path_str}+{bbox_count}"

            num_annotations = random.randint(5, 11)
            for _ in range(num_annotations):
                annotations.append(
                    {
                        "image_path": image_path_str,
                        "bbox_id": bbox_id,
                        "class_label": random.choice(categories),
                        "bbox": bbox,
                    }
                )

    # Create a DataFrame from the annotations
    df_answers = pd.DataFrame(annotations)

    # Create a pivot table counting how many times each class label appears per image
    df_answers_pivot = (
        df_answers.groupby(["bbox_id", "class_label"])
        .size()  # count rows in each group
        .unstack(fill_value=0)
    )

    # Build a dictionary mapping image paths to frequency dictionaries
    answer_frequencies = {
        bbox_id: dict(freq)
        for bbox_id, freq in df_answers_pivot.to_dict(orient="index").items()
    }

    # Determine the majority vote for each image (the class with the highest count)
    majority_votes = {
        bbox_id: (max(freq, key=freq.get) if max(freq.values()) > 0 else None)
        for bbox_id, freq in df_answers_pivot.to_dict(orient="index").items()
    }

    # Bundle everything into a simple namespace (Bunch)
    data = Bunch(
        categories=categories,
        image_sizes=image_sizes,
        frequencies=answer_frequencies,
        majority_votes=majority_votes,
        annotations=annotations,
    )

    return data


def upload_dataset_with_own_attributes(
    hari: hc.HARIClient,
    root_directory,
    source_dataset_name: str,
    target_dataset_name: str,
    question: str,
    attribute_name: str,
    user_group,
    is_anonymized,
) -> None:
    # create dataset
    dataset_name: str = (
        target_dataset_name if target_dataset_name is not None else source_dataset_name
    )
    dataset_id = get_or_create_dataset(hari, dataset_name, user_group, is_anonymized)

    # load actual data for upload
    data = load_data(root_directory, source_dataset_name)

    medias = {
        image_path: hc.hari_uploader.HARIMedia(
            file_path=image_path,
            name=image_path,
            back_reference=image_path,
            media_type=hc.models.MediaType.IMAGE,
        )
        for image_path in data.image_sizes
    }

    # We also assign annotation results to an attribute

    annotatable_attribute = dict(
        id=str(uuid.uuid4()),
        name=attribute_name,
        attribute_group=hc.models.AttributeGroup.AnnotationAttribute,
        attribute_type=hc.models.AttributeType.Categorical,
        question=question,
        possible_values=data.categories,
    )

    # calculate average number of annotations to be defined as target value of repeats
    # This is important for AINT execution
    number_annotations = [
        sum(data.frequencies.get(bbox_id).values()) for bbox_id in data.frequencies
    ]
    avg_number_annotions = int(round(sum(number_annotations) / len(number_annotations)))

    media_objects = {}
    for anno in data.annotations:
        image_path = anno["image_path"]
        bbox_id = anno["bbox_id"]
        class_label = anno["class_label"]
        bbox = anno["bbox"]
        x_center, y_center, width, height = bbox

        media = medias[image_path]

        # width, height = data.image_sizes.get(image_path)
        frequency = data.frequencies.get(bbox_id)
        majority_vote = data.majority_votes.get(bbox_id)

        if bbox_id not in media_objects:
            media_object = hc.hari_uploader.HARIMediaObject(
                back_reference=bbox_id,
                reference_data=hc.models.BBox2DCenterPoint(
                    type=hc.models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=x_center,
                    y=y_center,
                    width=width,
                    height=height,
                ),
            )
            media_objects[bbox_id] = media_object
            media.add_media_object(media_object)

            attribute = hc.hari_uploader.HARIAttribute(
                value=majority_vote,
                frequency=frequency,
                cant_solves=0,
                repeats=avg_number_annotions,
                **annotatable_attribute,
            )
            media_object.add_attribute(attribute)
            media_object.set_object_category_subset_name(majority_vote)

    check_and_upload_dataset(
        hari, dataset_id, data.categories, medias=list(medias.values())
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a dataset with an annotation attribute in HARI. This scripts assumes as dataformat the Data-Centric Image Classification (DCIC) Benchmark format. For more details see https://zenodo.org/records/8115942"
    )

    parser.add_argument(
        "--root_directory",
        type=str,
        help="Root directory of dataset",
        required=True,
    )

    parser.add_argument(
        "-s",
        "--source_dataset_name",
        type=str,
        help="Source folder name of the dataset to be uploaded.",
        required=True,
    )

    parser.add_argument(
        "-t",
        "--target_dataset_name",
        type=str,
        help="Target dataset name as it should appear in HARI.",
        default=None,
    )

    parser.add_argument(
        "-q",
        "--question",
        type=str,
        help="Annotation question asked to create the results.",
        required=True,
    )

    parser.add_argument(
        "-n",
        "--attribute_name",
        type=str,
        help="Name of the annotation attribute.",
        required=True,
    )

    parser.add_argument(
        "--user_group",
        type=str,
        help="User group for the upload",
        required=True,
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    root_directory = args.root_directory
    source_dataset_name = args.source_dataset_name
    target_dataset_name = args.target_dataset_name
    question = args.question
    attribute_name = args.attribute_name
    user_group = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    # Make sure that your data is anonymized before you mark it as such
    # If your data is not anonymized please contact us for further support.
    upload_dataset_with_own_attributes(
        hari,
        root_directory,
        source_dataset_name,
        target_dataset_name,
        question,
        attribute_name,
        user_group=user_group,
        is_anonymized=True,
    )
