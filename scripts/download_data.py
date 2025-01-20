import argparse
import uuid
from os.path import join

from hari_client import Config
from hari_client import HARIClient
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
