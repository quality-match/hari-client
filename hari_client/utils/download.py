import functools
import json
import os
import uuid
from os.path import join
from typing import Type
from typing import TypeVar

from tqdm import tqdm

from hari_client import HARIClient
from hari_client.models import models


def save_to_json(file_path: str, data: dict) -> None:
    """
    Args:
        file_path: The path to the file where the JSON will be saved.
        data: Dictionary containing the data to be saved.

    Returns:
        None: This function does not return a value. It writes the JSON data to the file.
    """
    with open(file_path, "w") as json_file:
        json.dump(data, json_file, indent=4)


def pydantic_save_to_json(
    file_path: str, data: models.BaseModel | list[models.BaseModel]
) -> None:
    """
    Save a Pydantic model or a list of Pydantic models to a JSON file.

    Args:
        file_path: The path to the file where the JSON will be saved.
        data: The Pydantic model instance or a list of instances to serialize and save.

    Returns:
        None: This function does not return a value. It writes the JSON data to the file.
    """
    with open(file_path, "w") as json_file:
        if isinstance(data, list):
            # Serialize a list of Pydantic models
            # .model_dump(mode="json") ensures sets become lists and other objects
            # are converted properly.
            serialized = [model.model_dump(mode="json") for model in data]
            json.dump(serialized, json_file, indent=2)
        elif isinstance(data, models.BaseModel):
            # Serialize a single Pydantic model
            serialized = data.model_dump(mode="json")
            json.dump(serialized, json_file, indent=2)
        else:
            raise TypeError(
                "Data must be a Pydantic model or a list of Pydantic models."
            )


def load_from_json(file_path: str) -> dict:
    """
    Load and parse a JSON file from the specified path.

    Args:
        file_path (str): The path to the JSON file on disk.

    Returns:
        dict: A Python dictionary containing the parsed JSON data.
    """
    with open(file_path, "r") as json_file:
        return json.load(json_file)


T = TypeVar("T", bound=models.BaseModel)


def pydantic_load_from_json(file_path: str, model_class: Type[T]) -> T | list[T]:
    """
    Load a Pydantic model from a JSON file.

    Args:
        file_path: Path to the JSON file containing the serialized model data.
        model_class: The Pydantic model class to deserialize into.

    Returns:
        T: An instance of the Pydantic model class populated with the JSON data.
    """
    with open(file_path, "r") as json_file:
        json_data = json.load(json_file)

    if isinstance(json_data, list):
        # Deserialize a list of models
        return [model_class.model_validate(item) for item in json_data]
    elif isinstance(json_data, dict):
        # Deserialize a single model
        return model_class.model_validate(json_data)
    else:
        raise TypeError("JSON content must be a dictionary or a list of dictionaries.")


def convert_internal_attributes_to_list(
    medias: list[models.MediaResponse], media_objects: list[models.MediaObjectResponse]
):
    """
    Aggregate all attributes from lists of Media and MediaObject responses.

    This function iterates over each media and media object, collects their
    attributes, and returns them in a single list. This approach avoids the need
    to re-download attributes by manually extracting them from already-retrieved data.

    Args:
        medias (list[models.MediaResponse]): A list of media responses, possibly containing attributes.
        media_objects (list[models.MediaObjectResponse]): A list of media object responses, possibly containing attributes.

    Returns:
        list[models.Attribute]: A list of combined attributes from both medias and media objects.
    """
    attributes = []

    print("Split attributes manually to avoid redownloading!")
    for m in tqdm(medias):
        if m.attributes is None:
            continue
        attributes.extend(m.attributes)
    for mo in tqdm(media_objects):
        if mo.attributes is None:
            continue
        attributes.extend(mo.attributes)

    return attributes


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


def lru_cache_dataset_directory(func):
    cache_dict = {}

    @functools.wraps(func)
    def wrapper(
        hari,
        dataset_id: uuid.UUID,
        directory: str,
        subset_ids=None,
        cache=True,
        additional_fields=None,
    ):
        # Build the cache key from only (dataset_id, directory)
        cache_key = (dataset_id, directory)

        # If it's in our dict, return it
        if cache_key in cache_dict:
            return cache_dict[cache_key]

        # Otherwise compute it, store, return
        result = func(hari, dataset_id, directory, subset_ids, cache, additional_fields)
        cache_dict[cache_key] = result
        return result

    return wrapper


@lru_cache_dataset_directory
def collect_media_and_attributes(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    directory: str,
    subset_ids: list[str] = [],
    cache: bool = True,
    additional_fields: list[str] = [],
) -> tuple[
    list[models.MediaResponse],
    list[models.MediaObjectResponse],
    list[models.Attribute],
    list[models.AttributeMetadataResponse],
]:
    """
    Collect media and their corresponding attributes from a specified dataset,
    optionally restricting to certain subsets and applying caching or additional query fields.

    Args:
        hari: An instance of the HARI client to query data.
        dataset_id: The unique identifier of the dataset from which to collect media.
        directory: The file system directory where the data may be cached.
        subset_ids: A list of subset identifiers to limit the media and media object retrieval.
            Defaults to an empty list, meaning no subset-based restriction is applied.
        cache: Whether to use cached data if available. Defaults to True.
        additional_fields: A list of extra fields to retrieve or process
            when collecting media and media_objects. Defaults to an empty list which means no extra fields.
            If 'attributes' are specified as attribute, the attributes are directly downloaded with the media and media objects.
            The attribute values are then calculated based on this and not directly downloaded.
            For large datasets this approach may be faster than separate downloads.

    Returns: Collection of queried media, media objects and attributes.
    """

    # Check if the JSON files already exist
    media_file = join(directory, "media.json")
    media_object_file = join(directory, "media_objects.json")
    attr_file = join(directory, "attributes.json")
    attr_meta_file = join(directory, "attributes_meta.json")
    os.makedirs(directory, exist_ok=True)

    # meta attributes
    if os.path.exists(attr_meta_file) and cache:
        print("Load the attribute metas from the json file cache.")
        attribute_metas = pydantic_load_from_json(
            attr_meta_file, models.AttributeMetadataResponse
        )

    else:
        print("Query the attribute metas objects from HARI.")
        attribute_metas = hari.get_attribute_metadata(dataset_id)
        pydantic_save_to_json(attr_meta_file, attribute_metas)

    # media and media object
    if os.path.exists(media_object_file) and os.path.exists(media_file) and cache:
        print("Load the media and media objects from the json file cache.")
        # Load the dictionaries from the existing JSON files
        medias = pydantic_load_from_json(media_file, models.MediaResponse)
        media_objects = pydantic_load_from_json(
            media_object_file, models.MediaObjectResponse
        )
    else:
        print("Query the media and media objects from HARI.")
        dataset_name, medias, media_objects = get_media_and_objects(
            hari, dataset_id, subset_ids, additional_fields
        )
        pydantic_save_to_json(media_file, medias)
        pydantic_save_to_json(media_object_file, media_objects)

    # attributes
    if os.path.exists(attr_file) and cache:
        # Load the dictionaries from the existing JSON files
        if "attributes" not in additional_fields:
            print("Load the attributes from the json file cache.")
            attributes = pydantic_load_from_json(attr_file, models.AttributeResponse)
        else:
            attributes = convert_internal_attributes_to_list(medias, media_objects)
    else:
        if "attributes" not in additional_fields:
            print("Query the attributes from HARI.")
            attributes = get_all_attributes_for_media_and_objects(
                hari, dataset_id, media_objects, medias
            )
            pydantic_save_to_json(attr_file, attributes)
        else:
            # create based on fields in media objects
            pydantic_save_to_json(attr_file, [])
            attributes = convert_internal_attributes_to_list(medias, media_objects)

    return medias, media_objects, attributes, attribute_metas


def get_media_and_objects(
    hari: HARIClient,
    dataset_id: uuid.UUID,
    subset_id: list[str] = [],
    additional_fields: list[str] = [],
) -> tuple[str, list[models.MediaResponse], list[models.MediaObjectResponse]]:
    """
    Retrieve the name of a dataset and fetch its associated media and media objects.

    Args:
        hari: An instance of the HARI client to query data.
        dataset_id: The unique identifier of the dataset.
        subset_id: A list of subset IDs to filter the media or
            media objects. Defaults to an empty list, meaning no subset-based restriction.
        additional_fields: Additional fields to be included in the
            media object projection. Defaults to an empty list.

    Returns:
        dataset_name, media and media objects.
    """
    print("Fetching dataset name...")

    # Fetch dataset name
    dataset = hari.get_dataset(dataset_id)
    dataset_name = dataset.name

    print("Fetched name: ", dataset_name)

    # Define query parameters to filter media objects/medias by subset ID if exists
    query = []
    if subset_id:
        subset_query_parameters = {
            "attribute": "subset_ids",
            "query_operator": "in",
            "value": subset_id,
        }
        query = json.dumps(subset_query_parameters)

    # Define projection for media objects, i.e. which fields we want to get at the returned value
    media_object_projection = {
        "projection[id]": True,
        "projection[tags]": True,
        "projection[timestamp]": True,
        "projection[back_reference]": True,
        "projection[media_id]": True,
        "projection[object_category]": True,
        "projection[frame_idx]": True,
        "projection[subset_ids]": True,
    }

    for additional_field in additional_fields:
        media_object_projection[f"projection[{additional_field}]"] = True

    # Define projection for medias, i.e. which fields we want to get at the returned value
    media_projection = {
        "projection[id]": True,
        "projection[back_reference]": True,
        "projection[subset_ids]": True,
    }

    # Fetch medias asynchronously
    medias = hari.get_medias_paged(dataset_id, query=query, projection=media_projection)
    media_objects = hari.get_media_objects_paged(
        dataset_id, query=query, projection=media_object_projection
    )

    # Await all parallel tasks
    # TODO parallelize calls for faster download

    return dataset_name, medias, media_objects


def get_all_attributes_for_media_and_objects(
    hari: HARIClient,
    dataset_id: str,
    media_objects: list[models.MediaObjectResponse],
    medias: list[models.MediaResponse],
) -> list[models.AttributeValueResponse]:
    """
    Retrieve all attribute values for the given media and media objects within a dataset.

    This function consolidates the IDs of both media and media objects, then uses a query
    to fetch their associated attribute values. It can handle large datasets by using the
    paginated method on the HARI client.

    Args:
        hari: An instance of the HARI client.
        dataset_id: The unique identifier of the dataset.
        media_objects: A list of media object responses
            from which to extract IDs.
        medias: A list of media responses from which to extract IDs.

    Returns:
        AttributeValues
    """

    # Initialize a list to store media object IDs
    media_object_ids = []

    # Extract media object IDs from the media_objects response
    for media_object in media_objects:
        if media_object.id:
            media_object_ids.append(media_object.id)

    # Initialize a list to store media IDs
    media_ids = []

    # Extract media IDs from the medias response
    for media in medias:
        if media.id:
            media_ids.append(media.id)

    # Combine media IDs and media object IDs for filtering attributes
    annotatable_ids = media_ids + media_object_ids

    # Define the first query parameter to filter attributes by annotatable ids
    # TODO may not work if the query is too long
    attribute_query_parameters = {
        "attribute": "annotatable_id",
        "query_operator": "in",
        "value": annotatable_ids,
    }

    attribute_values = hari.get_attribute_values_paged(
        dataset_id, query=json.dumps(attribute_query_parameters)
    )

    return attribute_values
