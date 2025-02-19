import argparse
import json
import logging
import math
import statistics
import uuid

import matplotlib.pyplot as plt
import tqdm
from pydantic import BaseModel

from hari_client import Config
from hari_client import HARIClient
from hari_client.models.models import AnnotationResponse
from hari_client.utils.analysis import caluclate_confidence_interval_scores

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic data models for structured data handling
class AnnotatorSummary(BaseModel):
    annotator_name: str
    total_annotations: int
    total_cant_solves: int
    percentage_cant_solves: float
    frequency_answers: dict[str, int]
    distribution_answers: dict[str, float]
    average_duration: float
    total_answered_reference_data: int
    total_correct_reference_data: int
    percentage_correct_reference_data: float


#
# def get_tag_data(dataset_id: str, reference_data_id: str) -> dict:
#     """
#     Fetches tag data by its ID.
#
#     Args:
#         dataset_id : The ID of the dataset.
#         reference_data_id : The ID of the reference data.
#
#     Returns:
#         The tag data.
#     """
#     # Request to fetch tag data
#     endpoint = f"/datasets/{dataset_id}/tags/{reference_data_id}"
#     tag_response = await request_hari(endpoint)
#     return tag_response
#
#


def generate_reference_data_map(dataset_id, subset_id, annotation_run_node_id) -> dict:
    """
    Generates a map of annotation run node IDs to reference data.

    Args:
        annotations : A list of annotations.
        batch_size (optional): Number of annotation run node IDs to fetch per batch. Defaults to 100.

    Returns:
        A map of annotation run node IDs to reference data.
    """
    reference_data_map = {}

    in_subset = {
        "attribute": "subset_ids",
        "query_operator": "in",
        "value": subset_id,
    }

    select_annotation_run_node = {
        "attribute": "annotation_run_node_id",
        "query_operator": "==",
        "value": annotation_run_node_id,
    }

    # TODO expects media objects
    media_objects_of_reference_subset = hari.get_media_objects_paged(
        dataset_id,
        query=json.dumps(in_subset),
        projection={
            "projection[id]": True,
        },
    )
    media_object_ids_of_reference_subset = [
        m.id for m in media_objects_of_reference_subset
    ]
    # TODO no paging , might break for large datasets
    reference_attributes = hari.get_attributes(
        dataset_id, query=json.dumps(select_annotation_run_node)
    )

    # create map annotateable id to expected value
    for attr in reference_attributes:
        if attr.annotatable_id in media_object_ids_of_reference_subset:
            # relevant media objects
            frequency = attr.frequency
            frequency["cant_solve"] = attr.cant_solves

            # Step 1: Find the maximum value in the dictionary
            max_value = max(frequency.values())

            # Step 2: Collect all keys that have this maximum value
            max_keys = [key for key, value in frequency.items() if value == max_value]

            # ensure only one value
            if len(max_keys) == 1:
                # maybe do not allow it since it is ambiguous
                reference_data_map[attr.annotatable_id] = max_keys[0]
            else:
                print(
                    "WARNING: tried to load reference data with ambiguous label which is not allowed @",
                    attr.annotatable_id,
                )

    return reference_data_map


def get_annotator_summary(
    annotator_id: str, annotations: list[AnnotationResponse], reference_data_map: dict
) -> AnnotatorSummary:
    """
    Gets detailed annotation information for a specific annotator.

    Args:
        annotator_id : The ID of the annotator.
        annotations : A list of annotations.
        reference_data_map : A map of reference data.

    Returns:
        Detailed information about the annotator's annotations and summary.
    """
    annotations_list = []
    total_duration = 0
    frequency_answers = {}
    total_answered_reference_data = 0
    total_correct_reference_data = 0

    for annotation in tqdm.tqdm(
        annotations, desc=f"Annotations of Annotator {annotator_id}", unit="annotations"
    ):
        # Convert duration from milliseconds to seconds
        duration_s = annotation.duration_ms / 1000

        # Determine answer and cant_solve flag
        result = annotation.result
        cant_solve = annotation.cant_solve
        answer = result
        if not result and cant_solve:
            answer = "cant_solve"

        # update frequency
        frequency_answers[answer] = frequency_answers.get(answer, 0) + 1

        if annotation.annotatable_id in reference_data_map:
            if reference_data_map[annotation.annotatable_id] == "cant_solve":
                continue  # cant solve
            # found entry
            total_answered_reference_data += 1
            # check correct
            if answer == reference_data_map[annotation.annotatable_id]:
                total_correct_reference_data += 1

        total_duration += duration_s

    # Calculate total annotations and average duration
    total_annotations = len(annotations)
    average_duration = (
        total_duration / total_annotations if total_annotations > 0 else 0
    )

    # Create and return the AnnotatorDetails object
    total_cant_solves = frequency_answers.get("cant_solve", 0)
    return AnnotatorSummary(
        annotator_name=annotator_id,
        total_annotations=total_annotations,
        total_cant_solves=total_cant_solves,
        percentage_cant_solves=float(total_cant_solves) / float(total_annotations)
        if total_annotations > 0
        else 0,
        frequency_answers=frequency_answers,
        distribution_answers={
            k: v / total_annotations if total_annotations > 0 else 0
            for k, v in frequency_answers.items()
        },
        average_duration=average_duration,
        total_answered_reference_data=total_answered_reference_data,
        total_correct_reference_data=total_correct_reference_data,
        percentage_correct_reference_data=total_correct_reference_data
        / total_answered_reference_data
        if total_answered_reference_data > 0
        else 0,
    )


def generate_annotator_analysis(
    dataset_id: uuid.UUID,
    dataset_name: str,
    annotation_run_id: uuid.UUID,
    question: str,
    annotator_details_list: list,
) -> dict:
    """
    Constructs the final report.

    Args:
        dataset_name : The name of the dataset.
        annotator_details_list : A list of annotator details.

    Returns:
        The final report.
    """
    logger.info("Constructing final report...")
    return {
        "annotatorReport": {
            "dataset_id": str(dataset_id),
            "dataset_name": dataset_name,
            "annotation_run_id": str(annotation_run_id),
            "question": question,
            "annotators": [
                details.dict(exclude_none=True) for details in annotator_details_list
            ],
        }
    }


def write_json_report(final_report: dict, dataset_name: str):
    """
    Writes the final report to a JSON file.

    Args:
        final_report : The final report.
        dataset_name : The name of the dataset.
    """
    json_file_name = f"annotator_report_{dataset_name}.json"
    with open(json_file_name, "w", encoding="utf-8") as jsonfile:
        json.dump(final_report, jsonfile, ensure_ascii=False, indent=4)
    print("JSON file created successfully:", json_file_name)


def visualize_annotator_analysis(
    annotator_analysis: dict, columns: int = 4, rows: int = 3
) -> None:
    print("Visualizing annotator report...")
    report = annotator_analysis["annotatorReport"]
    annotators = report["annotators"]
    dataset_name = report["dataset_name"]
    question = report["question"]

    """
        Creates bar plots for each annotator with the following metrics on the x-axis:
          - average_duration
          - percentage_correct_reference_data
          - all keys from distribution_answers
        Overlays aggregated stats (mean, 95% CI, median, outliers) from all annotators.

        :param annotators: List of annotator dictionaries.
        :param columns: Number of columns in the figure grid.
        :param rows: Number of rows in the figure grid.
        """
    # ----------------------------------------------------------------
    # 1) Collect the metric names from the first annotator (or all)
    #    We assume all annotators share the same distribution_answers keys.
    # ----------------------------------------------------------------
    all_distribution_keys = set()
    for ann in annotators:
        dist_answers = ann.get("distribution_answers", {})
        all_distribution_keys.update(dist_answers.keys())

    # Base metrics + distribution keys
    metrics = ["average_duration", "percentage_correct_reference_data"] + sorted(
        list(all_distribution_keys)
    )

    # ----------------------------------------------------------------
    # 2) Gather all values for each metric across all annotators
    #    to compute mean, median, 95% CI, etc.
    # ----------------------------------------------------------------
    # Dictionary: metric_name -> list of values from each annotator
    metric_values = {m: [] for m in metrics}
    for ann in annotators:
        for m in metrics:
            if m in ["average_duration", "percentage_correct_reference_data"]:
                value = ann.get(m, 0.0)  # default 0.0 if missing
            else:
                # distribution_answers
                dist_answers = ann.get("distribution_answers", {})
                value = dist_answers.get(m, 0.0)
            metric_values[m].append(value)

    # Precompute aggregated stats for each metric
    # We'll store: mean, median, std, 95% CI, outliers (if you want them)
    aggregated_stats = {}
    n_annotators = len(annotators)
    for m in metrics:
        vals = metric_values[m]
        mean_val = statistics.mean(vals) if vals else 0.0
        med_val = statistics.median(vals) if vals else 0.0
        std_val = statistics.pstdev(vals) if vals else 0.0  # population stdev
        # For a sample, you might use statistics.stdev(vals)

        # 95% CI => mean ± 1.96 * (std / sqrt(n)) if n > 1
        if n_annotators > 1:
            ci = 1.96 * (std_val / math.sqrt(n_annotators))
        else:
            ci = 0.0

        aggregated_stats[m] = {
            "mean": mean_val,
            "median": med_val,
            "std": std_val,
            "ci_95": ci,
            "values": vals,
        }

    # ----------------------------------------------------------------
    # 3) Plot each annotator's data in subplots of size (rows x columns).
    #    Create a new figure after filling one grid.
    # ----------------------------------------------------------------
    plots_per_figure = rows * columns
    num_annotators = len(annotators)

    # We’ll track how many plots we've made so far
    for idx, ann in enumerate(annotators):
        # If we need a new figure
        if idx % plots_per_figure == 0:
            # If not the first figure, show the previous figure (blocking)
            if idx != 0:
                plt.show()
            fig = plt.figure(figsize=(columns * 5, rows * 4))
            fig.canvas.manager.set_window_title(
                f"Annotator Analysis - {dataset_name} - {question}"
            )

        # Make a subplot with twin y-axis
        subplot_index = (idx % plots_per_figure) + 1
        ax1 = plt.subplot(rows, columns, subplot_index)
        ax2 = ax1.twinx()

        # Separate metrics: "average_duration" vs. the rest (percent)
        duration_metrics = ["average_duration"]
        percentage_metrics = [m for m in metrics if m not in duration_metrics]

        # Collect values for this annotator
        ann_duration_values = []
        ann_percentage_values = []
        uncertainty_values = []

        # side calculations for unceratinta
        total_annotations = ann.get("total_annotations", 0.0)
        total_reference_annotations = ann.get("total_answered_reference_data", 0.0)

        for m in duration_metrics:
            value = ann.get(m, 0.0)
            ann_duration_values.append(value)

        for m in percentage_metrics:
            if m in ["percentage_correct_reference_data"]:
                value = ann.get(m, 0.0)
                ann_percentage_values.append(value * 100.0)
                total = total_reference_annotations
            else:
                # distribution_answers keys are also percentages 0..1 => multiply by 100
                dist_answers = ann.get("distribution_answers", {})
                value = dist_answers.get(m, 0.0)
                ann_percentage_values.append(value * 100.0)
                total = total_annotations

            (
                p_hat,
                p_adjusted,
                ci_lower,
                ci_upper,
                m,
                n,
                invalids,
            ) = caluclate_confidence_interval_scores(
                "", value * total, total, verbose=False
            )
            uncertainty_values.append(
                (p_adjusted * 100.0, (p_adjusted - ci_lower) * 100.0)
            )

        # X-axis indices
        x_positions = range(len(metrics))

        # ----------------------------------------------------------------
        # Plot the bar for the current annotator
        # ----------------------------------------------------------------

        # TODO add uncertainty bars based on total numbers, is important for quality estimation

        x_duration = [0]  # one bar for average_duration
        ax1.bar(
            x_duration,
            ann_duration_values,
            color="skyblue",
            width=0.4,
            label=f"Duration [s]",
        )
        ax1.set_ylabel("Seconds")

        # Plot percentage bars on ax2
        x_percent = range(1, len(percentage_metrics) + 1)
        ax2.bar(
            x_percent,
            ann_percentage_values,
            color="orange",
            width=0.4,
            label=f"Value [%]",
        )
        ax2.set_ylabel("Percent")

        # ----------------------------------------------------------------
        # Overlay the aggregated stats for each metric
        # We'll plot:
        #   - Mean with 95% CI as an error bar
        #   - Median as a small 'x'
        #   - Individual outliers can be shown as points around the mean
        # ----------------------------------------------------------------
        # We artificially offset them horizontally so they don't overlap the bar
        offset = 0.0
        for i, m in enumerate(metrics):
            stats_m = aggregated_stats[m]
            mean_val = stats_m["mean"]
            ci_95 = stats_m["ci_95"]
            median_val = stats_m["median"]
            all_vals = stats_m["values"]

            # Convert percentage values to 0..100
            if m != "average_duration":
                mean_val *= 100.0
                ci_95 *= 100.0
                median_val *= 100.0
                all_vals = [v * 100.0 for v in all_vals]

            # Decide which axis we’re using
            if m == "average_duration":
                x_pos = 0
                axis = ax1
            else:
                x_pos = i  # because distribution metrics start at 1, shift accordingly
                axis = ax2

            offsets_additions = 0.1

            # Plot mean ± 95% CI as error bar
            axis.errorbar(
                x_pos + offsets_additions,  # slide offset
                mean_val,
                yerr=ci_95,
                fmt="o",
                color="darkred",
                capsize=5,
                label=None,
            )

            # plot uncerainty as CI
            if i > 0:
                # draw only for percentages
                axis.errorbar(
                    x_pos - offsets_additions,
                    uncertainty_values[i - 1][0],  # update index
                    yerr=uncertainty_values[i - 1][1],
                    fmt="d",
                    color="darkblue",
                    capsize=5,
                    label=None,
                )

            # Plot median as 'x'
            axis.plot(
                x_pos + offsets_additions,
                median_val,
                marker="x",
                color="green",
                markersize=8,
                label=None,
            )

            # Plot outliers only
            for val in all_vals:
                lower = mean_val - ci_95
                upper = mean_val + ci_95
                if val < lower or val > upper:
                    axis.plot(
                        x_pos + offsets_additions,
                        val,
                        marker=".",
                        color="gray",
                        markersize=5,
                    )

        # ----------------------------------------------------------------
        # Cosmetics and labeling
        # ----------------------------------------------------------------
        ax1.set_title(f"Annotator: {ann.get('annotator_name', 'N/A')}")
        all_metric_labels = ["average_duration"] + percentage_metrics
        xticks_positions = range(len(all_metric_labels))
        ax1.set_xticks(xticks_positions)
        ax1.set_xticklabels(all_metric_labels, rotation=45, ha="right")

        # Avoid repeating legend labels
        # Show legend only on the first subplot of each figure (optional)
        if subplot_index == 1:
            ax1.legend(loc="upper left")
            ax2.legend(loc="upper right")

    # Show the final figure if any subplots remain
    plt.tight_layout()
    plt.show()


def create_annotator_analysis(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    annotation_run_node_id: uuid.UUID,
    reference_subset_id: uuid.UUID | None = None,
    reference_annotation_run_node_id: uuid.UUID | None = None,
    visualize: bool = True,
):
    dataset = hari.get_dataset(dataset_id)
    dataset_name = dataset.name

    query = {
        "attribute": "annotation_run_node_id",
        "query_operator": "==",
        "value": annotation_run_node_id,
    }

    annotations: list[AnnotationResponse] = hari.get_annotations(
        dataset_id=dataset_id, query=json.dumps(query)
    )
    # print(annotations[0])

    if len(annotations) == 0:
        print("ERROR: No annotations found, aborting.")
        return
    question = annotations[0].question

    # Collect unique annotator IDs from annotations
    annotator_ids = {
        ann.annotator.annotator_id
        for ann in tqdm.tqdm(
            annotations, desc="Collecting annotator IDs", unit="annotations"
        )
    }

    # Generate reference data map
    reference_data_map = generate_reference_data_map(
        dataset_id, reference_subset_id, reference_annotation_run_node_id
    )

    # Initialize list to store annotator details
    annotator_summaries = []

    for annotator_id in tqdm.tqdm(
        annotator_ids, desc="Generating report for each annotator"
    ):
        # Filter annotations for the current annotator_id
        annotator_annotations = [
            ann
            for ann in tqdm.tqdm(
                annotations,
                desc=f"Filtering annotator {annotator_id} annotations",
                unit="annotations",
            )
            if ann.annotator.annotator_id == annotator_id
        ]

        # Generate annotator details
        annotator_summary = get_annotator_summary(
            annotator_id, annotator_annotations, reference_data_map
        )

        # Append annotator details to the list
        annotator_summaries.append(annotator_summary)

    # Construct the final report
    analysis_report = generate_annotator_analysis(
        dataset_id, dataset_name, annotation_run_node_id, question, annotator_summaries
    )

    # Write the results to a JSON file
    # TODO optional saving
    write_json_report(analysis_report, dataset_name)

    # Optional: visualize report
    if visualize:
        visualize_annotator_analysis(analysis_report)


def get_annotation_run_node_id_for_attribute_id(
    dataset_id: uuid.UUID, attribute_id: uuid.UUID
):
    query = {
        "attribute": "id",
        "query_operator": "==",
        "value": attribute_id,
    }
    # get attribute values to get annotations and thus linked annotation run
    # TODO check if this works for multi node pipelines
    attributes = hari.get_attribute_values(
        dataset_id=dataset_id, query=json.dumps(query), limit=1
    )
    assert (
        len(attributes) == 1
    ), f"Found no entries for the attribute {attribute_id} in dataset {dataset_id}"
    annotations = attributes[0].annotations
    assert (
        len(annotations) > 0
    ), f"Found no annotations for attribute {attribute_id} in dataset {dataset_id}"
    annotation_id = annotations[0]["annotation_id"]
    annotation = hari.get_annotation(dataset_id, annotation_id)
    annotation_run_node_id = annotation.annotation_run_node_id

    return annotation_run_node_id


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
            dataset_id=dataset_id, attribute_id=attribute_id
        )
    if reference_data_attribute_id is not None:
        reference_data_run_node_id = get_annotation_run_node_id_for_attribute_id(
            dataset_id=dataset_id, attribute_id=reference_data_attribute_id
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
