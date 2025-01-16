import argparse

from hari_client import Config
from hari_client import HARIClient
from hari_client.models import models


def get_ai_annotation_run_for_attribute_id(
    attribute_id: str, ai_annoation_runs: list[models.AiAnnotationRun] = None
) -> models.AiAnnotationRun | None:
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
        description="Get all linked AINT info for an AINT attribute"
    )

    parser.add_argument(
        "-a",
        "--aint_attribute_id",
        type=str,
        help="ID of the AI Nano Task Attribute.",
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
        aint_attribute_id, ai_annoation_runs
    )

    # OPTIONAL if you want a specific ai annotation run
    # annoation_run_id = "???????"
    # ai_annotation_run = hari.get_ai_annotation_run(annoation_run_id)

    model_id = ai_annotation_run.ml_annotation_model_id

    # get AINT model for Attribute ID

    # OPTIONAL if you want to get all models
    models = hari.get_aint_models()
    print(f"Found {len(models)} models")

    model = hari.get_aint_model(model_id)
    print(model)

    # get development data for AINT Model
    developement_id = model.training_set_id

    # OPTIONAL if you want to get all development sets
    sets = hari.get_development_sets()
    print(f"Found {len(sets)} development sets")

    development_set = hari.get_development_set(developement_id)
    print(development_set)
