import json
import math
import statistics
import uuid
from collections import Counter
from os.path import join

import matplotlib.pyplot as plt
import numpy as np
import statsmodels.api as sm
from pydantic import BaseModel
from statsmodels.stats.proportion import proportion_confint
from tqdm import tqdm

from hari_client import HARIClient
from hari_client.models.models import AnnotationResponse
from hari_client.models.models import AttributeGroup
from hari_client.models.models import AttributeMetadataResponse
from hari_client.models.models import AttributeValueResponse
from hari_client.models.models import DataBaseObjectType


def organize_attributes_by_group(
    attributes: list[AttributeValueResponse],
    ID2attribute_meta: dict[str, AttributeMetadataResponse],
) -> tuple[
    dict[AttributeGroup, list[AttributeValueResponse]],
    dict[AttributeGroup, list[AttributeValueResponse]],
]:
    """
    Organize a list of attribute values into two dictionaries, grouped by their attribute group and annotatable type.

    The function distinguishes between media-level attributes (MEDIA) and media object-level attributes (MEDIAOBJECT).
    For each attribute, it looks up its metadata to determine which annotatable type it belongs to, then groups it
    accordingly. It returns two separate dictionaries for media and media objects.

    Args:
        attributes (list[AttributeValueResponse]): A list of attribute values to be grouped.
        ID2attribute_meta (dict[str, AttributeMetadataResponse]): A mapping from metadata ID to its corresponding
            metadata object. Used to determine the annotatable type and group of each attribute.

    Returns:
        tuple[dict[AttributeGroup, list[AttributeValueResponse]], dict[AttributeGroup, list[AttributeValueResponse]]]:
            A tuple containing two dictionaries:
            1. A dictionary mapping AttributeGroup to a list of media-level attributes.
            2. A dictionary mapping AttributeGroup to a list of media object-level attributes.
    """
    # TODO splitting should maybe already happen in collect media and attributes

    group2media_attribute, group2media_object_attribute = {}, {}

    for attr in attributes:
        meta = ID2attribute_meta[attr.metadata_id]
        # get correct return dictionary
        if meta.annotatable_type == DataBaseObjectType.MEDIA:
            group2attribute = group2media_attribute
        elif meta.annotatable_type == DataBaseObjectType.MEDIAOBJECT:
            group2attribute = group2media_object_attribute
        else:
            raise ValueError("Unknown annotatable type")

        group = meta.attribute_group
        if group not in group2attribute:
            group2attribute[group] = [attr]
        else:
            group2attribute[group].append(attr)

    return group2media_attribute, group2media_object_attribute


def find_attribute_id_by_name(
    attribute_name: str,
    attribute_metas: list[AttributeMetadataResponse],
    object_type: DataBaseObjectType = DataBaseObjectType.MEDIAOBJECT,
    attribute_group: AttributeGroup = AttributeGroup.AnnotationAttribute,
) -> str | None:
    """
    Locate the ID of an attribute by name, filtering by object type and attribute group.

    This function searches through a list of attribute metadata to find a match by name. If multiple
    matches are found, it returns the first occurrence and prints a warning. If no match is found, it
    returns None.

    Args:
        attribute_name (str): The name of the attribute to find.
        attribute_metas (list[AttributeMetadataResponse]): A list of attribute metadata objects.
        object_type (DataBaseObjectType, optional): Filter for the annotatable type (media or media object).
            Defaults to MEDIAOBJECT.
        attribute_group (AttributeGroup, optional): Filter for the attribute group. Defaults to
            AnnotationAttribute.

    Returns:
        str | None: The ID of the matching attribute if found; otherwise, None.
    """
    all_questions = [
        attr.name
        for attr in attribute_metas
        if attr.annotatable_type == object_type
        and attr.attribute_group == attribute_group
    ]

    relevant_ids = [
        attr.id
        for attr in attribute_metas
        if attr.annotatable_type == object_type
        and attr.attribute_group == attribute_group
    ]

    counting = all_questions.count(attribute_name)

    if counting == 1:
        return relevant_ids[all_questions.index(attribute_name)]
    elif counting > 1:
        print(
            "WARNING: Attribute name is not unique, first occurrence of attribute name will be returned"
        )
        return relevant_ids[all_questions.index(attribute_name)]
    return None


def create_soft_label_for_annotations(
    attributes: list[AttributeValueResponse],
    attribute_name: str,
    normalize: bool = False,
    combine: bool = False,
    ignore_duplicate: bool = False,
    match_by: str = "id",
    match_by2name: dict[str, str] | None = None,
    additional_result: str | None = None,
) -> (
    dict[str, dict[str, dict[str, float]]]
    | tuple[dict[str, dict[str, dict[str, float]]], dict[str, dict[str, any]]]
):
    """
    Aggregate and combine annotation values to create soft labels or frequency-based labels.

    The function iterates through each attribute, extracting the annotation data under `attribute_name`. It groups
    them by the annotatable ID, and then by a `match_by` value (e.g., the attribute's ID). If `combine`
    is True, duplicate entries are merged by summing frequency counts. If `normalize` is True, each set of frequency
    counts is converted into a probability distribution. The user can also retrieve an additional result field from
    each attribute by specifying `additional_result`.

    Args:
        attributes (list[AttributeValueResponse]): A list of attribute value responses from which to aggregate data.
        attribute_name (str): The field name in each attribute value that contains the data to be aggregated.
        normalize (bool, optional): Whether to normalize each frequency distribution into a probability distribution.
            Defaults to False.
        combine (bool, optional): Whether to combine (sum) data for duplicate `match_by` entries. Defaults to False.
        ignore_duplicate (bool, optional): If False and duplicates exist without `combine`, prints a warning.
            Defaults to False.
        match_by (str): The attribute field to match on, e.g., 'id'. Defaults to 'id'.
        match_by2name: Optional dictionary which describes how the match by value should be mapped. E.g. map ids to readable version
        additional_result (str | None, optional): If specified, also retrieve and store data from this field.
            Defaults to None.

    Returns:
        dict[str, dict[str, dict[str, float]]] or tuple of:
            - (1) A nested dictionary keyed by annotatable ID, then keyed by the `match_by` value or the `match_by2name` entry if applicable.,
              mapping to a dict of {possible_label: frequency or probability}.
            - (2) If `additional_result` is specified, returns a tuple where the second element
              is a similarly nested dictionary capturing the additional data.
    """
    annotatableID2attributes = {}
    annotatableID2additional = {}

    for attr in attributes:
        if getattr(attr, attribute_name, None) is None:
            print(f"WARNING: {attribute_name} not found in {attr}")
            continue  # skip non defined attributes and questions

        if (additional_result is not None) and (
            getattr(attr, additional_result) is None
        ):
            print(
                f"WARNING: You specified the additional value {additional_result} for {attr} but it is not defined in the attribute"
            )

        # check if annotatable id is already used
        annotatable_id = attr.annotatable_id
        if annotatable_id not in annotatableID2attributes:
            annotatableID2attributes[annotatable_id] = {}
            annotatableID2additional[annotatable_id] = {}

        # add value of frequencies or could already be soft label
        queried_values = getattr(attr, attribute_name)
        match_by_value = getattr(attr, match_by)

        if match_by2name is not None:
            mapped_match_by_value = match_by2name.get(match_by_value, match_by_value)
        else:
            mapped_match_by_value = match_by_value

        # check for missing can not solve
        if "cant_solve" not in queried_values:
            queried_values["cant_solve"] = (
                attr.cant_solves if attr.cant_solves else 0
            )  # make sure default value is 0

        # Check for duplicates
        if mapped_match_by_value in annotatableID2attributes[annotatable_id]:
            if not combine:
                if not ignore_duplicate:
                    print(
                        f"Warning: duplicate for {mapped_match_by_value} @ {annotatable_id}"
                    )
                    print(
                        annotatableID2attributes[annotatable_id][mapped_match_by_value]
                    )
                    print(queried_values)
            else:
                # combine frequencies
                old_frequencies = annotatableID2attributes[annotatable_id][
                    mapped_match_by_value
                ]
                for key, value in old_frequencies.items():
                    # Add the value to the existing key or initialize it
                    queried_values[key] = queried_values.get(key, 0) + value

                if additional_result is not None:
                    print(
                        f"WARNING: you specified an additional result which can not be combined, latest value is reported"
                    )

        # write back
        annotatableID2attributes[annotatable_id][mapped_match_by_value] = queried_values
        if additional_result is not None:
            annotatableID2additional[annotatable_id][mapped_match_by_value] = getattr(
                attr, additional_result
            )

    # Optionally normalize frequencies
    if normalize:
        # use this if the values are actually frequencies of proper soft labels
        for annotatable_id in annotatableID2attributes:
            for matching_key in annotatableID2attributes[annotatable_id]:
                queried_values = annotatableID2attributes[annotatable_id][matching_key]
                total = sum(queried_values.values())
                queried_values = {
                    key: value / total for key, value in queried_values.items()
                }
                annotatableID2attributes[annotatable_id][matching_key] = queried_values

    if additional_result is not None:
        return annotatableID2attributes, annotatableID2additional
    else:
        return annotatableID2attributes


def compute_accuracy(Q: dict[str, float], P: dict[str, float]) -> float:
    """
    Compute a binary accuracy metric by comparing the class with the highest probability in Q
    to that in P.

    Args:
        Q (dict[str, float]): A mapping of class labels to their probabilities (prediction).
        P (dict[str, float]): A mapping of class labels to their probabilities (ground truth).

    Returns:
        float: 1.0 if the predicted class (argmax of Q) matches the true class (argmax of P),
               otherwise 0.0.
    """
    pred_class = max(Q, key=Q.get)
    true_class = max(P, key=P.get)
    return 1.0 if pred_class == true_class else 0.0


def update_mapping(
    annotations: dict[str, float],
    mapping: dict[str, str],
) -> dict[str, float]:
    """
    Remap the class labels of an annotation dictionary based on a provided mapping.

    This function is particularly useful if class labels need to be merged or renamed. For example,
    if multiple classes should be combined into a single class label, the mapping should direct them
    to the same key.

    Args:
        annotations (dict[str, float]): A mapping of class labels to their associated values (e.g., frequencies).
        mapping (dict[str, str]): A dictionary mapping old class labels to new labels.

    Returns:
        dict[str, float]: A new dictionary containing the annotations re-labeled based on the mapping.
    """
    new_annotations = {}
    for class_label, value in annotations.items():
        mapped_class = mapping[class_label]
        new_annotations[mapped_class] = new_annotations.get(mapped_class, 0) + value
    return new_annotations


def calculate_ml_human_alignment(
    annotatableID2annotation: dict[str, dict[str, dict[str, float]]],
    annotatableID2mlannotation: dict[str, dict[str, dict[str, float]]],
    attribute_key: str,
    human_attribute_key: str,
    human_mapping: dict[str, str] | None = None,
    ml_mapping: dict[str, str] | None = None,
    selected_subset_ids: list[str] = [],
    ID2subsets: dict[str, list[str]] | None = None,
    confidence_threshold: float = -1,
    ID2confidence: dict[str, dict[str, float]] | None = None,
) -> dict[str, list[float]] | None:
    """
    Calculate the alignment (accuracy and KL divergence) between machine-learning predictions and human annotations.

    The function iterates over the IDs in `annotatableID2annotation`, optionally filters them by subsets and confidence,
    and compares the model's soft-label distribution (`attribute_key`) with the human distribution (`human_attribute_key`).
    It calculates overall accuracy and KL divergence for each matching pair, storing these metrics in the `scores` dict.
    Additionally, it computes precision metrics per predicted class.

    Args:
        annotatableID2annotation (dict[str, dict[str, dict[str, float]]]): A nested dictionary of IDs to
            {human_attribute_key: {class_label: probability or frequency}}.
        annotatableID2mlannotation (dict[str, dict[str, dict[str, float]]]): A nested dictionary of IDs to
            {attribute_key: {class_label: probability or frequency}} for ML predictions.
        attribute_key (str): The key under which ML annotations are stored.
        human_attribute_key (str): The key under which human annotations are stored.
        human_mapping (dict[str, str] | None, optional): Mapping for human annotations to unify or rename classes.
            Defaults to None.
        ml_mapping (dict[str, str] | None, optional): Mapping for ML annotations to unify or rename classes.
            Defaults to None.
        selected_subset_ids (list[str], optional): A list of subset IDs to filter which annotations to evaluate.
            Defaults to an empty list.
        ID2subsets (dict[str, list[str]] | None, optional): A dictionary mapping IDs to their subset IDs,
            required if `selected_subset_ids` is non-empty. Defaults to None.
        confidence_threshold (float, optional): A minimum confidence level required to consider an ID for evaluation.
            If set to a non-negative value, `ID2confidence` must not be None. Defaults to -1.
        ID2confidence (dict[str, dict[str, float]] | None, optional): A dictionary mapping IDs to confidence values
            {attribute_key: confidence}. Required if `confidence_threshold >= 0`. Defaults to None.

    Returns:
        dict[str, list[float]] | None: A dictionary containing lists of accuracy ("acc") and KL divergence ("kl")
            values, plus precision metrics for each predicted class. If no common annotations are found, returns None.
    """
    # Validate subset usage
    assert (
        len(selected_subset_ids) == 0 or ID2subsets is not None
    ), "ID2subsets must be given if subsets as filtering are specified"
    assert (
        confidence_threshold < 0 or ID2confidence is not None
    ), "ID2confidence must be given if confidence is specified for filtering"

    # Validate confidence usage
    scores = {
        "acc": [],
        "kl": [],
    }

    for annotatable_id in tqdm(annotatableID2annotation):
        # If using subset filtering, skip IDs not in the selected subsets
        if len(selected_subset_ids) > 0:
            found = False
            for subset_id in ID2subsets[annotatable_id]:
                if subset_id in selected_subset_ids:
                    found = True
                    break
            # do not continue with this id if not specified
            if not found:
                continue

        if annotatable_id in annotatableID2mlannotation:
            ml_annotations = annotatableID2mlannotation[annotatable_id].get(
                attribute_key, {}
            )
            human_annotations = annotatableID2annotation[annotatable_id].get(
                human_attribute_key, {}
            )

            if len(ml_annotations) == 0 or len(human_annotations) == 0:
                # not found key, no matching possible
                continue

            # check if relevant with regard to confidence
            if confidence_threshold >= 0:
                conf = ID2confidence[annotatable_id][attribute_key]
                if conf < confidence_threshold:
                    continue

            # change mapping:
            if human_mapping is not None:
                human_annotations = update_mapping(human_annotations, human_mapping)
            if ml_mapping is not None:
                ml_annotations = update_mapping(ml_annotations, ml_mapping)

            # acc
            scores["acc"].append(compute_accuracy(ml_annotations, human_annotations))
            # KL Divergence
            scores["kl"].append(kl_divergence(ml_annotations, human_annotations))
            # acc per class
            # expected_class = max(human_annotations, key=human_annotations.get) # this would be recall
            predicted_class = max(ml_annotations, key=ml_annotations.get)
            if "precision_" + predicted_class not in scores:
                scores["precision_" + predicted_class] = []
            scores["precision_" + predicted_class].append(
                compute_accuracy(ml_annotations, human_annotations)
            )

    print(
        f"annotations with human/ml/ both(filtered) annotations: "
        f"{sum([human_attribute_key in values for values in annotatableID2annotation.values()])}/"
        f"{sum([attribute_key in values for values in annotatableID2mlannotation.values()])}/"
        f"{len(scores['acc'])} "
    )
    if len(scores["acc"]) == 0:
        # No entries available for analysis
        return

    # Summarize results, average across values
    for key, values in scores.items():
        if key.startswith("kl"):
            print(
                f"{key}: {np.mean(values):0.02f} +- {np.std(values):0.02f}, median {np.median(values):0.02f} #{len(values)}"
            )
        if "acc" in key or "precision" in key:
            # add confidence estimations
            caluclate_confidence_interval_scores(f"{key} -> ", sum(values), len(values))

    return scores


def caluclate_confidence_interval_scores(
    score_name: str,
    m: float,
    n: int,
    invalids: int = 0,
    confidence: float = 0.95,
    verbose: bool = True,
) -> tuple[float, float, float, float, float, int, int]:
    """
    Compute a confidence interval for a proportion (m out of n), using the Wilson score interval.

    This function prints the interval range if `verbose` is True. It returns a tuple containing
    the observed proportion, the adjusted proportion, and the lower/upper bounds of the interval,
    as well as the total counts.

    Args:
        score_name (str): A label for the score or metric being analyzed (e.g., 'acc').
        m (float): The sum or count of "successes" (e.g., number of correct predictions).
        n (int): The total number of trials or items.
        invalids (int, optional): The number of invalid samples to subtract from n. Defaults to 0.
        confidence (float, optional): The desired confidence level. Currently supports 0.95. Defaults to 0.95.
        verbose (bool, optional): If True, prints the interval results. Defaults to True.

    Returns:
        tuple[float, float, float, float, float, int, int]:
            - p_hat (float): The raw proportion (m / (n - invalids)).
            - p_adjusted (float): The Wilson score-adjusted proportion.
            - ci_lower (float): The lower bound of the confidence interval.
            - ci_upper (float): The upper bound of the confidence interval.
            - m (float): The count of successes (same as input).
            - n (int): The adjusted total trials (n - invalids).
            - invalids (int): The number of invalid samples.
    """

    n_original = n
    n = n - invalids

    # z value
    # Dictionary of z-values for common confidence levels
    confidence_to_z = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.575,
        # Add more if desired
    }
    if confidence in confidence_to_z:
        z = confidence_to_z[confidence]
    else:
        raise ValueError(
            f"Unsupported confidence level {confidence}. "
            f"Supported values are: {list(confidence_to_z.keys())}"
        )

    # safe guard for n == 0
    if n == 0:
        return 0.5, 0.5, 0, 1, m, n, invalids

    # calculate observed rate
    p_hat = m / n
    p_adjusted = (p_hat + (pow(z, 2) / (2 * n))) / (
        1 + (pow(z, 2) / n)
    )  # based on wilson

    alpha = 1 - confidence
    ci_lower, ci_upper = sm.stats.proportion_confint(m, n, alpha=alpha, method="wilson")
    if verbose:
        print(
            f"{score_name} {p_hat*100:0.02f}% , conf {p_adjusted*100:0.02f}% [{ci_lower*100:.2f}%, {ci_upper*100:.2f}%], m: {int(m):d}, n: {int(n):d}, invalid: {invalids:d}"
        )
    return p_hat, p_adjusted, ci_lower, ci_upper, m, n, invalids


def kl_divergence(
    Q: dict[str, float],
    P: dict[str, float],
) -> float:
    """
    Compute the Kullback-Leibler (KL) divergence between two distributions P and Q.

    KL divergence measures how one probability distribution diverges from a second, reference
    probability distribution. It is non-negative and is zero only if P and Q are the same
    distribution almost everywhere.

    Args:
        Q (dict[str, float]): The predicted distribution, keyed by class label.
        P (dict[str, float]): The true distribution, keyed by class label.

    Returns:
        float: The KL divergence value. A smaller value indicates less divergence.
    """
    epsilon = 1e-10
    kl_div = 0.0
    for key in P:
        p = P[key] + epsilon
        q = Q.get(key, epsilon) + epsilon
        kl_div += p * np.log(p / q)
    return kl_div


def calculate_cutoff_thresholds(
    annotatableID2annotation: dict[str, dict[str, dict[str, float]]],
    annotatableID2mlannotation: dict[str, dict[str, dict[str, float]]],
    annotatableID2confidence: dict[str, dict[str, float]],
    key: str,
    annotatableID2subsets: dict[str, list[str]],
    validation_subset_id: str,
    test_subset_id: str,
    use_per_classList: list[bool] = [True, False],
    correctness_thresholdList: list[float] = [0.99, 0.95],
    human_key: str | None = None,
    visualize: bool = False,
) -> dict[str, tuple[float, float]]:
    """
    Compute confidence cutoff thresholds for a given annotation key using a validation subset.

    This function calculates an automation-degree vs. correctness (ADC) curve by sorting items
    by confidence in descending order. It then determines a confidence threshold for various
    correctness levels, optionally handling per-class accuracy if `use_per_classList` includes True.
    The function can also plot the ADC curve if `visualize` is True.

    Args:
        annotatableID2annotation (dict[str, dict[str, dict[str, float]]]): Ground truth annotations,
            keyed by annotatable ID.
        annotatableID2mlannotation (dict[str, dict[str, dict[str, float]]]): ML predictions, keyed
            by annotatable ID.
        annotatableID2confidence (dict[str, dict[str, float]]): Per-annotatable ID confidence values,
            keyed by the attribute key (e.g., `key`).
        key (str): The attribute key (model prediction) for which to compute thresholds.
        annotatableID2subsets (dict[str, list[str]]): A dictionary mapping annotatable IDs to
            their subset IDs.
        validation_subset_id (str): The subset ID used for validation.
        test_subset_id (str): The subset ID used for testing (not explicitly used in the code snippet).
        use_per_classList (list[bool], optional): A list indicating whether to compute thresholds
            per class or overall. Defaults to [True, False].
        correctness_thresholdList (list[float], optional): A list of correctness thresholds for
            determining the cutoff. Defaults to [0.99, 0.95].
        human_key (str | None, optional): If specified, overrides `key` for the ground truth.
            Defaults to None.
        visualize (bool, optional): If True, plots the ADC curve. Defaults to False.

    Returns:
        dict[str, tuple[float, float]]:
            A dictionary keyed by a combination of `use_per_class` and `correctness_threshold`,
            mapping to a tuple of:
            (confidence_threshold, automation_degree), where `automation_degree` is the fraction
            of items processed before the threshold is reached.

            Example key format: "True$0.9900" -> (confidence_threshold, automation_degree)
    """
    # calculate ADC curve
    ml_annotations, human_annotations, confidences = [], [], []
    for annotatable_id in tqdm(annotatableID2annotation):
        # check if validation
        if validation_subset_id not in annotatableID2subsets[annotatable_id]:
            continue

        if annotatable_id in annotatableID2mlannotation:
            ml_annotation = annotatableID2mlannotation[annotatable_id].get(key, {})
            human_annotation = annotatableID2annotation[annotatable_id].get(
                key if human_key is None else human_key, {}
            )

            if len(ml_annotation) == 0 or len(human_annotation) == 0:
                # not found key, no matching possible
                continue

            ml_annotations.append(ml_annotation)
            human_annotations.append(human_annotation)
            confidences.append(annotatableID2confidence[annotatable_id][key])

    cutoff_thresholds = {}
    if len(confidences) > 0:
        # calculate is correct:
        isCorrect = [
            compute_accuracy(ml_anno, human_anno)
            for ml_anno, human_anno in zip(ml_annotations, human_annotations)
        ]
        isGTLabel = [
            max(human_anno, key=human_anno.get) for human_anno in human_annotations
        ]
        labels = list(set(isGTLabel))

        # print(isCorrect, confidences)

        # sort by confidences by zipping and unzipping
        combined = sorted(
            zip(confidences, isCorrect, isGTLabel), reverse=True
        )  # sort in descending order
        confidences, isCorrect, isGTLabel = zip(*combined)

        # calculate curve
        num_points = len(isCorrect)
        adc = {
            i / num_points: sum(isCorrect[: i + 1]) / (i + 1)
            for i in range(num_points + 1)
        }
        # per class
        isLabelPerClass = {
            label: [1 if gtLabel == label else 0 for gtLabel in isGTLabel]
            for label in labels
        }
        isCorrectPerClass = {
            label: [
                min(correct, isLabel)
                for correct, isLabel in zip(isCorrect, isLabelPerClass[label])
            ]
            for label in labels
        }
        adc_per_class = {
            label: {
                i
                / num_points: (
                    sum_correct / sum_label
                    if (sum_label := sum(isLabelPerClass[label][: i + 1])) != 0
                    else 1
                )
                for i in range(num_points + 1)
                if (sum_correct := sum(isCorrectPerClass[label][: i + 1]))
                is not None  # Use sum_correct for calculation
            }
            for label in labels
        }

        # calculate cut off confidences
        for use_per_class in use_per_classList:
            if use_per_class:
                adcs = list(adc_per_class.values())
            else:
                adcs = [adc]
            automation_degrees = list(adcs[0].keys())

            for correctnes_threshold in correctness_thresholdList:
                confidence_threshold = confidences[-1]
                last_ad = 1
                for i, ad in enumerate(automation_degrees):
                    # if threshold is not valid for any of the adcs at the specified ad break
                    isBelowThreshold = [adc[ad] < correctnes_threshold for adc in adcs]

                    if any(isBelowThreshold):
                        last_ad = automation_degrees[max(0, i - 1)]
                        # print(last_ad)
                        confidence_threshold = confidences[int(last_ad * num_points)]
                        break

                # save threshold
                cutoff_thresholds[f"{use_per_class}${correctnes_threshold:0.04f}"] = (
                    confidence_threshold,
                    last_ad,
                )

        if visualize:
            # print("ADC: ", adc)
            # visualize
            colors = [
                "lightcoral",
                "lightgreen",
                "lightsalmon",
                "lightpink",
                "lightseagreen",
                "lightsteelblue",
                "lightgoldenrodyellow",
                "lightcyan",
                "lightgray",
            ]

            # Create a  plot
            keys, values = list(adc.keys()), list(adc.values())
            plt.plot(keys, values, color="lightblue", linestyle="--", label="All")
            for i, label in enumerate(labels):
                plt.plot(
                    list(adc_per_class[label].keys()),
                    list(adc_per_class[label].values()),
                    color=colors[i],
                    linestyle="--",
                    label=label,
                )

            # Labels and title
            plt.xlabel("Automation Degree")
            plt.ylabel("Correctness")
            plt.title("ADC")
            plt.legend()

            # Show plot
            plt.show()

    return cutoff_thresholds


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


def generate_reference_data_map(
    hari, dataset_id, subset_id, annotation_run_node_id
) -> dict:
    """
    Generates a map of annotation run node IDs to reference data.

    Args:
        annotations : A list of annotations.
        batch_size (optional): Number of annotation run node IDs to fetch per batch. Defaults to 100.

    Returns:
        A map of annotation run node IDs to reference data.
    """
    reference_data_map = {}

    assert annotation_run_node_id is not None, "Annotation Run Node ID not specified"
    assert subset_id is not None, "Subset ID not specified"

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

    for annotation in tqdm(
        annotations, desc=f"Annotations of Annotator {annotator_id}"
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
    print("Constructing final report...")
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


def write_json_report(final_report: dict, output_directory: str, output_name: str):
    """
    Writes the final report to a JSON file.

    Args:
        final_report : The final report.
        output_name : The name of the dataset.
    """
    json_file_name = f"annotator_report_{output_name}.json"
    with open(
        join(output_directory, json_file_name), "w", encoding="utf-8"
    ) as jsonfile:
        json.dump(final_report, jsonfile, ensure_ascii=False, indent=4)
    print("JSON file created successfully:", join(output_directory, json_file_name))


def visualize_annotator_analysis(
    annotator_analysis: dict,
    columns: int = 4,
    rows: int = 3,
    output_directory: str = None,
    output_name: str = None,
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

    # index for counting annotation reports
    popup_window_counter = 0

    # We’ll track how many plots we've made so far
    for idx, ann in enumerate(annotators):
        # If we need a new figure
        if idx % plots_per_figure == 0:
            # If not the first figure, show the previous figure (blocking)
            if idx != 0:
                if output_directory is None:
                    plt.show()
                else:
                    plt.savefig(
                        join(
                            output_directory,
                            f"annotator_report_{output_name}_{popup_window_counter}.png",
                        )
                    )
                popup_window_counter += 1
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
    if output_directory is None:
        plt.show()
    else:
        plt.savefig(
            join(
                output_directory,
                f"annotator_report_{output_name}_{popup_window_counter}.png",
            )
        )

    plt.close()


def create_annotator_analysis(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    annotation_run_node_id: uuid.UUID,
    reference_subset_id: uuid.UUID | None = None,
    reference_annotation_run_node_id: uuid.UUID | None = None,
    visualize: bool = True,
    output_name: str = None,
    output_directory: str = None,
):
    dataset = hari.get_dataset(dataset_id)
    dataset_name = dataset.name

    if output_name is None:
        output_name = dataset_name

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
        for ann in tqdm(annotations, desc="Collecting annotator IDs")
    }

    # Generate reference data map
    if reference_subset_id is None or reference_annotation_run_node_id is None:
        reference_data_map = {}
    else:
        reference_data_map = generate_reference_data_map(
            hari, dataset_id, reference_subset_id, reference_annotation_run_node_id
        )

    # Initialize list to store annotator details
    annotator_summaries = []

    for annotator_id in tqdm(
        annotator_ids, desc="Generating report for each annotator"
    ):
        # Filter annotations for the current annotator_id
        annotator_annotations = [
            ann
            for ann in tqdm(
                annotations,
                desc=f"Filtering annotator {annotator_id} annotations",
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
    if output_directory is not None:
        write_json_report(analysis_report, output_directory, output_name)

    # Optional: visualize report
    if visualize:
        visualize_annotator_analysis(
            analysis_report, output_directory=output_directory, output_name=output_name
        )


def get_annotation_run_node_id_for_attribute_id(
    hari, dataset_id: uuid.UUID, attribute_id: uuid.UUID
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


def plot_histogram_with_wilson_ci(
    name, data: list, number_of_buckets=-1, output_directory=None
):
    """
    Plots a histogram of percentages with 95% Wilson confidence intervals
    (centered at the midpoint of the CI).

    - If number_of_buckets == -1, treats 'data' as discrete
      and plots one bar per unique value.
    - Otherwise, divides the data into 'number_of_buckets' bins
      (assumed in [0, 1], but can be adjusted below).
    """
    data = np.array([d for d in data if d is not None])  # filter out Nones
    n = len(data)
    if n == 0:
        print("No data to plot.")
        return

    # Helper function to get Wilson interval for k out of n
    def wilson_interval(k, n, alpha=0.05):
        # returns (ci_lower, ci_upper) in fraction form (0..1)
        return proportion_confint(count=k, nobs=n, alpha=alpha, method="wilson")

    # Decide how to group data
    if number_of_buckets == -1:
        # ----- Discrete Data -----
        counter = Counter(data)
        values = sorted(counter.keys())
        counts = np.array([counter[v] for v in values])
    else:
        # ----- Binned Data -----
        num_bins = number_of_buckets
        counts, bin_edges = np.histogram(
            data, bins=num_bins, range=(np.min(data), np.max(data))
        )
        # Use bin centers to represent each bin
        values = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        counts = np.array(counts)

    # Calculate fraction of total for each unique value/bin
    fractions = counts / n

    # Wilson confidence intervals (in fraction)
    ci_lower = []
    ci_upper = []
    for k in counts:
        low, up = wilson_interval(k, n, alpha=0.05)
        ci_lower.append(low)
        ci_upper.append(up)

    # Convert fractions & intervals to percentage
    fractions_pct = fractions * 100
    ci_lower_pct = np.array(ci_lower) * 100
    ci_upper_pct = np.array(ci_upper) * 100

    # Center the bar at the midpoint of the CI, not necessarily at fractions_pct
    # Because Wilson intervals may not be symmetric around the raw proportion
    ci_mid = 0.5 * (ci_lower_pct + ci_upper_pct)

    # Error is difference from center
    y_err_lower = ci_mid - ci_lower_pct
    y_err_upper = ci_upper_pct - ci_mid

    # ----- Plot -----
    plt.figure(figsize=(8, 5))
    value_offset = 0.0

    if number_of_buckets == -1:
        # Discrete: bar positions are integer indices
        x_positions = np.arange(len(values))
        plt.bar(x_positions, fractions_pct, color="skyblue", edgecolor="black")
        for x, y in zip(x_positions, fractions_pct):
            plt.text(x + value_offset, y + value_offset, f"{y:.2f}%")
        plt.errorbar(
            x_positions,
            ci_mid,
            yerr=[y_err_lower, y_err_upper],
            fmt="none",
            ecolor="red",
            capsize=5,
            label="95% Wilson CI",
        )
        plt.xticks(x_positions, values)
        plt.xlabel("Discrete Values")
    else:
        # Binned: bar positions at bin centers
        bar_width = (bin_edges[1] - bin_edges[0]) * 0.8
        plt.bar(
            values,
            fractions_pct,
            width=bar_width,
            color="skyblue",
            edgecolor="black",
            align="center",
        )
        for x, y in zip(values, fractions_pct):
            plt.text(x + value_offset, y + value_offset, f"{y:.2f}%")
        plt.errorbar(
            values,
            ci_mid,
            yerr=[y_err_lower, y_err_upper],
            fmt="none",
            ecolor="red",
            capsize=5,
            label="95% Wilson CI",
        )
        plt.xlabel("Value Range (binned)")

    plt.ylabel("Percentage of Data (%)")
    plt.title(f"Histogram of {name}")
    plt.legend()
    plt.tight_layout()
    if output_directory is not None:
        plt.savefig(join(output_directory, f"{name}.png"))
    else:
        plt.show()


def histograms_for_nanotask(
    ID2annotation,
    ID2ambiguity,
    attribute_id,
    ID2groupby_value={},
    groupy_name=None,
    groupby_values=None,
    output_directory=None,
):
    # Ensure is called at least once
    if groupby_values is None:
        groupby_values = [None]

    for groupby_value in groupby_values:
        groupby_naming = (
            ""
            if groupby_value is None
            else f" grouped by {groupy_name}={groupby_value}"
        )

        # majority vote class histogram
        plot_histogram_with_wilson_ci(
            "Majority Vote Classification" + groupby_naming,
            [
                max(
                    soft_label_dict[attribute_id], key=soft_label_dict[attribute_id].get
                )
                if attribute_id in soft_label_dict
                else None
                for media_object_id, soft_label_dict in ID2annotation.items()
                if ID2groupby_value.get(media_object_id, None) == groupby_value
            ],
            number_of_buckets=-1,
            output_directory=output_directory,
        )

        # ambiguity histogram
        plot_histogram_with_wilson_ci(
            "Ambiguity" + groupby_naming,
            [
                ambiguity_dict.get(attribute_id, None)
                for media_object_id, ambiguity_dict in ID2ambiguity.items()
                if ID2groupby_value.get(media_object_id, None) == groupby_value
            ],
            number_of_buckets=10,
            output_directory=output_directory,
        )

        # per class soft distribution
        ## calculate possible classes
        class_labels = None
        for media_object_id, soft_label_dict in ID2annotation.items():
            if attribute_id in soft_label_dict:
                # found one ID with labels
                class_labels = list(soft_label_dict[attribute_id].keys())
                break
            # else continue

        if class_labels is None:
            print("WARNING: No entries for attribute_id ", attribute_id)
        else:
            ## plot histogram per class
            for class_label in class_labels:
                plot_histogram_with_wilson_ci(
                    f"Soft Label for {class_label}" + groupby_naming,
                    [
                        soft_label_dict.get(attribute_id, {}).get(class_label, None)
                        for media_object_id, soft_label_dict in ID2annotation.items()
                        if ID2groupby_value.get(media_object_id, None) == groupby_value
                    ],
                    number_of_buckets=10,
                    output_directory=output_directory,
                )
