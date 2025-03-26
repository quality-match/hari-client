import argparse
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models
from hari_client.utils import logger

log = logger.setup_logger(__name__)


def get_ai_annotation_run_for_attribute_id(
    hari: HARIClient, ml_attribute_id: str
) -> models.AIAnnotationRunResponse | None:
    """
    Find an AI Annotation Run corresponding to a given attribute ID.

    Args:
        hari: The HARI client instance used to retrieve AI annotation runs if not provided.
        ml_attribute_id: The identifier of the attribute to match.

    Returns:
        The matching AI Annotation Run if found, otherwise None.
    """

    ai_annotation_runs = hari.get_ai_annotation_runs()
    log.info(f"Found {len(ai_annotation_runs)} AI Annotation Runs")

    # search for the desired annotation run
    for run in ai_annotation_runs:
        if run.attribute_metadata_id == uuid.UUID(ml_attribute_id):
            return run

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Get all linked AINT info for an AI annotation run attribute"
    )

    parser.add_argument(
        "-a",
        "--ml_attribute_id",
        type=uuid.UUID,
        help="ID of the AI annotation run Attribute.",
        required=True,
    )

    args = parser.parse_args()

    # Extract arguments.
    ml_attribute_id = args.ml_attribute_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # get Info for attribute ID

    # search for the desired annotation run
    # todo replace with get ai annotation rus with query when available
    ai_annotation_run = get_ai_annotation_run_for_attribute_id(hari, ml_attribute_id)

    if not ai_annotation_run:
        log.info(f"Could not find AI Annotation Run for attribute ID {ml_attribute_id}")
        exit(1)

    log.info(f"ai_annotation_run: {ai_annotation_run}")

    # get AINT model used in the ai annotation run
    model_id = ai_annotation_run.ml_annotation_model_id
    model = hari.get_ml_annotation_model_by_id(model_id)
    log.info(f"model: {model}")

    # get development data for AINT Model
    # !!! only available for qm internal users !!
    development_id = model.training_set_id

    development_set = hari.get_development_set(development_id)
    log.info(f"development_set: {development_set}")
