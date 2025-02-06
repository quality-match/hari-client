import matplotlib.pyplot as plt
import numpy as np
import statsmodels.api as sm
from tqdm import tqdm

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

        assert (additional_result is None) or (
            getattr(attr, additional_result) is not None
        ), f"You specified the additional value {additional_result} for {attr} but it is not defined in the attribute"

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
