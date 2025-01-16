import argparse

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def create_development_data(
    hari: HARIClient,
    name: str,
    dataset_id: str,
    attribute_id: str,
    subset_id: str,
    user_group: str = None,
) -> models.DevelopmentSetResponse:
    # construct training attributes
    # simple case only one attribute, simple filter subset
    if subset_id is not None:
        training_attribute = {"attribute_id": attribute_id, "dataset_id": dataset_id}
    else:
        training_attribute = {
            "attribute_id": attribute_id,
            "dataset_id": dataset_id,
            "query": [
                {
                    "attribute": "subset_ids",
                    "query_operator": "in",
                    "value": [subset_id],
                }
            ],
        }

    return hari.create_development_set(name, [training_attribute], user_group)


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(description="Create and train an AI Nano Task")

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Name of the AINT, used for identification. "
        "It is recommended to include the Project Name for easier searchability.",
        required=True,
    )

    # Add command-line arguments.
    parser.add_argument(
        "-a",
        "--attribute_id",
        type=str,
        help="Attribute ID on which the AINT should be trained",
        required=True,
    )
    parser.add_argument(
        "-d", "--dataset_id", type=str, help="Dataset ID to work on.", required=True
    )
    parser.add_argument(
        "-s",
        "--subset_id",
        type=str,
        help="Subset ID to which the attributes should be restricted.",
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    name: str = args.name
    attribute_id: str = args.attribute_id
    dataset_id: str = args.dataset_id
    subset_id: str | None = args.subset_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # TODO add user group

    # TODO example usage:
    # TODO test what happens if wrong input, wrong subset id seems still to work

    # Create Development Data
    development_data = create_development_data(
        hari, name, dataset_id, attribute_id, subset_id
    )
    development_data_id = development_data.id
    print(f"Created development data with ID: {development_data_id}")

    # Start AINT Training
    aint_id = hari.train_aint_model(name, development_data_id)

    print(
        "The AINT training can take a while please wait. You will be getting notified via HARI / Email when the training is done."
    )
