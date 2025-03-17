import argparse
import json
import os

import pandas as pd
from PIL import Image
from sklearn.utils import Bunch

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.utils.upload import check_and_upload_dataset
from hari_client.utils.upload import get_or_create_dataset


def load_yolo_data(image_dir: str, labels_dir: str, classes_filename: str):
    """
    Parse YOLO-format annotations where each .txt file corresponds to an image,
    and each line in the txt file has:
        class_idx x_center_norm y_center_norm width_norm height_norm

    Assumes:
        1) For each image in `image_dir`, there is a matching .txt in `labels_dir`
           with the same base filename but .txt extension.
        2) No separate classes file – we will label classes as 'class_{ID}'.

    Returns:
        Bunch:
            .categories -> list of category names used (e.g. ['class_45', 'class_49', 'class_50', ...])
            .df -> Bunch(images=..., annotations=...),
                   where images is a DataFrame of images,
                         annotations is a DataFrame of bounding boxes & attributes.
    """
    image_records = []
    annotation_records = []

    # Use this set to collect all encountered category names
    category_name_set = set()

    image_id_counter = 0

    with open(os.path.join(classes_filename), "r") as f:
        class_names = json.load(f)

        # Iterate over all images
    for file_name in sorted(os.listdir(image_dir)):
        # Check for typical image extensions
        if not (
            file_name.lower().endswith(".jpg")
            or file_name.lower().endswith(".jpeg")
            or file_name.lower().endswith(".png")
        ):
            continue

        # Paths
        img_path = os.path.join(image_dir, file_name)
        base_name, _ = os.path.splitext(file_name)
        label_txt = os.path.join(labels_dir, base_name + ".txt")

        # Read image size (so we can convert from normalized YOLO coords to pixel coords)
        with Image.open(img_path) as img:
            width, height = img.size

        # Add an image record
        image_records.append(
            {
                "image_id": image_id_counter,
                "file_name": img_path,
                "width": width,
                "height": height,
            }
        )

        # If the matching txt file exists, parse it
        annotation_id_counter = 0
        if os.path.exists(label_txt):
            with open(label_txt, "r") as lt:
                for line in lt:
                    parts = line.strip().split()
                    # Each line: class_idx, x_norm, y_norm, w_norm, h_norm
                    if len(parts) != 5:
                        # skip if the line format is unexpected
                        continue

                    (
                        class_idx_str,
                        x_norm_str,
                        y_norm_str,
                        w_norm_str,
                        h_norm_str,
                    ) = parts
                    class_idx = int(class_idx_str)
                    x_norm = float(x_norm_str)
                    y_norm = float(y_norm_str)
                    w_norm = float(w_norm_str)
                    h_norm = float(h_norm_str)

                    # Convert normalized coords -> absolute pixel coords
                    x_center = x_norm * width
                    y_center = y_norm * height
                    w_abs = w_norm * width
                    h_abs = h_norm * height

                    # We label the class as "class_{ID}"
                    # Convert the class index to its string label:
                    if str(class_idx) in class_names:
                        category_name = class_names[str(class_idx)]
                    else:
                        category_name = f"unknown_{class_idx}"  # or skip

                    category_name_set.add(category_name)

                    annotation_records.append(
                        {
                            "annotation_id": annotation_id_counter,
                            "image_id": image_id_counter,
                            "category": category_name,
                            # bounding box center-based
                            "x": x_center,
                            "y": y_center,
                            "width": w_abs,
                            "height": h_abs,
                            "back_reference": base_name
                            + ".txt"
                            + f"-{annotation_id_counter}",
                        }
                    )
                    annotation_id_counter += 1

        image_id_counter += 1

    # Create DataFrames
    df_images = pd.DataFrame(image_records).set_index("image_id", drop=True)
    df_annotations = pd.DataFrame(annotation_records).set_index(
        "annotation_id", drop=True
    )

    return Bunch(
        categories=sorted(list(category_name_set)),
        df=Bunch(images=df_images, annotations=df_annotations),
    )


def upload_yolo_dataset(
    hari,
    dataset_name,
    image_dir,
    labels_dir,
    classes_filename,
    user_group,
    is_anonymized,
):
    # Create or retrieve dataset
    dataset_id = get_or_create_dataset(
        hari, dataset_name, user_group, is_anonymized=is_anonymized
    )

    # Load YOLO data from your images/labels
    data = load_yolo_data(
        image_dir=image_dir, labels_dir=labels_dir, classes_filename=classes_filename
    )

    # Build HARIMedia objects
    medias = {}
    for i, (idx, image_info) in enumerate(data.df.images.iterrows(), start=1):
        medias[idx] = hari_uploader.HARIMedia(
            file_path=image_info["file_name"],
            name=os.path.basename(image_info["file_name"]),
            back_reference=image_info["file_name"],
            media_type=models.MediaType.IMAGE,
        )

    # For each annotation, create a HARIMediaObject with bounding box
    for object_idx, record in data.df.annotations.iterrows():
        media_object = hari_uploader.HARIMediaObject(
            back_reference=record.back_reference,
            reference_data=models.BBox2DCenterPoint(
                type=models.BBox2DType.BBOX2D_CENTER_POINT,
                x=record.x,
                y=record.y,
                width=record.width,
                height=record.height,
            ),
        )

        # add class
        media_object.set_object_category_subset_name(record["category"])

        # Append this object to the correct media
        medias[record.image_id].add_media_object(media_object)

    check_and_upload_dataset(
        hari,
        dataset_id,
        object_categories=set(data.categories),
        medias=list(medias.values()),
    )


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(description="Upload YOLO-format data to HARI.")

    # Add command-line arguments.
    parser.add_argument(
        "--dataset_name",
        type=str,
        help="Name of the dataset which should be uploaded",
        required=True,
    )
    parser.add_argument(
        "--image_directory",
        help="Directory of the images which should be uploaded",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--labels_directory",
        help="Directory of the corresponding annotations for the given images",
        type=str,
        required=True,
    )

    parser.add_argument(
        "--classes_filename",
        help="File of the corresponding classes for the given images",
        type=str,
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
    image_dir = args.image_directory
    labels_dir = args.labels_directory
    classes_filename = args.classes_filename
    user_group = args.user_group

    # load hari client
    config = Config(_env_file=".env")
    hari = HARIClient(config=config)

    # Call the main function
    # Make sure that your data is anonymized before you mark it as such
    # If your data is not anonymized please contact us for further support.
    upload_yolo_dataset(
        hari,
        dataset_name,
        image_dir,
        labels_dir,
        classes_filename,
        user_group=user_group,
        is_anonymized=True,
    )
