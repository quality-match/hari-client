import argparse

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def get_ai_annotation_run_for_attribute_id(
    hari, aint_attribute_id: str, ai_annoation_runs: list[models.AiAnnotationRun] = None
) -> models.AiAnnotationRun | None:
    """
    Find an AI Annotation Run corresponding to a given attribute ID.

    If a list of AI Annotation Runs is not provided, this function retrieves them from the
    HARI client, then searches for the run whose `attribute_metadata_id` matches the
    specified attribute ID.

    Args:
        hari: The HARI client instance used to retrieve AI annotation runs if not provided.
        aint_attribute_id (str): The identifier of the attribute to match.
        ai_annoation_runs (list[models.AiAnnotationRun], optional): An existing list of runs
            to search. If None, the function will call `hari.get_ai_annotation_runs()`.

    Returns:
        models.AiAnnotationRun | None: The matching AI Annotation Run if found, otherwise None.
    """

    if ai_annoation_runs is None:
        ai_annoation_runs: list[models.AiAnnotationRun] = hari.get_ai_annotation_runs()
        print(f"Found {len(ai_annoation_runs)} AI Annotation Runs")

    # search for the desired annotation run
    ai_annotation_run: models.AiAnnotationRun = None
    for run in ai_annoation_runs:
        if run.attribute_metadata_id == aint_attribute_id:
            ai_annotation_run = run
            break

    return ai_annotation_run


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Get all linked AINT info for an AI annotation run attribute"
    )

    parser.add_argument(
        "-a",
        "--aint_attribute_id",
        type=str,
        help="ID of the AI annotation run Attribute.",
        required=True,
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    aint_attribute_id: str = args.aint_attribute_id

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # get Info for attribute ID

    # get all annotation runs
    ai_annoation_runs: list[models.AiAnnotationRun] = hari.get_ai_annotation_runs()
    print(f"Found {len(ai_annoation_runs)} AI Annotation Runs")

    # search for the desired annotation run
    ai_annotation_run = get_ai_annotation_run_for_attribute_id(
        hari, aint_attribute_id, ai_annoation_runs
    )

    # OPTIONAL if you want a specific ai annotation run
    # annoation_run_id = "???????"
    # ai_annotation_run = hari.get_ai_annotation_run(annoation_run_id)

    model_id = ai_annotation_run.ml_annotation_model_id

    # get AINT model for Attribute ID

    # OPTIONAL if you want to get all models
    models = hari.get_ml_models()
    print(f"Found {len(models)} models")

    model = hari.get_ml_model_by_id(model_id)
    print(model)

    # get learning data for AINT Model
    aint_learning_data_id = model.aint_learning_data_id

    # OPTIONAL if you want to get all AINT learning data
    all_aint_learning_data = hari.get_multiple_aint_learning_data()
    print(f"Found {len(all_aint_learning_data)} aint learning data entities")

    aint_learning_data = hari.get_aint_learning_data(aint_learning_data_id)
    print(aint_learning_data)
