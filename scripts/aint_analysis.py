import argparse
import uuid
from os.path import join

from hari_client import Config
from hari_client import HARIClient
from hari_client.models.models import AttributeGroup
from hari_client.utils.analysis import calculate_cutoff_thresholds
from hari_client.utils.analysis import calculate_ml_human_alignment
from hari_client.utils.analysis import create_soft_label_for_annotations
from hari_client.utils.analysis import organize_attributes_by_group
from hari_client.utils.download import collect_media_and_attributes

if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Download all media, media_object and attribute data for given dataset_id"
    )

    # Add command-line arguments.
    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to download", required=True
    )

    # TODO define cache directory
    DATA_DIRECTORY = "/Volumes/Data/data/"

    # TODO example usage:

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.uuid4() = args.dataset_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    directory = join(DATA_DIRECTORY, "hari_client_testing")
    # media_file = join(directory, "media.json")
    # media_object_file = join(directory, "media_objects.json")
    #
    # medias = pydantic_load_from_json(media_file, models.MediaResponse)
    # media_objects = pydantic_load_from_json(media_object_file, models.MediaObjectResponse)
    # attribute_values = convert_internal_attributes_to_list(medias,media_objects)
    # attribute_metas = get_attribute_metas_for_attributes_values(hari, dataset_id, attribute_values)
    #
    # print(attribute_metas)
    medias, media_objects, attributes, attribute_metas = collect_media_and_attributes(
        hari, dataset_id, directory, subset_ids=[], additional_fields=["attributes"]
    )

    print(len(media_objects), media_objects[0])
    print(len(medias), medias[0])
    print(len(attributes), attributes[0])

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
        key,
        human_question_key=human_question_key,
        selected_subset_ids=[model_data["test_subset_id"]],
        ID2subsets=ID2subsets,
    )

    # calculate cutoff

    cutoff_threholds = calculate_cutoff_thresholds(
        ID2annotation,
        ID2mlannotation,
        ID2confidence,
        key,
        ID2subsets,
        model_data["validation_subset_id"],
        model_data["test_subset_id"],
        human_key=human_question_key,
    )

    # print(cutoff_threholds)
    for cut_off_name, (cut_off_threshold, approximated_ad) in cutoff_threholds.items():
        print(f"# {cut_off_name} @ ~{approximated_ad * 100:0.02f}% automation")
        calculate_ml_human_alignment(
            ID2annotation,
            ID2mlannotation,
            key,
            human_question_key=human_question_key,
            selected_subset_ids=[model_data["test_subset_id"]],
            ID2subsets=ID2subsets,
            confidence_threshold=cut_off_threshold,
            ID2confidence=ID2confidence,
        )
