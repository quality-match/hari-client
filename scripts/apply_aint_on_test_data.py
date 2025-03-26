import argparse
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.utils import logger

log = logger.setup_logger(__name__)


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Apply a trained AI Nano Task model to its associated test set. This can be used to do manual analysis on the test set."
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Name of the AINT AI annotation, that will be used for later identification.",
        required=True,
    )
    parser.add_argument(
        "-a",
        "--model_id",
        type=uuid.UUID,
        help="ID of the AI Nano Task model. Training needs to be done before the AINT can be used.",
        required=True,
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
    name = args.name
    model_id = args.model_id
    user_group = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # get development data for AINT ID
    # !!! only available to internal qm users !!!
    model = hari.get_ml_annotation_model_by_id(model_id)
    log.info(model.dataset_id)
    log.info(model.test_subset_id)

    # TODO Currently this request is blocked by the API

    # Start AINT prediction (ai annotation run)
    hari.start_ai_annotation_run(
        name, model.dataset_id, model.test_subset_id, model_id, user_group
    )

    log.info(
        "The AI annotation run can take a while, please wait. You will be notified via HARI / Email when the ai annotation is finished."
    )
