import argparse
import logging
import uuid

from hari_client import Config
from hari_client import HARIClient
from hari_client.utils.analysis import create_annotator_analysis
from hari_client.utils.analysis import get_annotation_run_node_id_for_attribute_id

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Argument parser setup.
    parser = argparse.ArgumentParser(
        description="Download an annotator report from HARI for a specific annotation run."
    )

    # Add command-line arguments.
    parser.add_argument(
        "--dataset_id",
        type=str,
        help="Dataset ID for which the report should be created",
        required=True,
    )

    parser.add_argument(
        "--annotation_run_node_id",
        type=str,
        help="Annotation Run ID for which the report should be created, Either this ID or Attribute ID need to be specified",
    )

    parser.add_argument(
        "-a",
        "--attribute_id",
        type=str,
        help="Attribute ID for which the report should be created, Either this ID or AnnotationRunNode ID need to be specified",
    )

    parser.add_argument(
        "--reference_data_attribute_id",
        type=str,
        help="Attribute ID which should be used as reference data",
    )

    parser.add_argument(
        "--reference_data_subset_id",
        type=str,
        help="Subset ID for on which the reference data is defined",
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Extract arguments.
    dataset_id: uuid.UUID = args.dataset_id
    annotation_run_node_id: uuid.UUID = args.annotation_run_node_id
    attribute_id: uuid.UUID = args.attribute_id
    reference_data_attribute_id: uuid.UUID = args.reference_data_attribute_id
    reference_data_subset_id: uuid.UUID = (
        args.reference_data_subset_id
    )  # TODO check what happens if empty

    assert (
        annotation_run_node_id is not None or attribute_id is not None
    ), "Either annotation_run_node_id or attribute_id must be specified"

    # load hari client
    config: Config = Config(_env_file=".env")
    hari: HARIClient = HARIClient(config=config)

    # determine if annotation run node id is give or needs to be calculated
    if annotation_run_node_id is None:
        annotation_run_node_id = get_annotation_run_node_id_for_attribute_id(
            hari, dataset_id=dataset_id, attribute_id=attribute_id
        )
    if reference_data_attribute_id is not None:
        reference_data_run_node_id = get_annotation_run_node_id_for_attribute_id(
            hari, dataset_id=dataset_id, attribute_id=reference_data_attribute_id
        )
    else:
        # use same annotation run
        reference_data_run_node_id = annotation_run_node_id

    # used here same annotation run node id for reference but could have been also different one
    # important the node values must match
    create_annotator_analysis(
        hari,
        dataset_id,
        annotation_run_node_id,
        reference_subset_id=reference_data_subset_id,
        reference_annotation_run_node_id=reference_data_run_node_id,
    )
