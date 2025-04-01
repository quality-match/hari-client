import datetime
import json
import pathlib
import types
import typing
import uuid
import warnings

import pydantic
import requests
from requests import adapters
from tqdm import tqdm

from hari_client.client import errors
from hari_client.config import config
from hari_client.models import models
from hari_client.utils import logger


T = typing.TypeVar("T")

log = logger.setup_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


def _parse_response_model(
    response_data: typing.Any, response_model: typing.Type[T]
) -> T:
    """
    Parses data of type typing.Any to a generic response_model type.
    Cases:
        - both response_data and response_model are None (meaning you expect to receive None as response)
            - None is returned
        - response_model is a pydantic model:
            - if response_data is a dict, response_data is parsed into an instance of the response_model.
        - response_model is a parametrized generic:
            - if response_data is a list and response_model is a list of unions:
                - each item in the response_data list is checked against the possible types in the union.
                - the parser attempts to parse each item using each type in the union until one succeeds.
                - if an item is successfully parsed into one of the union types, and it contains nested fields that are also complex structures (e.g., lists of unions), the parser recurses into those nested structures to fully parse them.
            - if response_data is a dict and response_model is a dict with specified key and value types:
                - each key-value pair in the response_data dict is parsed, with the keys being converted to the specified key type, and the values being recursively parsed according to the specified value type.
        - response_data is of the expected type (response_model):
            - The response_data is returned as is.

    Args:
        response_data: the input data
        response_model: the generic response_model type

    Raises:
        errors.ParseResponseModelError: When parsing fails for any reason

    Returns:
        T: The passed response_model type
    """
    # The response_data can have many different types:
    # --> custom classes, dict, list, primitives (str, int, etc.), None
    try:
        if response_model is None:
            if response_data is None:
                return None
            raise errors.ParseResponseModelError(
                response_data=response_data,
                response_model=response_model,
                message=f"Expected response_data to be None, but received {response_data=}",
            )

        # handle pydantic models
        if isinstance(response_model, type) and issubclass(
            response_model, pydantic.BaseModel
        ):
            if isinstance(response_data, dict):
                return response_model(**response_data)

        # handle parametrized generics
        origin = typing.get_origin(response_model)
        if origin is list:
            item_type = typing.get_args(response_model)[0]
            if isinstance(response_data, list):
                origin = typing.get_origin(item_type)
                if origin in [typing.Union, types.UnionType]:
                    return [
                        handle_union_parsing(item, item_type) for item in response_data
                    ]
                elif isinstance(item_type, type) and issubclass(
                    item_type, pydantic.BaseModel
                ):
                    return [item_type(**item) for item in response_data]
                else:
                    return [item_type(item) for item in response_data]
        if origin is dict:
            key_type, value_type = typing.get_args(response_model)
            if isinstance(response_data, dict):
                return {
                    key_type(k): (
                        value_type(**v) if isinstance(v, dict) else value_type(v)
                    )
                    for k, v in response_data.items()
                }

        if isinstance(response_data, response_model):
            return response_data

        raise errors.ParseResponseModelError(
            response_data=response_data,
            response_model=response_model,
            message=f"Can't parse response_data into response_model {response_model},"
            + f" because the combination of received data and expected response_model "
            f"is unhandled.{response_data=}.",
        )
    except Exception as err:
        raise errors.ParseResponseModelError(
            response_data=response_data,
            response_model=response_model,
            message=f"Failed to parse response_data into response_model {response_model}. {response_data=}",
        ) from err


def handle_union_parsing(item, union_type):
    for possible_type in typing.get_args(union_type):
        if isinstance(possible_type, type) and issubclass(
            possible_type, pydantic.BaseModel
        ):
            try:
                return possible_type(**item)
            except Exception:
                continue
    raise errors.ParseResponseModelError(
        response_data=item,
        response_model=union_type,
        message=f"Failed to parse item into one of the union types {union_type}. {item=}",
    )


def _prepare_request_query_params(
    params: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Prepares query parameters for the request module's `request` method.
    Handled cases:
      - parameter value is a list of pydantic models.
        - Serializes a query param value of type list[pydantic.BaseModel] to a list[str]. Lists are formatted by the `request` method as `?my_list=value_1&my_list=value_2&my_list=value_3...`,
        but it doesn't automatically serialize a list of pydantic models, so we have to handle this here.
        This method contains a workaround for the param "query". It's expected type is QueryList.
            - The workarounds are: passing a single already serialized QueryParameter/LogicParameter object (serialized with json.dumps), or a list of them.
            - Note that in the future only QueryList will be supported for query. For now other types are supported due to existing workarounds.

    Args:
        params: The query parameters that should be added to the request.

    Returns:
        The query parameters dictionary with properly serialized values.
    """
    params_copy = {}

    for param_name, param_value in params.items():
        params_copy[param_name] = param_value

        if isinstance(param_value, list):
            param_value_copy = []
            for item in param_value:
                if isinstance(item, pydantic.BaseModel):
                    param_value_copy.append(json.dumps(item.model_dump()))
                elif param_name == "query" and isinstance(item, str):
                    param_value_copy.append(item)
                    msg = (
                        "Argument's 'query' content was detected to be a string, but should be QueryParameter or LogicParameter."
                        + " Support for this behavior will be removed in a future release."
                    )
                    warnings.warn(msg)
                else:
                    param_value_copy.append(item)
            params_copy[param_name] = param_value_copy
        elif param_name == "query" and isinstance(param_value, str):
            msg = (
                "Argument 'query' was passed as a string, but should be passed as a QueryList (list of QueryParameter or LogicParameter objects)."
                + " Support for this behavior will be removed in a future release."
            )
            warnings.warn(msg)

    return params_copy


class HARIClient:
    BULK_UPLOAD_LIMIT = 500

    def __init__(self, config: config.Config):
        self.config = config

        self.access_token = None
        # expiry is reset on every token refresh with the expiry time provided by the server
        self.expiry = datetime.datetime.fromtimestamp(0)
        self.session = requests.Session()

    def _request(
        self,
        method: str,
        url: str,
        success_response_item_model: typing.Type[T],
        **kwargs,
    ) -> T | None:
        """Make a request to the API.

        Args:
            method: The HTTP method to use.
            url: The URL to request.
            success_response_item_model: The response model class to parse the response
                json body into when the request status is a success code.
            error_response_item_model: The response model class to parse the response
                json body into when the response status is an error code.
            **kwargs: Additional keyword arguments to pass to the underlying request method.
        """
        # prepare request
        self._refresh_access_token()
        full_url = f"{self.config.hari_api_base_url}{url}"

        if "json" in kwargs:
            kwargs["json"] = json.loads(
                json.dumps(kwargs["json"], cls=CustomJSONEncoder)
            )

        if "params" in kwargs:
            kwargs["params"] = _prepare_request_query_params(kwargs["params"])

        # do request and basic error handling
        response = self.session.request(method, full_url, **kwargs)
        if not response.ok:
            raise errors.APIError(response)

        if "application/json" not in response.headers.get("Content-Type", ""):
            raise ValueError(
                "Expected application/json to be in Content-Type header, but couldn't find it."
            )

        # parse json body
        try:
            response_json = response.json()
        except Exception as err:
            raise ValueError(
                f"Response body could not be parsed as JSON. {response_json=}"
            ) from err

        # Parse response json into the expected response model.
        response_parsed = _parse_response_model(
            response_data=response_json, response_model=success_response_item_model
        )
        return response_parsed

    def _refresh_access_token(self) -> None:
        if self.access_token is None or datetime.datetime.now() > self.expiry:
            self._get_auth_token()
            self.session.headers.update(
                {"Authorization": f"Bearer {self.access_token}"}
            )

    def _get_auth_token(self) -> None:
        """
        Gets a token from the HARI auth server using the configured credentials.
        """
        response = requests.post(
            f"{self.config.hari_auth_url}/realms/BBQ/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": self.config.hari_client_id,
                "username": self.config.hari_username,
                "password": self.config.hari_password,
            },
        )

        # Authentication error
        if response.status_code == 401:
            log.error("Authentication error: Invalid username or password.")
            raise errors.AuthenticationError(response)

        response.raise_for_status()
        response_json = response.json()
        self.access_token = response_json["access_token"]
        # Set expiry time with a buffer of 1 second
        self.expiry = datetime.datetime.now() + datetime.timedelta(
            seconds=response_json["expires_in"] - 1
        )

    @staticmethod
    def _pack(locals_, not_none: list[str] = None, ignore: list[str] = None):
        """Prepare a dictionary of local variables to be sent as query params or in the body.

        :param locals_: A dictionary with local variables
        :param not_none: A list of parameters that should only be included if they are not None
        :param ignore: A list with parameters that should not be included in the dictionary
        :return: The resulting dictionary
        """
        not_none = not_none or []
        ignore = ignore or []

        # Filter out None values
        local_vars = list(
            filter(
                lambda var_name: locals_[var_name] is not None
                or var_name not in not_none,
                locals_.keys(),
            )
        )
        # Filter out values to be ignored
        local_vars = list(filter(lambda var_name: var_name not in ignore, local_vars))

        return {k: locals_[k] for k in local_vars if k not in ["self", "kwargs"]}

    def _upload_file(
        self, file_path: str, upload_url: str, session: requests.Session = None
    ) -> None:
        if session is None:
            session = requests.Session()
        with open(file_path, "rb") as fp:
            response = session.put(upload_url, data=fp)
            response.raise_for_status()

    def _upload_visualisation_file_with_presigned_url(
        self, dataset_id: uuid.UUID, visualisation_config_id: str, file_path: str
    ) -> models.VisualisationUploadUrlInfo:
        """Creates a presigned S3 upload url for the media visualisation located in file_path and uploads it.

        Args:
            dataset_id: The dataset id
            file_path: The path to the file to upload
            visualisation_config_id: The id of the visualisation config to which the visualisation belongs. Has to already exist.

        Returns:
            The VisualisationUploadUrlInfo object.
        """

        # 1. get presigned upload url for the visualisation
        file_extension = pathlib.Path(file_path).suffix
        presign_responses = self.get_presigned_visualisation_upload_url(
            dataset_id=dataset_id,
            file_extension=file_extension,
            visualisation_config_id=visualisation_config_id,
            batch_size=1,
        )
        self._upload_file(
            file_path=file_path, upload_url=presign_responses[0].upload_url
        )

        return presign_responses[0]

    def _upload_media_files_with_presigned_urls(
        self,
        dataset_id: uuid.UUID,
        file_paths: dict[int, str],
    ) -> dict[int, models.MediaUploadUrlInfo]:
        """Creates a presigned S3 upload url for every media file and uploads them.

        Args:
            dataset_id: The dataset id
            file_paths: A dict with paths to the files to upload. Keys represent the order of file_paths.
                The returned dict with MediaUploadUrlInfo objects maintains the same order.
                All files have to have the same file extension.

        Returns:
            A dict of MediaUploadUrlInfo objects. The keys represent the order of input file_paths.

        Raises:
            MediaFileExtensionNotIdentifiedDuringUploadError: if the file_extension of the provided file_paths couldn't be identified.
        """

        # the response dict
        presign_response_by_file_path_idx: dict[int, models.MediaUploadUrlInfo] = {}

        # find all file extensions
        files_by_file_extension: dict[str, list[tuple[int, str]]] = {}
        for idx, file_path in file_paths.items():
            file_extension = pathlib.Path(file_path).suffix
            if file_extension == "":
                raise errors.MediaFileExtensionNotIdentifiedDuringUploadError(file_path)
            if file_extension not in files_by_file_extension:
                files_by_file_extension[file_extension] = []
            files_by_file_extension[file_extension].append((idx, file_path))

        # set up the session with retry mechanism
        session = requests.Session()
        # due to the SSLEOFError obscuring the underlying error response from the cloud provider, we don't know
        # which status code to retry on. Therefore we retry on every 5xx codes, as well as the
        # two default 4xx codes.
        retries = adapters.Retry(
            total=5,
            backoff_factor=0.1,
            status_forcelist=[
                413,
                429,
                500,
                501,
                502,
                503,
                504,
                505,
                506,
                507,
                508,
                510,
                511,
            ],
        )
        session.mount("https://", adapters.HTTPAdapter(max_retries=retries))

        for (
            file_extension,
            file_extension_file_paths,
        ) in files_by_file_extension.items():
            # 1. get presigned upload url for the files
            presign_response_batch = self.get_presigned_media_upload_url(
                dataset_id=dataset_id,
                file_extension=file_extension,
                batch_size=len(file_extension_file_paths),
            )

            # 2. upload the image
            for idx, file_path in enumerate(file_extension_file_paths):
                presign_response_by_file_path_idx[
                    file_path[0]
                ] = presign_response_batch[idx]
                self._upload_file(
                    session=session,
                    file_path=file_path[1],
                    upload_url=presign_response_batch[idx].upload_url,
                )

        return presign_response_by_file_path_idx

    ### dataset ###
    def create_dataset(
        self,
        name: str,
        mediatype: models.MediaType | None = "image",
        user_group: str | None = None,
        creation_timestamp: str | None = None,
        reference_files: list | None = None,
        num_medias: int | None = 0,
        num_media_objects: int | None = 0,
        num_annotations: int | None = None,
        num_attributes: int | None = None,
        num_instances: int | None = 0,
        color: str | None = "#FFFFFF",
        archived: bool | None = False,
        is_anonymized: bool | None = False,
        license: str | None = None,
        owner: str | None = None,
        current_snapshot_id: int | None = None,
        visibility_status: (
            models.VisibilityStatus | None
        ) = models.VisibilityStatus.VISIBLE,
        data_root: str | None = "custom_upload",
        id: str | None = None,
        external_media_source: models.ExternalMediaSourceAPICreate | None = None,
    ) -> models.Dataset:
        """Creates an empty dataset in the database.

        Args:
            name: Name of the dataset
            mediatype: MediaType of the dataset
            user_group: The user group the new dataset shall be available to
            creation_timestamp: Creation timestamp
            reference_files: Reference files
            num_medias: Number of medias
            num_media_objects: Number of media objects
            num_annotations: Number of annotations
            num_attributes: Number of attributes
            num_instances: Number of instances
            color: Color of dataset
            archived: Whether dataset is archived
            is_anonymized: Whether dataset is anonymized
            license: License of dataset
            owner: Owner of the dataset
            current_snapshot_id: Current snapshot ID
            visibility_status: Visibility status of the new dataset
            data_root: Data root
            id: ID of the newly created dataset
            external_media_source: External Media Source

        Returns:
            The created dataset

        Raises:
            APIException: If the request fails.
        """
        if external_media_source:
            external_media_source = external_media_source.model_dump()

        return self._request(
            "POST",
            "/datasets",
            json=self._pack(locals(), not_none=["creation_timestamp", "id"]),
            success_response_item_model=models.Dataset,
        )

    def update_dataset(
        self,
        dataset_id: uuid.UUID,
        id: str | None = None,
        name: str | None = None,
        mediatype: models.MediaType | None = None,
        is_anonymized: bool | None = None,
        color: str | None = None,
        archived: bool | None = None,
        owner: str | None = None,
        current_snapshot_id: int | None = None,
        num_medias: int | None = None,
        num_media_objects: int | None = None,
        num_annotations: int | None = None,
        num_attributes: int | None = None,
        num_instances: int | None = None,
        visibility_status: models.VisibilityStatus | None = None,
    ) -> models.DatasetResponse:
        """Updates the dataset with the given id.

        Args:
            dataset_id: Dataset id of the dataset to update
            id: New id of the dataset
            name: Name of the dataset
            mediatype: MediaType of the dataset
            is_anonymized: Whether dataset is anonymized
            color: Color of dataset
            archived: Whether dataset is archived
            owner: Owner of the dataset
            current_snapshot_id: Current snapshot ID
            num_medias: Number of medias
            num_media_objects: Number of media objects
            num_annotations: Number of annotations
            num_attributes: Number of attributes
            num_instances: Number of instances
            visibility_status: Visibility status of the new dataset

        Returns:
            The updated dataset

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PATCH",
            f"/datasets/{dataset_id}",
            json=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.DatasetResponse,
        )

    def get_dataset(self, dataset_id: uuid.UUID) -> models.DatasetResponse:
        """Returns a dataset with a given dataset_id.

        Args:
            dataset_id: dataset id

        Returns:
            The dataset with the given dataset_id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}",
            success_response_item_model=models.DatasetResponse,
        )

    def get_datasets(
        self,
        subset: bool | None = False,
        visibility_statuses: tuple | None = (models.VisibilityStatus.VISIBLE,),
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        name_filter: str | None = None,
        archived: bool | None = False,
    ) -> list[models.DatasetResponse]:
        """Returns datasets that a user has access to.

        Args:
            subset: Return also subsets. If False, returns only parent datasets
            visibility_statuses: Visibility statuses of the returned datasets
            limit: limit the number of datasets returned
            skip: skip the number of datasets returned
            query: query parameters to filter the datasets
            sort: sorting parameters to sort the datasets
            name_filter: filter by dataset name
            archived: if true, return only archived datasets; if false (default), return non-archived datasets.

        Returns:
            A list of datasets

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            "/datasets",
            params=self._pack(locals()),
            success_response_item_model=list[models.DatasetResponse],
        )

    def get_datasets_count(
        self,
        visibility_statuses: tuple | None = (models.VisibilityStatus.VISIBLE,),
        query: models.QueryList | None = None,
        name_filter: str | None = None,
        archived: bool | None = False,
    ) -> int:
        """
        Returns dataset count for the user.
        Args:
            visibility_statuses: Visibility statuses of the returned datasets
            query: query parameters to filter the datasets
            name_filter: filter by dataset name
            archived: if true, count only archived datasets; if false (default), count non-archived datasets.

        Returns:
            The number of datasets

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            "/datasets:count",
            params=self._pack(locals()),
            success_response_item_model=int,
        )

    def get_subsets_for_dataset(
        self,
        dataset_id: uuid.UUID,
        visibility_statuses: tuple | None = (models.VisibilityStatus.VISIBLE,),
    ) -> list[models.DatasetResponse]:
        """Returns all subsets belonging to a specific dataset

        Args:
            dataset_id: The dataset id of the parent dataset
            visibility_statuses: Visibility statuses of the returned subsets

        Returns:
            A list of subsets

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/subsets",
            params=self._pack(locals(), ignore=["dataset_id"]),
            # the response model for a subset is the same as for a dataset
            success_response_item_model=list[models.DatasetResponse],
        )

    def archive_dataset(self, dataset_id: uuid.UUID) -> str:
        """Archives a dataset and all its subsets.

        Args:
            dataset_id: Dataset id of the dataset to be deleted

        Returns: The dataset id of the archived dataset

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "DELETE", f"/datasets/{dataset_id}", success_response_item_model=str
        )

    ### subset ###
    def create_subset(
        self,
        dataset_id: uuid.UUID,
        subset_type: models.SubsetType,
        subset_name: str,
        filter_options: models.QueryList | None = None,
        secondary_filter_options: models.QueryList | None = None,
        object_category: bool | None = False,
        visualisation_config_id: str | None = None,
    ) -> str:
        """creates a new subset based on a filter and uploads it to the database

        Args:
            dataset_id: Dataset Id
            subset_type: Type of the subset (media, media_object, instance, attribute)
            subset_name: The name of the subset
            filter_options: Filter options defining subset
            secondary_filter_options: In Media subsets these will filter down the media_objects
            object_category: True if the new subset shall be shown as a category for objects in HARI
            visualisation_config_id: Visualisation Config Id

        Returns:
            The new subset id

        Raises:
            APIException: If the request fails.
        """
        body = {}
        if filter_options:
            body["filter_options"] = filter_options
        if secondary_filter_options:
            body["secondary_filter_options"] = secondary_filter_options

        return self._request(
            "POST",
            "/subsets:createFiltered",
            params=self._pack(
                locals(), ignore=["filter_options", "secondary_filter_options"]
            ),
            json=body,
            success_response_item_model=str,
        )

    def create_empty_subset(
        self,
        dataset_id: uuid.UUID,
        subset_type: models.SubsetType,
        subset_name: str,
        object_category: bool | None = False,
        visibility_status: models.VisibilityStatus | None = None,
    ) -> str:
        """creates a new empty subset and uploads it to the database

        Args:
            dataset_id: Dataset Id
            subset_type: Type of the subset (media, media_object, instance, attribute)
            subset_name: The name of the subset
            object_category: True if the new subset shall be shown as a category for objects in HARI
            visibility_status: Visibility status of the created subset

        Returns:
            The new subset id

        Raises:
            APIException: If the request fails.
        """
        body = {}

        return self._request(
            "POST",
            "/subsets",
            params=self._pack(
                locals(),
            ),
            json=body,
            success_response_item_model=str,
        )

    ### external media source ###
    def get_external_media_source(
        self, external_media_source_id: uuid.UUID
    ) -> models.ExternalMediaSourceAPIResponse:
        """Returns an external media source with a given external_media_source_id.

        Args:
            external_media_source_id: external media source id

        Returns:
            The external media source with the given external_media_source_id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/externalMediaSources/{external_media_source_id}",
            params=self._pack(locals()),
            success_response_item_model=models.ExternalMediaSourceAPIResponse,
        )

    ### media ###
    def create_media(
        self,
        dataset_id: uuid.UUID,
        file_path: str | None,
        name: str,
        media_type: models.MediaType,
        back_reference: str,
        archived: bool = False,
        scene_id: str | None = None,
        realWorldObject_id: str | None = None,
        frame_idx: int | None = None,
        frame_timestamp: str | None = None,
        back_reference_json: str | None = None,
        visualisations: list[models.VisualisationUnion] | None = None,
        subset_ids: set[str] | None = None,
        metadata: models.ImageMetadata | models.PointCloudMetadata | None = None,
        file_key: str | None = None,
        with_media_files_upload: bool = True,
    ) -> models.Media:
        """Accepts a single file, uploads it, and creates the media in the db.

        Args:
            dataset_id: The dataset id
            file_path: File path of the media to be uploaded
            name: Name of the media
            media_type: The media type
            back_reference: Back reference to identify the media later on
            archived: Whether the media is archived
            scene_id: Scene Id of the media
            realWorldObject_id: Realworldobject Id of the media
            frame_idx: Frame index of the media
            frame_timestamp: Frame timestamp
            back_reference_json: Another back reference for the media
            visualisations: Visualisations of the media
            subset_ids: Subset ids the media occurs in
            metadata: Image metadata
            file_key: The file key is the key of the media file in cloud storage (excluding the bucket_name, container_name, etc.).
            with_media_files_upload: Whether the media file has to be uploaded or not

        Returns:
            Media that was just created

        Raises:
            APIException: If the request fails.
            MediaCreateMissingFilePathError: if a MediaCreate object is missing the file_path field and with_media_files_upload is True.
            MediaCreateMissingFileKeyError: if a MediaCreate object is missing the file_key field and with_media_files_upload is False.
        """
        if with_media_files_upload:
            # 1. upload file
            if not file_path:
                raise errors.MediaCreateMissingFilePathError(
                    models.MediaCreate(
                        file_path=file_path,
                        name=name,
                        media_type=media_type,
                        back_reference=back_reference,
                    )
                )
            media_upload_responses = self._upload_media_files_with_presigned_urls(
                dataset_id, file_paths={0: file_path}
            )
            media_url = media_upload_responses[0].media_url
        elif not file_key:
            raise errors.MediaCreateMissingFileKeyError(
                models.MediaCreate(
                    name=name,
                    media_type=media_type,
                    back_reference=back_reference,
                )
            )

        # 2. create the media in HARI
        json_body = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
                "media_upload_responses",
                "with_media_files_upload",
            ],
        )
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias",
            json=json_body,
            success_response_item_model=models.Media,
        )

    def create_medias(
        self,
        dataset_id: uuid.UUID,
        medias: list[models.BulkMediaCreate],
        with_media_files_upload: bool = True,
    ) -> models.BulkResponse:
        """Accepts multiple media files, uploads them, and creates the media entries in the db.
        The limit is 500 per call.

        Args:
            dataset_id: The dataset id
            medias: A list of MediaCreate objects. Each object contains the file_path as a field.
            with_media_files_upload: Whether the media files have to be uploaded or not.

        Returns:
            A BulkResponse with information on upload successes and failures.

        Raises:
            APIException: If the request fails.
            BulkUploadSizeRangeError: if the number of medias exceeds the per call upload limit.
            MediaCreateMissingFilePathError: if a MediaCreate object is missing the file_path field and with_media_files_upload is True.
            MediaCreateMissingFileKeyError: if a MediaCreate object is missing the file_key field and with_media_files_upload is False.
            MediaFileExtensionNotIdentifiedDuringUploadError: if the file_extension of the provided file_paths couldn't be identified.
        """

        if len(medias) > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.BulkUploadSizeRangeError(
                limit=HARIClient.BULK_UPLOAD_LIMIT, found_amount=len(medias)
            )
        if with_media_files_upload:
            # 1. upload files - if necessary
            file_paths: dict[int, str] = {}
            for idx, media in enumerate(medias):
                if not media.file_path:
                    raise errors.MediaCreateMissingFilePathError(media)
                file_paths[idx] = media.file_path

            media_upload_responses = self._upload_media_files_with_presigned_urls(
                dataset_id, file_paths=file_paths
            )

            # 2. set media_urls on medias and parse them to dicts
            media_dicts = []
            for idx, media in enumerate(medias):
                media.media_url = media_upload_responses[idx].media_url
                media_dicts.append(media.model_dump())
        else:
            media_dicts = []
            for media in medias:
                if not media.file_key:
                    raise errors.MediaCreateMissingFileKeyError(media)
                media_dicts.append(media.model_dump())

        # 3. create the medias in HARI
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias:bulk",
            json=media_dicts,
            success_response_item_model=models.BulkResponse,
        )

    def update_media(
        self,
        dataset_id: uuid.UUID,
        media_id: str,
        back_reference: str | None = None,
        archived: bool | None = None,
        scene_id: str | None = None,
        realWorldObject_id: str | None = None,
        visualisations: list[models.VisualisationUnion] | None = None,
        subset_ids: list | None = None,
        name: str | None = None,
        metadata: models.ImageMetadata | models.PointCloudMetadata | None = None,
        frame_idx: int | None = None,
        media_type: models.MediaType | None = None,
        frame_timestamp: str | None = None,
        back_reference_json: str | None = None,
    ) -> models.Media:
        """Updates the media

        Args:
            dataset_id: The dataset id
            media_id: The media id
            back_reference: Back reference identifying the media
            archived: Whether to return archived media
            scene_id: Scene id of the media
            realWorldObject_id: Realworldobject Id
            visualisations: Visualisations of the media
            subset_ids: Subset ids the media is in
            name: Name of the media
            metadata: Image metadata
            frame_idx: Frame idx of the media
            media_type: Type of the media
            frame_timestamp: Frame timestamp
            back_reference_json: Another type of back reference

        Returns:
            The updated media

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PATCH",
            f"/datasets/{dataset_id}/medias/{media_id}",
            json=self._pack(locals(), ignore=["dataset_id", "media_id"]),
            success_response_item_model=models.Media,
        )

    def get_media(
        self,
        dataset_id: uuid.UUID,
        media_id: str,
        presign_media: bool | None = True,
        archived: bool | None = False,
        projection: dict[str, bool] | None = None,
    ) -> models.MediaResponse:
        """Get a media by its id.

        Args:
            dataset_id: The dataset id
            media_id: The media id
            presign_media: Whether to presign media
            archived: Return archived media
            projection: The fields to be returned (dictionary keys with value True are
                returned, keys with value False are not returned)

        Returns:
            The media matching the provided id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias/{media_id}",
            params=self._pack(locals(), ignore=["dataset_id", "media_id"]),
            success_response_item_model=models.MediaResponse,
        )

    def get_medias(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MediaResponse]:
        """Get medias of a dataset

        Args:
            dataset_id: The dataset id
            archived: if true, return only archived medias; if false (default), return non-archived medias.
            presign_medias: Whether to presign medias
            limit: The number of medias tu return
            skip: The number of medias to skip
            query: The filters to be applied to the search
            sort: The list of sorting parameters
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            A list of medias in a dataset

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.MediaResponse],
        )

    def get_medias_paginated(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        batch_size: int = 100,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MediaResponse]:
        """Get medias of a dataset, but with pagination, could be used for larger datasets to avoid timeouts.

        Args:
            dataset_id: The dataset id
            archived: Whether to get archived media
            presign_medias: Whether to presign medias
            batch_size: The number of medias to fetch per request. Defaults to 100.
            query: The filters to be applied to the search
            sort: The list of sorting parameters
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            A list of medias in a dataset

        Raises:
            APIException: If the request fails.
        """

        total_medias: int = self.get_media_count(
            dataset_id, archived, query
        ).total_count

        log.info(f"Fetching {total_medias} medias ...")

        medias: list[models.MediaResponse] = []

        # Loop through media pages until all are retrieved
        for skip in tqdm(range(0, total_medias, batch_size)):
            medias_page = self.get_medias(
                dataset_id=dataset_id,
                archived=archived,
                presign_medias=presign_medias,
                limit=batch_size,
                skip=skip,
                query=query,
                sort=sort,
                projection=projection,
            )
            medias.extend(medias_page)

        log.info(f"Fetched {len(medias)} medias successfully.")

        return medias

    def archive_media(self, dataset_id: uuid.UUID, media_id: str) -> str:
        """Archive the media

        Args:
            dataset_id: The dataset id
            media_id: The media id

        Returns:
            Media id of the archived media

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "DELETE",
            f"/datasets/{dataset_id}/medias/{media_id}",
            success_response_item_model=str,
        )

    def get_presigned_visualisation_upload_url(
        self,
        dataset_id: uuid.UUID,
        file_extension: str,
        visualisation_config_id: str,
        batch_size: int,
    ) -> list[models.VisualisationUploadUrlInfo]:
        """
        Creates a presigned upload URL for a file to be uploaded to S3 and used for visualisations.

        Args:
            dataset_id: id of the dataset to which the visualisation will belong
            file_extension: the file extension of the file to be uploaded. For example: ".jpg", ".png"
            visualisation_config_id: id of the visualisation configuration of the visualisation
            batch_size: number of upload links and ids to generate. Valid range: 1 <= batch_size <= 500.

        Returns:
            list[models.VisualisationUploadUrlInfo]: A list with UploadUrlInfo objects containing the presigned
                upload URL and the media_url which should be used when creating the media.

        Raises:
            APIException: If the request fails.
            ParameterRangeError: If the batch_size is out of range.
        """
        if batch_size < 1 or batch_size > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.ParameterNumberRangeError(
                param_name="batch_size",
                minimum=1,
                maximum=HARIClient.BULK_UPLOAD_LIMIT,
                value=batch_size,
            )
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/visualisations/uploadUrl",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.VisualisationUploadUrlInfo],
        )

    def get_media_histograms(
        self, dataset_id: uuid.UUID, subset_id: str | None = None
    ) -> list[models.AttributeHistogram]:
        """Get the histogram data

        Args:
            dataset_id: The dataset id
            subset_id: The subset Id

        Returns:
            A list of media histograms

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias/histograms",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeHistogram],
        )

    def get_instance_histograms(
        self, dataset_id: uuid.UUID, subset_id: str | None = None
    ) -> list[models.AttributeHistogram]:
        """Get the histogram data

        Args:
            dataset_id: dataset id
            subset_id: Subset Id

        Returns:
            list

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/instances/histograms",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeHistogram],
        )

    def get_media_object_count_statistics(
        self,
        dataset_id: uuid.UUID,
        subset_id: str | None = None,
        archived: bool | None = False,
    ) -> dict[str, typing.Any]:
        """Get a dictionary describing the number of medias and number of corresponding media objects

        Args:
            dataset_id: The dataset id
            subset_id: The subset id or None, if the result for the whole dataset
            archived: if true, consider only archived medias; if false (default), consider only non-archived medias.

        Returns:
            Dictionary, where the key is the number of medias in the dataset having
            value number of media objects

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias/mediaObjectsFrequency",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=dict,
        )

    def get_media_count(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> models.FilterCount:
        """Calculates the number of medias for a given filter setting

        Args:
            dataset_id: The dataset id
            archived: if true, consider only archived medias; if false (default), consider only non-archived medias.
            query: Query

        Returns:
            A dictionary with the total count and false_negative_percentage and false_positive_percentage

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias:count",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.FilterCount,
        )

    def create_visualisation_config(
        self,
        dataset_id: uuid.UUID,
        name: str,
        parameters: (
            models.CropVisualisationConfigParameters
            | models.TileVisualisationConfigParameters
            | models.RenderedVisualisationConfigParameters
        ),
    ) -> models.VisualisationConfiguration:
        """Creates a new visualisation_config based on the provided parameters.

        Args:
            dataset_id: The dataset id
            name: Name of the visualisation config
            parameters: CropVisualisationConfigParameters

        Returns:
            VisualisationConfiguration

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/visualisationConfigs",
            json={
                "name": name,
                # Convert to dict to avoid the following type of errors:
                # Object of type CropVisualisationConfigParameters is not JSON serializable
                "parameters": parameters.model_dump(exclude_unset=True),
            },
            success_response_item_model=models.VisualisationConfiguration,
        )

    def add_visualisation_to_media(
        self,
        dataset_id: uuid.UUID,
        media_id: str,
        file_path: str,
        visualisation_configuration_id: str,
    ) -> models.Visualisation:
        """Adds a visualisation to the media

        Args:
            dataset_id: The dataset id a visualisation belongs to
            media_id: The media id a visualisation belongs to
            file_path: Path to the file of the visualisation to be uploaded
            visualisation_configuration_id: The visualisation configuration id to be used

        Returns:
            Visualisation

        Raises:
            APIException: If the request fails.
        """
        # 1. upload file to presigned URL
        visualisation_upload_response = (
            self._upload_visualisation_file_with_presigned_url(
                dataset_id=dataset_id,
                visualisation_config_id=visualisation_configuration_id,
                file_path=file_path,
            )
        )
        visualisation_url = visualisation_upload_response.upload_url

        # 2. create the visualisation in HARI
        query_params = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
                "media_id",
                "visualisation_upload_response",
            ],
        )
        # We need to add annotatable_id and annotatable_type to the query_params
        query_params["annotatable_id"] = media_id
        query_params["annotatable_type"] = models.DataBaseObjectType.MEDIA

        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias/{media_id}/visualisations",
            params=query_params,
            success_response_item_model=models.Visualisation,
        )

    def get_presigned_media_upload_url(
        self, dataset_id: uuid.UUID, file_extension: str, batch_size: int
    ) -> list[models.MediaUploadUrlInfo]:
        """
        Creates a presigned upload URL for a file to be uploaded to S3 and used for medias.

        Args:
            dataset_id: id of the dataset to which the media will belong
            file_extension: the file extension of the file to be uploaded. For example: ".jpg", ".png"
            batch_size: number of upload links and ids to generate. Valid range: 1 <= batch_size <= 500.

        Returns:
            list[models.MediaUploadUrlInfo]: A list with MediaUploadUrlInfo objects containing the presigned
                upload URL and the media_url which should be used when creating the media.

        Raises:
            APIException: If the request fails.
            ParameterRangeError: If the validating input args fails.
        """
        if batch_size < 1 or batch_size > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.ParameterNumberRangeError(
                param_name="batch_size",
                minimum=1,
                maximum=HARIClient.BULK_UPLOAD_LIMIT,
                value=batch_size,
            )
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias/uploadUrl",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.MediaUploadUrlInfo],
        )

    ### media object ###
    def create_media_object(
        self,
        dataset_id: uuid.UUID,
        media_id: str,
        back_reference: str,
        source: models.DataSource = models.DataSource.REFERENCE,
        archived: bool | None = False,
        scene_id: str | None = None,
        realWorldObject_id: str | None = None,
        visualisations: list[models.VisualisationUnion] | None = None,
        subset_ids: list | None = None,
        instance_id: str | None = None,
        object_category: uuid.UUID | None = None,
        qm_data: list[models.GeometryUnion] | None = None,
        reference_data: models.GeometryUnion | None = None,
        frame_idx: int | None = None,
        media_object_type: models.MediaObjectType | None = None,
    ) -> models.MediaObject:
        """Creates a new media_object in the database.

        Args:
            dataset_id: dataset id
            media_id: Media Id
            back_reference: Back Reference
            source: DataSource
            archived: Archived
            scene_id: Scene Id
            realWorldObject_id: Realworldobject Id
            visualisations: Visualisations
            subset_ids: Subset Ids
            instance_id: Instance Id
            object_category: Object Category
            qm_data: QM sourced geometry object
            reference_data: Externally sourced geometry object
            frame_idx: Frame Idx
            media_object_type: Media Object Type

        Returns:
            MediaObject

        Raises:
            APIException: If the request fails.
        """
        qm_data = (
            list(map(lambda x: x.dict(), qm_data))
            if isinstance(qm_data, list)
            else None
        )
        reference_data = reference_data.model_dump() if reference_data else None
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/mediaObjects",
            json=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.MediaObject,
        )

    def create_media_objects(
        self,
        dataset_id: uuid.UUID,
        media_objects: list[models.BulkMediaObjectCreate],
    ) -> models.BulkResponse:
        """Creates new media_objects in the database. The limit is 500 per call.

        Args:
            dataset_id: dataset id
            media_objects: List of media objects

        Returns:
            A BulkResponse with information on upload successes and failures.

        Raises:
            APIException: If the request fails.
            BulkUploadSizeRangeError: if the number of medias exceeds the per call upload limit.
        """

        if len(media_objects) > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.BulkUploadSizeRangeError(
                limit=HARIClient.BULK_UPLOAD_LIMIT, found_amount=len(media_objects)
            )

        # 1. parse media_objects to dicts before upload
        media_object_dicts = [
            media_object.model_dump() for media_object in media_objects
        ]

        # 2. send media_objects to HARI
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/mediaObjects:bulk",
            json=media_object_dicts,
            success_response_item_model=models.BulkResponse,
        )

    def update_media_object(
        self,
        dataset_id: uuid.UUID,
        media_object_id: str,
        back_reference: str | None = None,
        archived: bool | None = None,
        scene_id: str | None = None,
        realWorldObject_id: str | None = None,
        visualisations: list[models.VisualisationUnion] | None = None,
        subset_ids: list | None = None,
        media_id: str | None = None,
        instance_id: str | None = None,
        source: models.DataSource | None = None,
        object_category: uuid.UUID | None = None,
        qm_data: list[models.GeometryUnion] | None = None,
        reference_data: models.GeometryUnion | None = None,
        frame_idx: int | None = None,
        media_object_type: models.MediaObjectType | None = None,
    ) -> models.MediaObject:
        """Updates the media object given by a media object id

        Args:
            dataset_id: dataset id
            media_object_id: media object id
            back_reference: Back Reference
            archived: Archived
            scene_id: Scene Id
            realWorldObject_id: Realworldobject Id
            visualisations: Visualisations
            subset_ids: Subset Ids
            media_id: Media Id
            instance_id: Instance Id
            source: DataSource
            object_category: Object category's subset id
            qm_data: QM sourced geometry object
            reference_data: Externally sourced geometry object
            frame_idx: Frame Idx
            media_object_type: Media Object Type

        Returns:
            MediaObject

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PATCH",
            f"/datasets/{dataset_id}/mediaObjects/{media_object_id}",
            json=self._pack(locals(), ignore=["dataset_id", "media_object_id"]),
            success_response_item_model=models.MediaObject,
        )

    def get_media_object(
        self,
        dataset_id: uuid.UUID,
        media_object_id: str,
        archived: bool | None = False,
        presign_media: bool | None = True,
        projection: dict[str, bool] | None = None,
    ) -> models.MediaObjectResponse:
        """Fetches a media object by its id.

        Args:
            dataset_id: dataset id
            media_object_id: media object id
            archived: Archived
            presign_media: Presign Media
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            Requested media object

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/mediaObjects/{media_object_id}",
            params=self._pack(locals(), ignore=["dataset_id", "media_object_id"]),
            success_response_item_model=models.MediaObjectResponse,
        )

    def get_media_objects(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MediaObjectResponse]:
        """Queries the database based on the submitted parameters and returns a list of media objects

        Args:
            dataset_id: dataset id
            archived: if true, return only archived media objects; if false (default), return non-archived media objects.
            presign_medias: Presign Medias
            limit: Limit
            skip: Skip
            query: Query
            sort: Sort
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            list of media objects of a dataset

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/mediaObjects",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.MediaObjectResponse],
        )

    def get_media_objects_paginated(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        batch_size: int = 100,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MediaObjectResponse]:
        """Get media objects of a dataset, pagination, could be used for larger datasets to avoid timeouts.

        Args:
            dataset_id: The dataset id
            archived: Whether to get archived media objects
            presign_medias: Whether to presign medias
            batch_size: The number of media objects to fetch per request. Defaults to 100.
            query: The filters to be applied to the search
            sort: The list of sorting parameters
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            A list of media objects in a dataset

        Raises:
            APIException: If the request fails.
        """

        total_media_objects: int = self.get_media_object_count(
            dataset_id, archived, query
        ).total_count

        log.info(f"Fetching {total_media_objects} media objects ...")

        media_objects: list[models.MediaObjectResponse] = []

        # Loop through media object pages until all are retrieved
        for skip in tqdm(range(0, total_media_objects, batch_size)):
            media_objects_page = self.get_media_objects(
                dataset_id=dataset_id,
                archived=archived,
                presign_medias=presign_medias,
                limit=batch_size,
                skip=skip,
                query=query,
                sort=sort,
                projection=projection,
            )
            media_objects.extend(media_objects_page)

        log.info(f"Fetched {len(media_objects)} media objects successfully.")

        return media_objects

    def archive_media_object(self, dataset_id: uuid.UUID, media_object_id: str) -> str:
        """Delete (archive) a media object from the db.

        Args:
            dataset_id: dataset id
            media_object_id: media object id

        Returns:
            Media object id of the deleted media object

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "DELETE",
            f"/datasets/{dataset_id}/mediaObjects/{media_object_id}",
            success_response_item_model=str,
        )

    def get_media_object_histograms(
        self, dataset_id: uuid.UUID, subset_id: str | None = None
    ) -> list[models.AttributeHistogram]:
        """Get the histogram data

        Args:
            dataset_id: dataset id
            subset_id: Subset Id

        Returns:
            Histograms of the media object

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/mediaObjects/histograms",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeHistogram],
        )

    def get_media_object_count(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> models.FilterCount:
        """Calculates the number of mediaObjects found in the db for a given filter setting

        Args:
            dataset_id: dataset id
            archived: if true, consider only archived media objects; if false (default), consider only non-archived media objects.
            query: Query

        Returns:
            FilterCount

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/mediaObjects:count",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.FilterCount,
        )

    def add_visualisation_to_media_object(
        self,
        dataset_id: uuid.UUID,
        media_object_id: str,
        file_path: str,
        visualisation_configuration_id: str,
    ) -> models.Visualisation:
        """Adds the visualisations of the mediaObject with the given id.

        Args:
            dataset_id: The dataset id a visualisation belongs to
            media_object_id: The media object id a visualisation belongs to
            file_path: Path to the file of the visualisation to be uploaded
            visualisation_configuration_id: The visualisation configuration id to be used

        Returns:
            Visualisation

        Raises:
            APIException: If the request fails.
        """
        # 1. upload file to presigned URL
        visualisation_upload_response = (
            self._upload_visualisation_file_with_presigned_url(
                dataset_id=dataset_id,
                visualisation_config_id=visualisation_configuration_id,
                file_path=file_path,
            )
        )
        visualisation_url = visualisation_upload_response.upload_url

        # 2. create the visualisation in HARI
        query_params = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
                "media_object_id",
                "visualisation_upload_response",
            ],
        )
        # We need to add annotatable_id and annotatable_type to the query_params
        query_params["annotatable_id"] = media_object_id
        query_params["annotatable_type"] = models.DataBaseObjectType.MEDIAOBJECT

        return self._request(
            "POST",
            f"/datasets/{dataset_id}/mediaObjects/{media_object_id}/visualisations",
            params=query_params,
            success_response_item_model=models.Visualisation,
        )

    ### metadata ###
    def trigger_histograms_update_job(
        self,
        dataset_id: uuid.UUID,
        trace_id: uuid.UUID | None = None,
        compute_for_all_subsets: bool = False,
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers the update of the histograms for a given dataset.

        Args:
            dataset_id: The dataset id
            trace_id: An id to trace the processing job(s). Is created by the user
            compute_for_all_subsets: Update histograms for all subsets

        Raises:
            APIException: If the request fails.

        Returns:
            list[models.BaseProcessingJobMethod]: the methods being executed
        """
        params = {"compute_for_all_subsets": compute_for_all_subsets}

        if trace_id is not None:
            params["trace_id"] = trace_id

        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/histograms",
            params=params,
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

    def trigger_metadata_rebuild_job(
        self,
        dataset_ids: list[uuid.UUID],
        anonymize: bool = False,
        calculate_histograms: bool = True,
        trace_id: uuid.UUID | None = None,
        force_recreate: bool = False,
        compute_auto_attributes: bool = False,
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers execution of one or more jobs which (re-)build metadata for all provided datasets.

        Args:
            dataset_ids: dataset_ids to rebuild metadata for max 10.
            anonymize: Anonymize the dataset if true. This will incur costs
            calculate_histograms: Calculate histograms if true
            trace_id: An id to trace the processing job
            force_recreate: If True already existing crops and thumbnails will be recreated; only available for qm internal users
            compute_auto_attributes: If True auto attributes will be computed

        Returns:
            The methods being executed
        """
        if len(dataset_ids) < 1 or len(dataset_ids) > 10:
            raise errors.ParameterListLengthError(
                param_name="dataset_ids",
                minimum=1,
                maximum=10,
                length=len(dataset_ids),
            )
        return self._request(
            "POST",
            "/metadata:rebuild",
            json=self._pack(locals()),
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

    def trigger_dataset_metadata_rebuild_job(
        self,
        dataset_id: uuid.UUID,
        subset_id: uuid.UUID | None = None,
        anonymize: bool = False,
        calculate_histograms: bool = True,
        trace_id: uuid.UUID | None = None,
        force_recreate: bool = False,
        compute_auto_attributes: bool = False,
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers execution of one or more jobs which (re-)build metadata for the provided dataset.

        Args:
            dataset_id: dataset_id to rebuild metadata for
            subset_id: subset_id to rebuild metadata for
            anonymize: Anonymize the dataset if true. This will incur costs.
            calculate_histograms: Calculate histograms if true.
            trace_id: An id to trace the processing job
            force_recreate: If True already existing crops and thumbnails will be recreated; only available for qm internal users
            compute_auto_attributes: If True auto attributes will be computed

        Returns:
            The methods being executed
        """
        params = {
            "anonymize": anonymize,
            "calculate_histograms": calculate_histograms,
            "force_recreate": force_recreate,
            "compute_auto_attributes": compute_auto_attributes,
        }
        if subset_id:
            params["subset_id"] = subset_id
        if trace_id:
            params["trace_id"] = trace_id

        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/metadata",
            params=params,
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

    ### processing_jobs ###
    def get_processing_jobs(
        self,
        trace_id: uuid.UUID = None,
    ) -> list[models.ProcessingJob]:
        """
        Retrieves the list of processing jobs that the user has access to.

        Args:
            trace_id: Helps to identify related processing jobs. Use the trace_id that
                was specified when triggering a processing job

        Raises:
            APIException: If the request fails.

        Returns:
            A list of processing jobs for the user or [] if there are no jobs of
            trace_id is not found.
        """
        params = {}
        if trace_id:
            params["trace_id"] = trace_id

        return self._request(
            "GET",
            "/processingJobs",
            params=params,
            success_response_item_model=list[models.ProcessingJob],
        )

    def get_processing_job(
        self,
        processing_job_id: uuid.UUID,
    ) -> models.ProcessingJob:
        """
        Retrieves a specific processing job by its id.

        Args:
            processing_job_id: The unique identifier of the processing job to retrieve.

        Raises:
            APIException: If the request fails.

        Returns:
            The ProcessingJob model retrieved from the API.
        """

        return self._request(
            "GET",
            f"/processingJobs/{processing_job_id}",
            success_response_item_model=models.ProcessingJob,
        )

    ### attributes ###
    def create_attributes(
        self,
        dataset_id: uuid.UUID,
        attributes: list[models.BulkAttributeCreate],
    ) -> models.BulkResponse:
        """Creates new attributes in the database. The limit is 500 per call.

        Args:
            dataset_id: The dataset id
            attributes: A list of AttributeCreate objects. Each object contains the
                file_path as a field.

        Returns:
            A BulkResponse with information on upload successes and failures.

        Raises:
            APIException: If the request fails.
            BulkUploadSizeRangeError: if the number of attributes exceeds the per call
                upload limit.
        """

        if len(attributes) > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.BulkUploadSizeRangeError(
                limit=HARIClient.BULK_UPLOAD_LIMIT, found_amount=len(attributes)
            )

        # 1. parse attributes to dicts before upload
        attribute_dicts = [attribute.model_dump() for attribute in attributes]

        # 2. send attributes to HARI
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/attributes:bulk",
            json=attribute_dicts,
            success_response_item_model=models.BulkResponse,
        )

    def create_attribute(
        self,
        id: uuid.UUID,
        dataset_id: uuid.UUID,
        name: str,
        annotatable_id: str,
        value: models.typeT,
        annotatable_type: typing.Literal[
            models.DataBaseObjectType.MEDIA,
            models.DataBaseObjectType.MEDIAOBJECT,
            models.DataBaseObjectType.INSTANCE,
        ],
        attribute_group: models.AttributeGroup = models.AttributeGroup.InitialAttribute,
        attribute_type: models.AttributeType | None = None,
        min: models.typeT | None = None,
        max: models.typeT | None = None,
        sum: models.typeT | None = None,
        cant_solves: int | None = None,
        solvability: float | None = None,
        aggregate: typing.Any | None = None,
        modal: typing.Any | None = None,
        credibility: float | None = None,
        convergence: float | None = None,
        ambiguity: float | None = None,
        median: typing.Any | None = None,
        variance: typing.Any | None = None,
        standard_deviation: typing.Any | None = None,
        range: typing.Any | None = None,
        average_absolute_deviation: typing.Any | None = None,
        cumulated_frequency: typing.Any | None = None,
        frequency: dict[str, int] | None = None,
        question: str | None = None,
        ml_predictions: dict[str, float] | None = None,
        ml_probability_distributions: dict[str, float] | None = None,
        repeats: int | None = None,
        possible_values: list[str] | None = None,
    ) -> models.AttributeResponse:
        """Create an attribute for a dataset.

        Args:
            dataset_id: The dataset id
            id: The attribute id
            name: The name of the attribute
            value: The value of the attribute
            annotatable_id: The annotatable id
            annotatable_type: The annotatable type
            attribute_group: The attribute group
            attribute_type: The attribute type
            min: The min value
            max: The max value
            sum: The sum value
            cant_solves: The cant solves value
            solvability: The solvability value
            aggregate: The aggregate value
            modal: The modal value
            credibility: The credibility value
            convergence: The convergence value
            ambiguity: The ambiguity value
            median: The median value
            variance: The variance value
            standard_deviation: The standard deviation value
            range: The range value
            average_absolute_deviation: The average absolute deviation value
            cumulated_frequency: The cumulated frequency value
            frequency: The frequency value
            question: The question value
            range: The range value
            possible_values: The possible values for the given attribute
            repeats: The number of times the attribute was annotated
            ml_predictions: The ML predictions for the attribute
            ml_probability_distributions: The ML probability distributions for the attribute

        Returns:
            The created attribute.
        """
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/attributes",
            json=self._pack(locals(), ignore=["dataset_id"], not_none=["question"]),
            success_response_item_model=models.AttributeResponse,
        )

    def get_attributes(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.AttributeResponse]:
        """Returns all attributes of a dataset

        Args:
            dataset_id: The dataset id
            archived: if true, return only archived attributes; if false (default), return non-archived attributes.
            limit: The maximum number of attributes to return
            skip: The number of attributes to skip
            query: A query to filter attributes
            sort: A order by which to sort attributes
            projection: A dictionary of fields to return

        Returns:
            A list of attributes

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributes",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeResponse],
        )

    def get_attribute_value_count(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> models.FilterCount:
        """Calculates the number of attribute values for a given filter setting

        Args:
            dataset_id: The dataset id
            archived: Whether to consider archived attribute values
            query: Query

        Returns:
             a FilterCount object containing the total count of attribute values returned by the query.

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributeValues:count",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.FilterCount,
        )

    def get_attribute_value(
        self,
        dataset_id: uuid.UUID,
        attribute_id: str,
        annotatable_id: str,
        archived: bool | None = False,
    ) -> models.AttributeValueResponse:
        """Returns an attribute value with a given attribute_id.

        Args:
            dataset_id: The dataset id
            attribute_id: The attribute id
            annotatable_id: The id of the annotatable the attribute belongs to
            archived: Whether to return archived attribute values

        Returns:
            The attribute with the given attribute_id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributeValues/{attribute_id}",
            params=self._pack(locals(), ignore=["dataset_id", "attribute_id"]),
            success_response_item_model=models.AttributeValueResponse,
        )

    def get_attribute_values(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
    ) -> list[models.AttributeValueResponse]:
        """Get attribute values of a dataset

        Args:
            dataset_id: The dataset id
            archived: Whether to get archived attribute values
            limit: The number of medias tu return
            skip: The number of medias to skip
            query: The filters to be applied to the search
            sort: The list of sorting parameters

        Returns:
            A list of attribute values in a dataset

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributeValues",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeValueResponse],
        )

    def get_attribute_values_paginated(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        batch_size: int = 100,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
    ) -> list[models.AttributeValueResponse]:
        """Returns attribute values of a dataset, but with pagination, could be used for larger datasets to avoid timeouts.

        Args:
            dataset_id: The dataset id
            archived: Whether to get archived attribute values
            batch_size: The number of attribute values to fetch per request. Defaults to 100.
            query: The filters to be applied to the search
            sort: The list of sorting parameters

        Returns:
            A list of attribute values in a dataset

        Raises:
            APIException: If the request fails.
        """

        total_attributes: int = self.get_attribute_value_count(
            dataset_id, archived, query
        ).total_count

        log.info(f"Fetching {total_attributes} attribute values ...")

        attribute_values: list[models.AttributeValueResponse] = []

        # Loop through attribute value pages until all are retrieved
        for skip in tqdm(range(0, total_attributes, batch_size)):
            attribute_values_page = self.get_attribute_values(
                dataset_id=dataset_id,
                archived=archived,
                limit=batch_size,
                skip=skip,
                query=query,
                sort=sort,
            )
            attribute_values.extend(attribute_values_page)

        log.info(f"Fetched {len(attribute_values)} attribute values successfully.")

        return attribute_values

    def get_attribute(
        self, dataset_id: uuid.UUID, attribute_id: str, annotatable_id: str
    ) -> models.AttributeResponse:
        """Returns an attribute with a given attribute_id.

        Args:
            dataset_id: The dataset id
            attribute_id: The attribute id
            annotatable_id: The id of the annotatable the attribute belongs to

        Returns:
            The attribute with the given attribute_id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributes/{attribute_id}",
            params=self._pack(locals(), ignore=["dataset_id", "attribute_id"]),
            success_response_item_model=models.AttributeResponse,
        )

    def update_attribute(
        self,
        dataset_id: uuid.UUID,
        attribute_id: str,
        annotatable_id: str,
        name: str | None = None,
        value: models.typeT | None = None,
        min: models.typeT | None = None,
        max: models.typeT | None = None,
        sum: models.typeT | None = None,
        cant_solves: int | None = None,
        solvability: float | None = None,
        aggregate: typing.Any | None = None,
        modal: typing.Any | None = None,
        credibility: float | None = None,
        convergence: float | None = None,
        ambiguity: float | None = None,
        median: typing.Any | None = None,
        variance: typing.Any | None = None,
        standard_deviation: typing.Any | None = None,
        range: typing.Any | None = None,
        average_absolute_deviation: typing.Any | None = None,
        cumulated_frequency: typing.Any | None = None,
        frequency: dict[str, int] | None = None,
        question: str | None = None,
        archived: bool | None = None,
        ml_predictions: dict[str, float] | None = None,
        ml_probability_distributions: dict[str, float] | None = None,
    ) -> models.AttributeResponse:
        """Updates the attribute with the given id.

        Args:
            dataset_id: The dataset id the attribute belongs to
            attribute_id: The attribute id
            annotatable_id: The annotatable id the attribute belongs to

            name: The name of the attribute
            value: The value of the attribute
            min: The min value
            max: The max value
            sum: The sum value
            cant_solves: The cant solves value
            solvability: The solvability value
            aggregate: The aggregate value
            modal: The modal value
            credibility: The credibility value
            convergence: The convergence value
            ambiguity: The ambiguity value
            median: The median value
            variance: The variance value
            standard_deviation: The standard deviation value
            range: The range value
            average_absolute_deviation: The average absolute deviation value
            cumulated_frequency: The cumulated frequency value
            frequency: The frequency value
            question: The question value
            archived: The archived value
            range: The range value
            ml_predictions: The parameters of the posterior Dirichlet distribution
            ml_probability_distributions: The the Dirichlet distribution values

        Returns:
            The updated attribute

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PATCH",
            f"/datasets/{dataset_id}/attributes/{attribute_id}",
            params={"annotatable_id": annotatable_id},
            json=self._pack(
                locals(), ignore=["dataset_id", "attribute_id", "annotatable_id"]
            ),
            success_response_item_model=models.AttributeResponse,
        )

    def delete_attribute(
        self, dataset_id: uuid.UUID, attribute_id: str, annotatable_id: str
    ) -> str:
        """Delete an attribute from a dataset.

        Args:
            dataset_id: The ID of the dataset.
            attribute_id: The ID of the attribute.
            annotatable_id: The id of the annotatable the attribute belongs to

        Returns:
            The deleted attribute

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "DELETE",
            f"/datasets/{dataset_id}/attributes/{attribute_id}",
            params=self._pack(locals(), ignore=["dataset_id", "attribute_id"]),
            success_response_item_model=str,
        )

    def get_attribute_metadata(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> list[models.AttributeMetadataResponse]:
        """Returns attribute metadata of a dataset.

        Args:
            dataset_id: The dataset id
            archived: if true, return only archived attribute metadata; if false (default), return non-archived attribute metadata.
            query: A query to filter attribute metadata

         Returns:
            A list of attribute metadata

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "GET",
            f"/datasets/{dataset_id}/attributeMetadata",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.AttributeMetadataResponse],
        )

    def get_visualisation_configs(
        self,
        dataset_id: uuid.UUID,
        archived: bool | None = False,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        limit: int | None = None,
        skip: int | None = None,
    ) -> list[models.VisualisationConfiguration]:
        """
        Retrieve the visualization configurations for a given dataset.

        Args:
            dataset_id (UUID): The ID of the dataset for which to retrieve visualization configurations.
            archived: if true, return only archived visualisation configurations; if false (default), return non-archived visualisation configurations.
            query: The filters to be applied to the search
            sort: The list of sorting parameters
            limit: How many visualisation_configs to return
            skip: How many visualisation_configs to skip

        Returns:
            list[models.VisualisationConfiguration]: A list of visualization configuration objects.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/visualisationConfigs",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.VisualisationConfiguration],
        )

    ### AI Nano Tasks ###

    def get_multiple_aint_learning_data(
        self,
    ) -> list[models.AINTLearningData]:
        """
        !!! Only available for qm internal users !!!

        Retrieve all AINT learning data available to the user.

        Returns:
            A list of AINT learning data objects.
        """
        return self._request(
            "GET",
            f"/aintLearningData",
            success_response_item_model=list[models.AINTLearningData],
        )

    def get_aint_learning_data(
        self, aint_learning_data_id: uuid.UUID
    ) -> models.AINTLearningData:
        """
        !!! Only available for qm internal users !!!

        Get a single AINT learning data by its ID.

        Args:
            aint_learning_data_id: The unique identifier of the AINT learning data.

        Returns:
            The requested AINT learning data.
        """
        return self._request(
            "GET",
            f"/aintLearningData/{aint_learning_data_id}",
            success_response_item_model=models.AINTLearningData,
        )

    def create_aint_learning_data(
        self,
        name: str,
        training_attributes: list[models.TrainingAttribute],
        id: uuid.UUID | None = None,
        status: models.AIAnnotationRunStatus | None = None,
        created_at: datetime.datetime | None = None,
        updated_at: datetime.datetime | None = None,
        archived_at: datetime.datetime | None = None,
        owner: uuid.UUID | None = None,
        user_group: str | None = None,
    ) -> models.AINTLearningData:
        """
        !!! Only available for qm internal users !!!

        Create a new AINT learning data from training attributes.

        Args:
            name: A descriptive name for the AINT learning data.
            training_attributes: The training attributes to be used in the AINT learning data.
            user_group: The user group for creating the AINT learning data (default: None).
            id: The id of the AINT learning data. If None, random id will be generated during creation.
            status: The status of the AINT learning data.
            created_at: The creation date of the AINT learning data.
            updated_at: The update date of the AINT learning data.
            archived_at: The archived date of the AINT learning data.
            owner: The owner of the AINT learning data.

        Returns:
            Created AINT learning data object.
        """

        body = {
            key: value
            for key, value in locals().items()
            if value is not None and key not in ["self", "training_attributes"]
        }

        training_attribute_dicts = [
            training_attribute.model_dump()
            for training_attribute in training_attributes
        ]

        body["training_attributes"] = training_attribute_dicts

        return self._request(
            "POST",
            "/aintLearningData",
            json=body,
            success_response_item_model=models.AINTLearningData,
        )

    def update_aint_learning_data(
        self,
        aint_learning_data_id: uuid.UUID,
        name: str | None = None,
        question: str | None = None,
        user_group: str | None = None,
        status: models.AINTLearningDataStatus | None = None,
    ) -> models.AINTLearningData:
        """
        !!! Only available for qm internal users !!!

        Update AINT learning data.

        Args:
            aint_learning_data_id: The unique identifier of the AINT learning data.
            name: The desired name of the AINT learning data.
            question: The desired question of the AINT learning data.
            user_group: The desired user group of the AINT learning data.
            status: The desired status of the AINT learning data.

        Returns:
           Updated AINT learning data.

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "PATCH",
            f"/aintLearningData/{aint_learning_data_id}",
            json=self._pack(locals(), ignore=["aint_learning_data_id"]),
            success_response_item_model=models.AINTLearningData,
        )

    def delete_aint_learning_data(
        self,
        aint_learning_data_id: uuid.UUID,
    ) -> str:
        """
        !!! Only available for qm internal users !!!

        Delete AINT learning data.

        Args:
            aint_learning_data_id: The unique identifier of the AINT learning data.

        Returns:
           Deleted AINT learning data id.

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "DELETE",
            f"/aintLearningData/{aint_learning_data_id}",
            success_response_item_model=str,
        )

    def get_ml_annotation_models(
        self,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MlAnnotationModel]:
        """
        Retrieve all ml annotation models available to the user.

        Args:
            projection: The fields to be returned (dictionary keys with value True are returned,
            keys with value False are not returned).

        Returns:
             A list of ml annotation models.
        """
        return self._request(
            "GET",
            f"/mlAnnotationModels",
            params=self._pack(locals()),
            success_response_item_model=list[models.MlAnnotationModel],
        )

    def get_ml_annotation_model_by_id(
        self,
        ml_annotation_model_id: uuid.UUID,
        projection: dict[str, bool] | None = None,
    ) -> models.MlAnnotationModel:
        """
        Retrieve a specific ml model by its ID.

        Args:
            ml_annotation_model_id: The unique identifier of the AI annotation model.
            projection: The fields to be returned (dictionary keys with value True are returned,
            keys with value False are not returned).

        Returns:
            The requested ml model.
        """
        return self._request(
            "GET",
            f"/mlAnnotationModels/{ml_annotation_model_id}",
            params=self._pack(locals(), ignore=["ml_annotation_model_id"]),
            success_response_item_model=models.MlAnnotationModel,
        )

    def get_ml_annotation_models_by_training_ann_run_id(
        self,
        annotation_run_id: uuid.UUID,
    ) -> list[models.MlAnnotationModel]:
        """
        Get all ml annotation  models trained on the data of a specific annotation run.

        Args:
            annotation_run_id: The id of the annotation run used for model training.

        Returns:
            The list of ml annotation models trained on the data of the annotation run.

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/annotationRun/{annotation_run_id}/mlAnnotationModels",
            success_response_item_model=list[models.MlAnnotationModel],
        )

    def train_ml_annotation_model(
        self,
        name: str,
        aint_learning_data_id: uuid.UUID | None = None,
        reference_set_annotation_run_id: uuid.UUID | None = None,
        id: uuid.UUID | None = None,
        dataset_id: uuid.UUID | None = None,
        created_at: datetime.datetime | None = None,
        updated_at: datetime.datetime | None = None,
        archived_at: datetime.datetime | None = None,
        owner: uuid.UUID | None = None,
        user_group: str | None = None,
    ) -> models.MlAnnotationModel:
        """
        Train a new ml annotation model on the specified AINT learning data or reference set of the specified annotation run.

        Args:
            name: A descriptive name for the ml annotation model.
            aint_learning_data_id: The unique identifier of the AINT learning data to use for training.
            reference_set_annotation_run_id: The unique identifier of the annotation run to use the data for training from.
            id: The id of the model. If None, random id will be generated during creation.
            dataset_id: The dataset id to train the model on.
            created_at: The creation timestamp of the ml annotation model.
            updated_at: The update timestamp of the ml annotation model.
            archived_at: The archived timestamp of the ml annotation model.
            owner: The owner of the ml annotation model.
            user_group: The user group for scoping this annotation run (default: None).

        Either aint_learning_data_id or reference_set_annotation_run_id must be specified.

        Returns:
            The created ml annotation model.
        Raises:
            APIException: If the request fails.
        """

        body = {
            key: value
            for key, value in locals().items()
            if value is not None and key not in ["self"]
        }

        return self._request(
            "POST",
            "/mlAnnotationModels",
            json=body,
            success_response_item_model=models.MlAnnotationModel,
        )

    def update_ml_annotation_model(
        self,
        ml_annotation_model_id: uuid.UUID,
        name: str | None = None,
        user_group: str | None = None,
        status: models.MLAnnotationModelStatus | None = None,
        training_subset_id: uuid.UUID | None = None,
        validation_subset_id: uuid.UUID | None = None,
        test_subset_id: uuid.UUID | None = None,
        reference_set_annotation_run_id: uuid.UUID | None = None,
        model_weight_location: str | None = None,
        automation_correctness_curve: dict | None = None,
        aint_learning_data_id: uuid.UUID | None = None,
    ) -> models.MlAnnotationModel:
        """
        Update a ml annotation model.

        Args:
            ml_annotation_model_id: The id of the ml annotation model.
            name: new desired name for the ml annotation model.
            user_group: new desired user group for the ml annotation model.
            status: new desired status for the ml annotation model.
            training_subset_id: training subset id for the ml annotation model.
            validation_subset_id: validation subset id for the ml annotation model.
            test_subset_id: test subset id for the ml annotation model.
            reference_set_annotation_run_id: reference set annotation run id for the ml annotation model.
            model_weight_location: model weight location for the ml annotation model.
            automation_correctness_curve: automation correctness curve for the ml annotation model.
            aint_learning_data_id: AINT learning data id for the ml annotation model.

        Returns:
            The updated ml annotation model.

        Raises:
            APIException: If the request fails.
        """

        body = {
            key: value
            for key, value in locals().items()
            if value is not None and key not in ["self", "ml_annotation_model_id"]
        }

        return self._request(
            "PATCH",
            f"/mlAnnotationModels/{ml_annotation_model_id}",
            json=body,
            success_response_item_model=models.MlAnnotationModel,
        )

    def delete_ml_annotation_model(
        self,
        ml_annotation_model_id: uuid.UUID,
    ) -> str:
        """
        Delete a ml annotation model.

        Args:
            ml_annotation_model_id: The id of the ml annotation model.

        Returns:
            The id of the deleted ml annotation model.

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "DELETE",
            f"/mlAnnotationModels/{ml_annotation_model_id}",
            success_response_item_model=str,
        )

    def get_ai_annotation_runs(
        self,
    ) -> list[models.AIAnnotationRun]:
        """
        Retrieve all AI annotation runs available to the user.

        Returns:
            A list of AI annotation runs.
        """
        return self._request(
            "GET",
            f"/aiAnnotationRuns",
            success_response_item_model=list[models.AIAnnotationRun],
        )

    def get_ai_annotation_run(
        self, ai_annotation_run_id: uuid.UUID
    ) -> models.AIAnnotationRun:
        """
        Retrieve a specific AI annotation run by its ID.

        Args:
            ai_annotation_run_id: The unique identifier of the AI annotation run.

        Returns:
            The requested AI annotation run.
        """
        return self._request(
            "GET",
            f"/aiAnnotationRuns/{ai_annotation_run_id}",
            success_response_item_model=models.AIAnnotationRun,
        )

    def start_ai_annotation_run(
        self,
        name: str,
        dataset_id: uuid.UUID,
        subset_id: uuid.UUID,
        ml_annotation_model_id: uuid.UUID,
        attribute_metadata_id: uuid.UUID | None = None,
        id: uuid.UUID | None = None,
        status: models.AIAnnotationRunStatus | None = None,
        created_at: datetime.datetime | None = None,
        updated_at: datetime.datetime | None = None,
        archived_at: datetime.datetime | None = None,
        owner: uuid.UUID | None = None,
        user_group: str | None = None,
    ) -> models.AIAnnotationRun:
        """
        Start a new AI annotation run. Applies the specified ml annotation model to the dataset and subset.

        Args:
            name: A descriptive name for the AI annotation run.
            dataset_id: The unique identifier of the dataset to be annotated.
            subset_id: The unique identifier of the subset to be annotated.
            ml_annotation_model_id: The unique identifier of the ml annotation model to use.
            user_group: The user group for scoping this annotation run (default: None).
            attribute_metadata_id: The unique identifier of the attribute metadata to use for the annotation run (default: None).
            id: The id of the AINT learning data. If None, random id will be generated during creation.
            status: The status of the AI annotation run.
            created_at: The creation timestamp of the AI annotation run.
            updated_at: The update timestamp of the AI annotation run.
            archived_at: The archived timestamp of the AI annotation run.
            owner: The owner of the AI annotation run.

        Returns:
            The created AI annotation run.
        """

        body = {
            key: value
            for key, value in locals().items()
            if value is not None and key != "self"
        }

        return self._request(
            "POST",
            "/aiAnnotationRuns",
            json=body,
            success_response_item_model=models.AIAnnotationRun,
        )

    def update_ai_annotation_run(
        self,
        ai_annotation_run_id: uuid.UUID,
        name: str | None = None,
        user_group: str | None = None,
        status: models.AIAnnotationRunStatus | None = None,
        attribute_metadata_id: uuid.UUID | None = None,
    ) -> models.AIAnnotationRun:
        """
        Update an AI annotation run.

        Args:
            ai_annotation_run_id: The id of the AI annotation run.
            name: new desired name for the AI annotation run.
            user_group: new desired user group for the AI annotation run.
            status: status for the AI annotation run.
            attribute_metadata_id: attribute metadata id for the AI annotation run.

        Returns:
            The updated AI annotation run.

        Raises:
            APIException: If the request fails.
        """

        body = {
            key: value
            for key, value in locals().items()
            if value is not None and key not in ["self", "ai_annotation_run_id"]
        }

        return self._request(
            "PATCH",
            f"/aiAnnotationRuns/{ai_annotation_run_id}",
            json=body,
            success_response_item_model=models.AIAnnotationRun,
        )

    def delete_ai_annotation_run(
        self,
        ai_annotation_run: uuid.UUID,
    ) -> str:
        """
        Delete an AI annotation run.

        Args:
            ai_annotation_run: The id of the AI annotation run.

        Returns:
            The id of the deleted AI annotation run.

        Raises:
            APIException: If the request fails.
        """

        return self._request(
            "DELETE",
            f"/aiAnnotationRuns/{ai_annotation_run}",
            success_response_item_model=str,
        )
