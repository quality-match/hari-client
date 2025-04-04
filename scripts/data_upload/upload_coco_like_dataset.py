import argparse
import json
import uuid

import pandas as pd
from sklearn.utils import Bunch

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.utils.upload import check_and_upload_dataset
from hari_client.utils.upload import get_or_create_dataset


def load_data(filename: str):
    # `filename`: json file containing instance annotations

    with open(filename, "r") as fp:
        instances = json.load(fp)

    df_images = pd.DataFrame(instances["images"]).set_index("id", drop=True)

    df_categories = (
        pd.DataFrame(instances["categories"])
        .set_index("id", drop=True)
        .rename(columns={"name": "category"})
    )

    supercategories = df_categories.supercategory.unique().tolist()
    categories = df_categories.category.to_list()

    df_annotations = (
        pd.DataFrame(instances["annotations"])
        .set_index("id", drop=True)
        .join(df_categories, on="category_id")
        .drop(columns=["segmentation", "category_id"])
        .assign(iscrowd=lambda df: df.iscrowd.astype(bool))
    )

    # Transform COCO [left, top, width, height]
    #   to QM Brain's [center_x, center_y, width, height]
    df_boxes = pd.json_normalize(
        df_annotations.bbox.map(
            lambda r: {
                "x": r[0] + r[2] / 2,
                "y": r[1] + r[3] / 2,
                "width": r[2],
                "height": r[3],
            }
        )
    ).set_index(df_annotations.index)

    df_annotations = df_annotations.join(df_boxes).drop(columns=["bbox"])

    return Bunch(
        categories=categories,
        supercategories=supercategories,
        df=Bunch(images=df_images, annotations=df_annotations),
    )


def upload_coco_like_dataset(
    hari, dataset_name, images_dir, annotations_file, user_group, is_anonymized
):
    dataset_id = get_or_create_dataset(
        hari, dataset_name, user_group, is_anonymized=is_anonymized
    )

    # We create identities for the attributes that we
    #   want to assign to the objects

    attributes = [
        (name, str(uuid.uuid4()), atype)
        for name, atype in zip(
            ["category", "supercategory", "iscrowd"],
            [
                models.AttributeType.Categorical,
                models.AttributeType.Categorical,
                models.AttributeType.Binary,
            ],
        )
    ]

    data = load_data(filename=annotations_file)

    medias = {
        idx: hari_uploader.HARIMedia(
            file_path=image_info["file_name"],
            name=image_info["file_name"],
            back_reference=image_info["coco_url"],
            media_type=models.MediaType.IMAGE,
        )
        for idx, image_info in (
            data.df.images.assign(file_name=lambda df: f"{images_dir}/" + df.file_name)
            .pipe(lambda df: df[["file_name", "coco_url"]])
            .to_dict(orient="index")
        ).items()
    }

    for object_idx, record in data.df.annotations.iterrows():
        media_object = hari_uploader.HARIMediaObject(
            back_reference=f"{object_idx}",
            reference_data=models.BBox2DCenterPoint(
                type=models.BBox2DType.BBOX2D_CENTER_POINT,
                x=record.x,
                y=record.y,
                width=record.width,
                height=record.height,
            ),
        )
        # Set category to enable creation of subsets
        # Here: the supercategory is used for subset creation
        media_object.set_object_category_subset_name(record.supercategory)
        # Add media object to the media it belongs to
        medias[record.image_id].add_media_object(media_object)

        # Add attributes
        for attr_name, attr_id, attr_type in attributes:
            media_object.add_attribute(
                hari_uploader.HARIAttribute(
                    id=attr_id,
                    name=attr_name,
                    attribute_type=attr_type,
                    value=record[attr_name],
                )
            )

    check_and_upload_dataset(
        hari,
        dataset_id,
        object_categories=set(data.supercategories),
        medias=list(medias.values()),
    )


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create subsets in a HARI dataset based on an attribute."
    )

    # Add command-line arguments.

    parser.add_argument(
        "--dataset_name",
        type=str,
        help="Name of the dataset which should be uploaded",
        required=True,
    )

    parser.add_argument(
        "--image_directory",
        type=str,
        help="Directory of the images which should be uploaded",
        required=True,
    )

    parser.add_argument(
        "--annotations_file",
        type=str,
        help="File of the corresponding annotations for the given images",
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
    dataset_name = args.dataset_name
    images_dir = args.image_directory
    annotations_file = args.annotations_file
    user_group = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function
    # Make sure that your data is anonymized before you mark it as such
    # If your data is not anonymized please contact us for further support.
    upload_coco_like_dataset(
        hari,
        dataset_name,
        images_dir,
        annotations_file,
        user_group=user_group,
        is_anonymized=True,
    )
