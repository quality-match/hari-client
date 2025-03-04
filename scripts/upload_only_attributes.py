import argparse

import requests

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models
from hari_client.utils.upload import check_and_upload_dataset
from hari_client.utils.upload import get_or_create_dataset

if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Example script how to upload attributes to a previously created media or media objects"
    )

    # Add command-line arguments.
    parser.add_argument(
        "--dataset_name",
        type=str,
        help="Name of the dataset which should be uploaded",
        required=True,
    )

    parser.add_argument(
        "--image_url",
        type=str,
        help="Url of an image which should be uploaded as a dataset",
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
    image_url = args.image_url
    user_group = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # create dataset
    dataset_id = get_or_create_dataset(
        hari=hari, dataset_name=dataset_name, user_group=user_group, is_anonymized=True
    )

    # download image and create media
    local_path = "./test_img.png"
    img_data = requests.get(image_url).content
    with open(local_path, "wb") as handler:
        handler.write(img_data)

    # recreate the previous uploaded data, create full entry here since media may not have been uploaded
    media = hari_uploader.HARIMedia(
        name="Test image 1",
        file_path=local_path,
        back_reference=image_url,
        media_type=models.MediaType.IMAGE,
    )

    # Add media object to the media
    obj1 = hari_uploader.HARIMediaObject(
        back_reference="MO1",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=10,
            y=11,
            width=12,
            height=13,
        ),
    )
    media.add_media_object(obj1)

    # Add attributes to the media
    att1 = hari_uploader.HARIAttribute(
        name="Attribute3",
        attribute_group=models.AttributeGroup.InitialAttribute,
        attribute_type=models.AttributeType.Binary,
        value=False,
    )
    media.add_attribute(att1)
    obj1.add_attribute(att1)

    # upload image to dataset
    check_and_upload_dataset(
        hari=hari,
        dataset_id=dataset_id,
        object_categories=[],
        medias=[media],
        new_subset_name="All Media",
        subset_type=models.SubsetType.MEDIA,
    )

    # if media is uploaded already only the backreference is needed
    media = hari_uploader.HARIMediaMockUpload(
        back_reference=image_url,
    )

    obj1 = hari_uploader.HARIMediaObjectMockUpload(back_reference=obj1.back_reference)

    # Add attributes to the media
    att2 = hari_uploader.HARIAttribute(
        name="Attribute4",
        attribute_group=models.AttributeGroup.AnnotationAttribute,
        attribute_type=models.AttributeType.Categorical,
        question="This could be a question?",
        possible_values=["yes", "cat", "wizard"],
        value="wizard",
        frequency={"wizard": 4, "cat": 2},
        cant_solves=1,
        repeats=7,
    )
    media.add_attribute(
        att1, att2
    )  # att1 was already uploaded but uploader can handle this

    media.add_media_object(obj1)
    obj1.add_attribute(att1, att2)

    # upload image to dataset
    check_and_upload_dataset(
        hari=hari,
        dataset_id=dataset_id,
        object_categories=[],
        medias=[media],
        new_subset_name="All Media",
        subset_type=models.SubsetType.MEDIA,
    )
