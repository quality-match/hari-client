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

    parser.add_argument(
        "-c",
        "--cache_directory",
        type=str,
        help="Cache directory for saving the downloaded material",
        required=True,
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.uuid4() = args.dataset_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # define cache directory
    if config.data_directory:
        cache_directory = join(config.data_directory, args.cache_directory)
    else:
        cache_directory = args.cache_directory

    # download data
    medias, media_objects, attributes, attribute_metas = collect_media_and_attributes(
        hari,
        dataset_id,
        cache_directory,
        subset_ids=[],
        additional_fields=["attributes"],
    )

    print(len(media_objects), media_objects[0] if len(media_objects) else None)
    print(len(medias), medias[0] if len(medias) else None)
    print(len(attributes), attributes[0] if len(attributes) else None)
