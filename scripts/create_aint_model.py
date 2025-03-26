import argparse
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models
from hari_client.utils import logger

log = logger.setup_logger(__name__)


def create_development_data(
    hari: HARIClient,
    name: str,
    dataset_id: uuid.UUID,
    attribute_id: uuid.UUID,
    subset_id: uuid.UUID,
    user_group: str = None,
) -> models.DevelopmentSetResponse:
    # construct training attributes
    if subset_id is None:
        training_attribute = models.TrainingAttribute(
            attribute_id=attribute_id, dataset_id=dataset_id
        )
    else:
        training_attribute = models.TrainingAttribute(
            attribute_id=attribute_id,
            dataset_id=dataset_id,
            query=[
                models.QueryParameter(
                    attribute="subset_ids", query_operator="in", value=[subset_id]
                )
            ],
        )

    return hari.create_development_set(name, [training_attribute], user_group)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create and train an AI Nano Task (model). This also create the needed development sets."
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Name of the AINT model, used for identification.",
        required=True,
    )

    parser.add_argument(
        "-a",
        "--attribute_id",
        type=uuid.UUID,
        help="Attribute ID on which the AINT should be trained",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--dataset_id",
        type=uuid.UUID,
        help="Dataset ID to work on.",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--subset_id",
        type=uuid.UUID,
        help="Subset ID to which the attributes should be restricted.",
    )

    parser.add_argument(
        "--user_group",
        type=str,
        help="User group for the creation, if you can not see your creation you might have a visibility issue related to your user_group",
        required=True,
    )

    args = parser.parse_args()

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Create Development Data
    # !!! only available to qm internal users !!!
    development_data = create_development_data(
        hari,
        args.name,
        args.dataset_id,
        args.attribute_id,
        args.subset_id,
        args.user_group,
    )
    development_data_id = development_data.id
    log.info(f"Created development data with ID: {development_data_id}")

    # Start AINT model training
    model_id = hari.train_ml_annotation_model(args.name, development_data_id)

    log.info(
        "The AINT training can take a while, please wait. "
        "You will be notified via HARI / Email when the training is done."
    )
