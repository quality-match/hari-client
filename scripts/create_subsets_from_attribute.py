import argparse
import json
from typing import List
from uuid import UUID

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models
from hari_client.models.models import SubsetType


def create_subsets_for_attribute(
    hari: HARIClient, dataset_id: str, attribute_id: str, prefix: str
) -> None:
    """
    Function to create subsets in a HARI dataset based on a given attribute.
    Disclaimer: This function only works for MediaObjects subsets. It uses the first visualization config by default.

    Args:
        hari (HARIClient): API Client
        dataset_id (str): The ID of the dataset to work on.
        attribute_id (str): The ID of the attribute to query.
        prefix (str): A prefix to add to subset names for better sorting.
    """

    dataset_id = UUID(dataset_id)

    # Retrieve the dataset object using the provided dataset ID.
    dataset = hari.get_dataset(dataset_id)
    print(f"Working on dataset: {dataset.name}")

    # 2. Get attributes matching the provided attribute ID.
    # Construct a query to find the attribute with the specified ID.
    query: dict = {"attribute": "id", "query_operator": "==", "value": attribute_id}

    # Execute the query to retrieve the attributes.
    attributes = hari.get_attributes(dataset_id, query=json.dumps(query))
    print(f"Found {len(attributes)} attributes with ID {attribute_id}")

    # 3. Extract needed subsets.
    # Collect all unique labels from the attribute frequencies.
    labels: List[str] = list(
        set(
            [
                label
                for attribute in attributes
                if attribute.frequency is not None
                for label in attribute.frequency.keys()
            ]
        )
    )
    print(f"Need to create subsets for labels: {labels}")

    # 4. Create subsets.
    # Retrieve available visualization configurations for the dataset.
    visconfigs: List[models.VisualisationConfiguration] = hari.get_vis_configs(
        dataset_id
    )
    if not visconfigs:
        print("No visualization configurations found for the dataset.")
        return

    # Use the first visualization configuration ID.
    vis_config_id: str = visconfigs[0].id
    print(f"Using visualization configuration ID: {vis_config_id}")

    # Create subsets for each label.
    for label in labels:
        # Define the query to select media objects with the specific attribute and label.
        label_query: dict = {
            "attribute": f"attributes.{attribute_id}.dataset_id",
            "query_operator": "==",
            "value": dataset_id,
        }
        dataset_query: dict = {
            "attribute": f"attributes.{attribute_id}.aggregate",
            "query_operator": "in",
            "value": [label],
        }
        subset_name: str = f"{prefix}{label}"
        print(f"Creating subset: {subset_name}")

        # Create the subset using the HARI client.
        hari.create_subset(
            dataset_id=dataset_id,
            subset_type=SubsetType.MEDIA_OBJECT,
            subset_name=subset_name,
            visualisation_config_id=vis_config_id,
            filter_options=[label_query, dataset_query],
        )


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create subsets in a HARI dataset based on an attribute."
    )

    # Add command-line arguments.
    parser.add_argument(
        "-a",
        "--attribute_id",
        type=str,
        help="Attribute ID for which each distinct aggregate value should be transformed into a subset.",
        required=True,
    )
    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to work on.", required=True
    )
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        help="Prefix to add to subset names for better sorting.",
        default="",
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    attribute_id: str = args.attribute_id
    dataset_id: str = args.dataset_id
    prefix: str = args.prefix

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    create_subsets_for_attribute(hari, dataset_id, attribute_id, prefix)
