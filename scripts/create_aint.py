import argparse

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def create_aint_learning_data_from_attribute(
    hari: HARIClient,
    name: str,
    dataset_id: str,
    attribute_id: str,
    subset_id: str,
    user_group: str = None,
) -> models.AINTLearningDataResponse:
    # construct training attributes
    # simple case only one attribute, simple filter subset
    if subset_id is None:
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

    return hari.create_aint_learning_data(name, [training_attribute], user_group)


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Create and train an AI Nano Task (model). This also create the needed AINT learning data."
    )

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

    parser.add_argument(
        "--user_group",
        type=str,
        help="User group for the creation, if you can not see your creation you might have a visibility issue related to your user_group",
        required=True,
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    name: str = args.name
    attribute_id: str = args.attribute_id
    dataset_id: str = args.dataset_id
    subset_id: str | None = args.subset_id
    user_group: str = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Create AINT Learning Data
    aint_learning_data = create_aint_learning_data_from_attribute(
        hari, name, dataset_id, attribute_id, subset_id, user_group=user_group
    )
    aint_learning_data_id = aint_learning_data.id
    print(f"Created aint learning data with ID: {aint_learning_data_id}")

    # Start AINT Training
    aint_id = hari.train_ml_model(name, aint_learning_data_id, user_group=user_group)

    print(
        "The AINT training can take a while please wait. You will be getting notified via HARI / Email when the training is done."
    )
