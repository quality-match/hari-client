import argparse
import json
import os
import uuid
from pathlib import Path

import pandas as pd
from PIL import Image
from sklearn.utils import Bunch

import hari_client as hc
from hari_client import Config
from hari_client import HARIClient
from hari_client.utils.upload import check_and_create_dataset
from hari_client.utils.upload import check_and_upload_dataset


def load_data(root_directory, source_dataset_name: str):
    # We have no explicit image objects
    # An image implicitly represents an image object
    # We therefore need the dimensions of the images

    image_sizes = dict(
        [
            (image_path.as_posix(), Image.open(image_path).size)
            for image_path in (
                Path(os.path.join(root_directory, source_dataset_name)).rglob(
                    "fold[0-9]*/**/*.png"
                )
            )
        ]
    )

    # change image_path name to be cut of after before source dataset name
    image_sizes = {
        source_dataset_name
        + image_path.split(source_dataset_name)[1]: image_sizes[image_path]
        for image_path in image_sizes.keys()
    }

    # Read the annotation file
    # Assumed to be in the top-level folder of each dataset,
    # named `annotations.json`

    annotation_file_path = (
        Path(os.path.join(root_directory, source_dataset_name)) / "annotations.json"
    )
    with open(annotation_file_path, "r") as fp:
        # The json yields a list containing one object
        raw_data = json.load(fp)

    # get all annotation slices
    annotations = [anno for slice in raw_data for anno in slice["annotations"]]

    df_answers = pd.DataFrame(annotations)
    categories = df_answers.class_label.unique().tolist()

    df_answers_pivot = (
        pd.pivot_table(
            data=df_answers,
            index="image_path",
            columns="class_label",
            values="class_label",
            aggfunc="count",
        )
        .fillna(0)
        .astype(int)
    )

    # We create a dictionary that maps `image_path`s to response frequencies
    # We filter the answers so that only categories that have received at least
    #   one answer are written

    answer_frequencies = {
        image_path: {
            cat_name: answer_cnt
            for cat_name, answer_cnt in frequency.items()
            if answer_cnt > 0
        }
        for image_path, frequency in (df_answers_pivot.to_dict(orient="index").items())
    }

    # We would also like to report the majority vote for each object
    # { image_path => majority category }

    majority_votes = df_answers_pivot.idxmax(axis="columns").to_dict()

    return Bunch(
        categories=categories,
        image_sizes=image_sizes,
        frequencies=answer_frequencies,
        majority_votes=majority_votes,
    )


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
    dataset_id = check_and_create_dataset(hari, dataset_name, user_group, is_anonymized)

    # load actual data for uplod
    data = load_data(root_directory, source_dataset_name)

    medias = {
        image_path: hc.hari_uploader.HARIMedia(
            file_path=str(Path(os.path.join(root_directory, image_path))),
            name=image_path,
            back_reference=image_path,
            media_type=hc.models.MediaType.IMAGE,
        )
        for image_path in data.frequencies
    }

    # medias == media objects
    # but we still need to explicity create them
    # using dummy geometries

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
        sum(data.frequencies.get(image_path).values()) for image_path in medias
    ]
    avg_number_annotions = int(round(sum(number_annotations) / len(number_annotations)))

    for image_path, media in medias.items():
        width, height = data.image_sizes.get(image_path)
        frequency = data.frequencies.get(image_path)
        majority_vote = data.majority_votes.get(image_path)

        media_object = hc.hari_uploader.HARIMediaObject(
            back_reference=image_path,
            reference_data=hc.models.BBox2DCenterPoint(
                type=hc.models.BBox2DType.BBOX2D_CENTER_POINT,
                x=width / 2,
                y=height / 2,
                width=width,
                height=height,
            ),
        )
        attribute = hc.hari_uploader.HARIAttribute(
            value=majority_vote,
            frequency=frequency,
            cant_solves=0,
            repeats=avg_number_annotions,
            **annotatable_attribute
        )
        media_object.add_attribute(attribute)
        media_object.set_object_category_subset_name(majority_vote)
        media.add_media_object(media_object)

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
