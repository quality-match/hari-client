import argparse

from hari_client import Config
from hari_client import HARIClient


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(description="Create and train an AI Nano Task")

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
        "--aint_id",
        type=str,
        help="ID of the AI Nano Task. Training needs to be done before the AINT can be used.",
        required=True,
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    name: str = args.name
    aint_id: str = args.aint_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # get development data for AINT ID
    model = hari.get_aint_model(aint_id)
    print(model.dataset_id)
    print(model.test_subset_id)

    # TODO user_group
    # TODo example usage

    # TODo not possbile, subset id unknown, most likely because it is hidden

    # Start AINT prediction
    hari.start_ai_annotation_run(
        name, model.dataset_id, model.test_subset_id, aint_id, user_group=None
    )

    print(
        "The AINT prediction can take a while please wait. You will be getting notified via HARI / Email when the prediction is done."
    )
