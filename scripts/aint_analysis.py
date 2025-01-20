import argparse
import uuid
from os.path import join

from get_aint_attribute_info import get_ai_annotation_run_for_attribute_id

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models
from hari_client.models.models import AttributeGroup
from hari_client.utils.analysis import calculate_cutoff_thresholds
from hari_client.utils.analysis import calculate_ml_human_alignment
from hari_client.utils.analysis import create_soft_label_for_annotations
from hari_client.utils.analysis import find_attribute_id_by_name
from hari_client.utils.analysis import organize_attributes_by_group
from hari_client.utils.download import collect_media_and_attributes


def aint_analysis(
    human_annotation_attribute_id: str,
    ai_annotation_attribute_id: str,
    model: models.MlAnnotationModel,
):
    # generate lookup tables
    ID2attribute_meta = {a.id: a for a in attribute_metas}

    # primary target: media_objects, medias would also be possible
    ID2subsets = {m.id: m.subset_ids for m in media_objects}

    # organize Attributes by type
    # TODO splitting should maybe already happen in collect media and attributes
    group2media_attribute, group2media_object_attribute = organize_attributes_by_group(
        attributes, ID2attribute_meta
    )

    # convert annotations into soft label
    ID2annotation = create_soft_label_for_annotations(
        group2media_object_attribute[AttributeGroup.AnnotationAttribute],
        "frequency",
        normalize=True,
        combine=False,
    )

    print(len(ID2annotation))
    print(ID2annotation[list(ID2annotation.keys())[0]])

    ID2mlannotation, ID2confidence = create_soft_label_for_annotations(
        group2media_object_attribute[AttributeGroup.MlAnnotationAttribute],
        "ml_probability_distributions",
        normalize=False,
        ignore_duplicate=True,
        additional_result="confidence",
    )

    # calculate alignment
    print("# 100% Automation")
    calculate_ml_human_alignment(
        ID2annotation,
        ID2mlannotation,
        ai_annotation_attribute_id,
        human_attribute_key=human_annotation_attribute_id,
        selected_subset_ids=[model.test_subset_id],
        ID2subsets=ID2subsets,
    )

    # calculate cutoff
    cutoff_thresholds = calculate_cutoff_thresholds(
        ID2annotation,
        ID2mlannotation,
        ID2confidence,
        ai_annotation_attribute_id,
        ID2subsets,
        model.validation_subset_id,
        model.test_subset_id,
        human_key=human_annotation_attribute_id,
    )

    # print(cutoff_threholds)
    for cut_off_name, (cut_off_threshold, approximated_ad) in cutoff_thresholds.items():
        print(f"# {cut_off_name} @ ~{approximated_ad * 100:0.02f}% automation")
        calculate_ml_human_alignment(
            ID2annotation,
            ID2mlannotation,
            ai_annotation_attribute_id,
            human_attribute_key=human_annotation_attribute_id,
            selected_subset_ids=[model.test_subset_id],
            ID2subsets=ID2subsets,
            confidence_threshold=cut_off_threshold,
            ID2confidence=ID2confidence,
        )


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Download all media, media_object and attribute data for given dataset_id"
    )

    # Add command-line arguments.
    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to download", required=True
    )

    parser.add_argument(
        "-s", "--subset_id", type=str, help="Optional, Subset ID for filtering down"
    )

    parser.add_argument(
        "-aa",
        "--ai_annotation_attribute_id",
        type=str,
        help="AI Annotation Attribute ID which should be evaluated",
        required=True,
    )

    parser.add_argument(
        "-ha",
        "--human_annotation_attribute_name",
        type=str,
        help="Human Annotation Attribute Name which should be evaluated",
        required=True,
    )

    parser.add_argument(
        "-c",
        "--cache_directory",
        type=str,
        help="Cache directory for saving the downloaded material",
        required=True,
    )

    # TODO example usage:

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.uuid4() = args.dataset_id
    subset_id: str = args.subset_id
    ai_annotation_attribute_id = args.ai_annotation_attribute_id
    human_annotation_attribute_name = args.human_annotation_attribute_name

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # define cache directory
    if config.data_directory:
        cache_directory = join(config.data_directory, args.cache_directory)
    else:
        cache_directory = args.cache_directory

    medias, media_objects, attributes, attribute_metas = collect_media_and_attributes(
        hari,
        dataset_id,
        cache_directory,
        subset_ids=[subset_id] if subset_id is not None else [],
        additional_fields=["attributes"],
    )

    # print(len(media_objects), media_objects[0])
    # print(len(medias), medias[0])
    # print(len(attributes), attributes[0])

    # Get AINT info for attribute ID
    ai_annotation_run = get_ai_annotation_run_for_attribute_id(
        hari, ai_annotation_attribute_id
    )
    model_id = ai_annotation_run.ml_annotation_model_id
    model: models.MlAnnotationModel = hari.get_aint_model(model_id)

    # try to find specific question by name
    human_annotation_attribute_id = find_attribute_id_by_name(
        human_annotation_attribute_name, attribute_metas
    )

    aint_analysis(human_annotation_attribute_id, ai_annotation_attribute_id, model)
