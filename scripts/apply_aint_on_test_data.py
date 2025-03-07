import argparse

from hari_client import Config
from hari_client import HARIClient


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Apply a trained AI Nano Task model to its associated test set. This can be used to do manual analysis on the test set."
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Name of the AINT execution, used for identification. "
        "It is recommended to include the Project Name and Applied Dataset / Subset name for easier searchability.",
        required=True,
    )
    parser.add_argument(
        "-a",
        "--aint_model_id",
        type=str,
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
    name: str = args.name
    aint_id: str = args.aint_id
    user_group: str = args.user_group

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # get development data for AINT ID
    model = hari.get_ml_model(aint_id)
    print(model.dataset_id)
    print(model.test_subset_id)

    # TODO Currently this request is blocked by the API

    # Start AINT prediction
    hari.start_ai_annotation_run(
        name, model.dataset_id, model.test_subset_id, aint_id, user_group=user_group
    )

    print(
        "The AINT prediction can take a while please wait. You will be getting notified via HARI / Email when the prediction is done."
    )
