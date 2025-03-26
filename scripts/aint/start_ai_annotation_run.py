import argparse
import uuid

from hari_client import Config
from hari_client import HARIClient


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apply a trained AI Nano Task model to new data to run ai annotation and get model's predictions."
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Name of the AINT AI annotation run, used for later identification.",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--model_id",
        type=uuid.UUID,
        help="ID of the AI Nano Task model. Training needs to be finished before the model can be used for ai annotation.",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--dataset_id",
        type=uuid.UUID,
        help="Dataset ID of the new data.",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--subset_id",
        type=uuid.UUID,
        help="Subset ID of the new data.",
        required=True,
    )

    parser.add_argument(
        "-u",
        "--user_group",
        type=str,
        help="User group for the creation, if you can not see your created run, you might have a visibility issue related to your user_group",
        required=True,
    )

    args = parser.parse_args()

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # Start new AI annotation run to get AINT model predictions
    hari.start_ai_annotation_run(
        args.name, args.dataset_id, args.subset_id, args.model_id, args.user_group
    )

    print(
        "The AI annotation run can take some time, please wait. "
        "You will be notified via HARI / Email when the ai annotation is finished."
    )
