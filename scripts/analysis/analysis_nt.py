import argparse
import logging
import os
import uuid
from os.path import join

from hari_client import Config
from hari_client import HARIClient
from hari_client.models.models import AttributeGroup
from hari_client.utils.analysis import create_soft_label_for_annotations
from hari_client.utils.analysis import histograms_for_nanotask
from hari_client.utils.analysis import organize_attributes_by_group
from hari_client.utils.download import collect_media_and_attributes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(description="Analyse the specific annotation run.")

    # Add command-line arguments.
    parser.add_argument(
        "--dataset_id",
        type=str,
        help="Dataset ID for which the report should be created",
        required=True,
    )

    parser.add_argument(
        "-s", "--subset_id", type=str, help="Optional, Subset ID for filtering down"
    )

    parser.add_argument(
        "-a",
        "--attribute_id",
        type=str,
        help="Attribute ID for which the report should be created, Either this ID or AnnotationRunNode ID need to be specified",
    )


    parser.add_argument(
        "-c",
        "--cache_directory",
        type=str,
        help="Cache directory for saving the downloaded material",
        required=True,
    )

    parser.add_argument(
        "-o",
        "--output_directory",
        type=str,
        help="Output directory for the analysis",
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.UUID = args.dataset_id
    attribute_id: uuid.UUID = args.attribute_id
    subset_id: uuid.UUID = args.subset_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # define cache directory
    if config.data_directory:
        cache_directory = join(config.data_directory, args.cache_directory)
        if args.output_directory:
            output_directory = join(config.data_directory, args.output_directory)
        else:
            output_directory = None
    else:
        cache_directory = args.cache_directory
        output_directory = args.output_directory

    if output_directory is not None:
        os.makedirs(output_directory, exist_ok=True)

    medias, media_objects, attributes, attribute_metas = collect_media_and_attributes(
        hari,
        dataset_id,
        cache_directory,
        subset_ids=[subset_id] if subset_id is not None else [],
        additional_fields=["attributes"],
        cache=False,
    )

    print(medias[0])
    print(media_objects[0])

    # generate lookup tables
    ID2attribute_meta = {str(a.id): a for a in attribute_metas}

    # print(attributes)

    # organize Attributes by type
    group2media_attribute, group2media_object_attribute = organize_attributes_by_group(
        attributes, ID2attribute_meta
    )

    # print(group2media_object_attribute)

    # convert annotations into soft label
    ID2annotation, ID2ambiguity = create_soft_label_for_annotations(
        group2media_object_attribute[AttributeGroup.AnnotationAttribute],
        "frequency",
        normalize=True,
        combine=False,
        additional_result="ambiguity",
    )

    # visualize
    histograms_for_nanotask(
        ID2annotation, ID2ambiguity, str(attribute_id), output_directory=output_directory
    )

    # group by operations

    initial_attributes = group2media_object_attribute[AttributeGroup.InitialAttribute]
    ## group by initial attribute
    # TODO add to argparse
    initial_attribute_name = "reid camera_id"
    ## get attribute meta id
    initial_attribute_meta_id = None
    for attr_meta in attribute_metas:
        # TODO improvement idea: make name comparison more robust by casting to lower case and remove _ and spaces
        if (
            attr_meta.attribute_group == AttributeGroup.InitialAttribute
            and attr_meta.name == initial_attribute_name
        ):
            initial_attribute_meta_id = attr_meta.id

    if initial_attribute_meta_id is None:
        print("WARNING: No initial attribute with name ", initial_attribute_name)
    else:
        ID2initial_attribute = {}
        for init_attr in initial_attributes:
            if init_attr.metadata_id == initial_attribute_meta_id:
                ID2initial_attribute[init_attr.annotatable_id] = init_attr.value

        # group by
        groupby_values = []
        for media_object_id, group_value in ID2initial_attribute.items():
            if group_value not in groupby_values:
                groupby_values.append(group_value)

        if len(groupby_values) == 0:
            print(
                "WARNING: No value found for grouping by initial attribute ",
                initial_attribute_name,
            )
        else:
            histograms_for_nanotask(
                ID2annotation,
                ID2ambiguity,
                str(attribute_id),
                ID2groupby_value=ID2initial_attribute,
                groupby_values=groupby_values,
                groupy_name=initial_attribute_name,
                output_directory=output_directory,
            )
