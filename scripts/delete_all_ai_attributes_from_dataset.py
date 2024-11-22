import argparse
import json
from uuid import UUID

from tqdm import tqdm

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def delete_all_ai_attributes_from_dataset(
    hari: HARIClient, dataset_id: str, delete: bool
) -> None:
    """
    Delete all AI-generated attributes (MlAnnotationAttribute) from a HARI dataset.

    Args:
        hari (HARIClient): The HARI client instance used to interact with the HARI API.
        dataset_id (str): The ID of the dataset from which to delete attributes.
        delete (bool): Flag indicating whether to actually delete the attributes (True) or just display them (False).
    """

    dataset_id = UUID(dataset_id)

    # Define a query to select all AI-generated attributes (MlAnnotationAttribute)
    query_all_ai_attributes: dict = {
        "attribute": "attribute_group",
        "query_operator": "==",
        "value": models.AttributeGroup.MlAnnotationAttribute,
    }

    # Retrieve all attribute metadata matching the query
    attribute_metadata_list: list[
        models.AttributeMetadataResponse
    ] = hari.get_attribute_metadata(
        dataset_id, query=json.dumps(query_all_ai_attributes)
    )

    print(f"Found {len(attribute_metadata_list)} AI attributes to be deleted")

    # Iterate over each attribute metadata and delete if specified
    for attribute in tqdm(attribute_metadata_list, desc="Processing attributes"):
        if delete:
            # Delete the attribute metadata from the dataset
            hari.delete_attributeMetadata(dataset_id, attribute.id)
            print(
                f"Deleted attribute {attribute.id} with question '{attribute.question}'"
            )
        else:
            # Display the attribute that would be deleted
            print(
                f"Would delete attribute {attribute.id} with question '{attribute.question}'"
            )


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create subsets in a HARI dataset based on an attribute."
    )

    # Add command-line arguments.

    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to work on.", required=True
    )

    parser.add_argument(
        "--delete",
        help="If set, actually delete the attributes. If not set, only display what would be deleted.",
        default=False,
        action="store_true",
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: str = args.dataset_id
    delete: bool = args.delete
    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    delete_all_ai_attributes_from_dataset(hari, dataset_id, delete)
