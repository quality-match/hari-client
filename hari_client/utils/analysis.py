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
):
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
    attribute_name,
    normalize=False,
    combine=False,
    ignore_duplicate=False,
    match_by="id",
    additional_result=None,
):
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

        # check for missing can not solve
        if "cant_solve" not in queried_values:
            queried_values["cant_solve"] = (
                attr.cant_solves if attr.cant_solves else 0
            )  # make sure default value is 0

        # print(match_by_value, queried_values)

        # existing value
        if match_by_value in annotatableID2attributes[annotatable_id]:
            if not combine:
                if not ignore_duplicate:
                    print(f"Warning: duplicate for {match_by_value} @ {annotatable_id}")
                    print(annotatableID2attributes[annotatable_id][match_by_value])
                    print(queried_values)
            else:
                # combine frequencies
                old_frequencies = annotatableID2attributes[annotatable_id][
                    match_by_value
                ]
                for key, value in old_frequencies.items():
                    # Add the value to the existing key or initialize it
                    queried_values[key] = queried_values.get(key, 0) + value

                if additional_result is not None:
                    print(
                        f"WARNING: you specified an additional result which can not be combined, latest value is reported"
                    )

        # write back
        annotatableID2attributes[annotatable_id][match_by_value] = queried_values
        if additional_result is not None:
            annotatableID2additional[annotatable_id][match_by_value] = getattr(
                attr, additional_result
            )

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


def compute_accuracy(Q, P):
    pred_class = max(Q, key=Q.get)
    true_class = max(P, key=P.get)
    accuracy = 1.0 if pred_class == true_class else 0.0
    return accuracy


def update_mapping(annotations, mapping):
    new_annotations = {}
    for class_label, value in annotations.items():
        mapped_class = mapping[class_label]
        new_annotations[mapped_class] = new_annotations.get(mapped_class, 0) + value
    return new_annotations


def calculate_ml_human_alignment(
    annotatableID2annotation,
    annotatableID2mlannotation,
    attribute_key,
    human_attribute_key,
    human_mapping=None,
    ml_mapping=None,
    selected_subset_ids=[],
    ID2subsets=None,
    confidence_threshold=-1,
    ID2confidence=None,
):
    # print("#calculation human / ml alignment")

    assert (
        len(selected_subset_ids) == 0 or ID2subsets is not None
    ), "ID2subsets must be given if subsets as filtering are specified"
    assert (
        confidence_threshold < 0 or ID2confidence is not None
    ), "ID2confidence must be given if confidence is specified for filtering"

    scores = {
        # 'ce': [],
        "acc": [],
        "kl": [],
    }
    # for label in labels:
    #     scores["acc_" + label] = []
    for annotatable_id in tqdm(annotatableID2annotation):
        # check if relevant with regard to subset
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

            # print(ml_annotations, human_annotations)

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

            # ce
            # scores['ce'].append(compute_calbiration_error(ml_annotations, human_annotations))
            # acc
            scores["acc"].append(compute_accuracy(ml_annotations, human_annotations))
            # kl
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
        # no entries
        return

    # average results
    for key, values in scores.items():
        # print(f"{key}: {np.mean(values):0.02f} +- {np.std(values):0.02f}, median {np.median(values):0.02f} #{len(values)}")
        if "acc" in key or "precision" in key:
            # add confidence estimations
            caluclate_confidence_interval_scores(
                f"{key} -> confidence", sum(values), len(values)
            )


def caluclate_confidence_interval_scores(score_name, m, n, invalids=0, confidence=0.95):
    """
    based on wilson
    :param score_name:
    :param m:
    :param n:
    :param confidence:
    :return:
    """

    n_original = n
    n = n - invalids

    # z value
    if confidence == 0.95:
        z = 1.96
    else:
        raise ValueError("z not defined for confidence of ", confidence)

    # calculate observed rate
    p_hat = m / n
    p_adjusted = (p_hat + (pow(z, 2) / (2 * n))) / (
        1 + (pow(z, 2) / n)
    )  # based on wilson

    alpha = 1 - confidence
    ci_lower, ci_upper = sm.stats.proportion_confint(m, n, alpha=alpha, method="wilson")
    print(
        f"{score_name}: {p_hat*100:0.02f}% , conf {p_adjusted*100:0.02f}% [{ci_lower*100:.2f}%, {ci_upper*100:.2f}%], m: {int(m):d}, n: {int(n):d}, invalid: {invalids:d}"
    )


def kl_divergence(Q, P):
    # print(Q,P)
    epsilon = 1e-10
    kl_div = 0.0
    for key in P:
        p = P[key] + epsilon
        q = Q.get(key, epsilon) + epsilon
        kl_div += p * np.log(p / q)
    return kl_div


def calculate_cutoff_thresholds(
    annotatableID2annotation,
    annotatableID2mlannotation,
    annotatableID2confidence,
    key,
    annotatableID2subsets,
    validation_subset_id,
    test_subset_id,
    use_per_classList=[True, False],
    correctness_thresholdList=[0.99, 0.95],
    human_key=None,
):
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

        print(cutoff_thresholds)

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
        # plt.show()

    return cutoff_thresholds
