import argparse
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.utils.upload import trigger_and_display_metadata_update

if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create subsets in a HARI dataset based on an attribute."
    )

    # Add command-line arguments.

    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to recreate", required=True
    )

    parser.add_argument("-s", "--subset_id", type=str, help="Subset ID to recreate")

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.UUID = uuid.UUID(args.dataset_id)
    subset_id: uuid.UUID | None = (
        uuid.UUID(args.subset_id) if args.subset_id is not None else None
    )
    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Call the main function.
    trigger_and_display_metadata_update(hari, dataset_id, subset_id)
