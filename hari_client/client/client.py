import datetime
import pathlib
import types
import typing
import uuid

import pydantic
import requests

from hari_client.client import errors
from hari_client.config import config
from hari_client.models import models
from hari_client.utils import logger

T = typing.TypeVar("T")

log = logger.setup_logger(__name__)


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
            + f" because the combination of received data and expected response_model is unhandled."
            + f"{response_data=}.",
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

        # do request and basic error handling
        response = self.session.request(method, full_url, **kwargs)
        if not response.ok:
            raise errors.APIError(response)

        if not "application/json" in response.headers.get("Content-Type", ""):
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

    def _upload_file(self, file_path: str, upload_url: str) -> None:
        with open(file_path, "rb") as fp:
            response = requests.put(upload_url, data=fp)
            response.raise_for_status()

    def _upload_visualisation_file_with_presigned_url(
        self, dataset_id: str, visualisation_config_id: str, file_path: str
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
        dataset_id: str,
        file_paths: list[str],
    ) -> list[models.MediaUploadUrlInfo]:
        """Creates a presigned S3 upload url for every media file and uploads them.

        Args:
            dataset_id: The dataset id
            file_paths: The paths to the files to upload. All files have to have the same file extension.

        Returns:
            A list of MediaUploadUrlInfo objects.

        Raises:
            UploadingFilesWithDifferentFileExtensionsError: if the file extensions of the files are different.
        """

        # validate that all files have the same file extension
        file_extensions = set(
            [pathlib.Path(file_path).suffix for file_path in file_paths]
        )
        if len(file_extensions) > 1:
            raise errors.UploadingFilesWithDifferentFileExtensionsError(file_extensions)

        # 1. get presigned upload url for the files
        presign_response = self.get_presigned_media_upload_url(
            dataset_id=dataset_id,
            file_extension=list(file_extensions)[0],
            batch_size=len(file_paths),
        )

        # 2. upload the image
        for idx, file_path in enumerate(file_paths):
            self._upload_file(
                file_path=file_path, upload_url=presign_response[idx].upload_url
            )

        return presign_response

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
        visibility_status: models.VisibilityStatus
        | None = models.VisibilityStatus.VISIBLE,
        data_root: str | None = "custom_upload",
        id: str | None = None,
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

        Returns:
            The created dataset

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "POST",
            f"/datasets",
            json=self._pack(locals(), not_none=["creation_timestamp", "id"]),
            success_response_item_model=models.Dataset,
        )

    def update_dataset(
        self,
        dataset_id: str,
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

    def get_dataset(self, dataset_id: str) -> models.DatasetResponse:
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
    ) -> list[models.DatasetResponse]:
        """Returns all datasets that a user has access to.

        Args:
            subset: Return also subsets. If False, returns only parent datasets
            visibility_statuses: Visibility statuses of the returned datasets

        Returns:
            A list of datasets

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets",
            params=self._pack(locals()),
            success_response_item_model=list[models.DatasetResponse],
        )

    def get_subsets_for_dataset(
        self,
        dataset_id: str,
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

    def archive_dataset(self, dataset_id: str) -> str:
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
            f"/subsets:createFiltered",
            params=self._pack(
                locals(), ignore=["filter_options", "secondary_filter_options"]
            ),
            json=body,
            success_response_item_model=str,
        )

    ### media ###
    def create_media(
        self,
        dataset_id: str,
        file_path: str,
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

        Returns:
            Media that was just created

        Raises:
            APIException: If the request fails.
        """

        # 1. upload file
        media_upload_responses = self._upload_media_files_with_presigned_urls(
            dataset_id, file_paths=[file_path]
        )
        media_url = media_upload_responses[0].media_url

        # 2. create the media in HARI
        json_body = self._pack(
            locals(),
            ignore=["file_path", "dataset_id", "media_upload_responses"],
        )
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias",
            json=json_body,
            success_response_item_model=models.Media,
        )

    def create_medias(
        self, dataset_id: str, medias: list[models.BulkMediaCreate]
    ) -> models.BulkResponse:
        """Accepts multiple files, uploads them, and creates the medias in the db.
        The limit is 500 per call.

        Args:
            dataset_id: The dataset id
            medias: A list of MediaCreate objects. Each object contains the file_path as a field.

        Returns:
            A BulkResponse with information on upload successes and failures.

        Raises:
            APIException: If the request fails.
            UploadingFilesWithDifferentFileExtensionsError: if the file extensions of the files are different.
            BulkUploadSizeRangeError: if the number of medias exceeds the per call upload limit.
            MediaCreateMissingFilePathError: if a MediaCreate object is missing the file_path field.
        """

        if len(medias) > HARIClient.BULK_UPLOAD_LIMIT:
            raise errors.BulkUploadSizeRangeError(
                limit=HARIClient.BULK_UPLOAD_LIMIT, found_amount=len(medias)
            )

        # 1. upload files
        file_paths = []
        for media in medias:
            if not media.file_path:
                raise errors.MediaCreateMissingFilePathError(media)
            file_paths.append(media.file_path)

        media_upload_responses = self._upload_media_files_with_presigned_urls(
            dataset_id, file_paths=file_paths
        )

        # 2. parse medias to dicts and set their media_urls
        media_dicts = []
        for idx, media in enumerate(medias):
            media_dicts.append(media.dict())
            media_dicts[idx]["media_url"] = media_upload_responses[idx].media_url

        # 3. create the medias in HARI
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias:bulk",
            json=media_dicts,
            success_response_item_model=models.BulkResponse,
        )

    def update_media(
        self,
        dataset_id: str,
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
        dataset_id: str,
        media_id: str,
        presign_media: bool | None = True,
        archived: bool | None = False,
        projection: dict | None = None,
    ) -> models.MediaResponse:
        """Get a media by its id.

        Args:
            dataset_id: The dataset id
            media_id: The media id
            presign_media: Whether to presign media
            archived: Return archived media
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            The media object matching the provided id

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
        dataset_id: str,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
        projection: dict[str, bool] | None = None,
    ) -> list[models.MediaResponse]:
        """Get all medias of a dataset

        Args:
            dataset_id: The dataset id
            archived: Whether to get archived media
            presign_medias: Whether to presign medias
            limit: The number of medias tu return
            skip: The number of medias to skip
            query: The filters to be applied to the search
            sort: The list of sorting parameters
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            A list of all medias in a dataset

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.MediaResponse],
        )

    def archive_media(self, dataset_id: str, media_id: str) -> str:
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
        dataset_id: str,
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
        self, dataset_id: str, subset_id: str | None = None
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
        self, dataset_id: str, subset_id: str | None = None
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
        dataset_id: str,
        subset_id: str | None = None,
        archived: bool | None = False,
    ) -> dict[str, typing.Any]:
        """Get a dictionary describing the number of medias and number of corresponding media objects

        Args:
            dataset_id: The dataset id
            subset_id: The subset id or None, if the result for the whole dataset
            archived: Whether to consider archived medias (default: False)

        Returns:
            Dictionary, where the key is the number of medias in the dataset having value number of media objects

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
        dataset_id: str,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> models.FilterCount:
        """Calculates the number of medias for a given filter setting

        Args:
            dataset_id: The dataset id
            archived: Whether to consider archived medias
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
        dataset_id: str,
        name: str,
        parameters: models.CropVisualisationConfigParameters
        | models.TileVisualisationConfigParameters
        | models.RenderedVisualisationConfigParameters,
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
                "parameters": parameters.dict(exclude_unset=True),
            },
            success_response_item_model=models.VisualisationConfiguration,
        )

    def add_visualisation_to_media(
        self,
        dataset_id: str,
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
        self, dataset_id: str, file_extension: str, batch_size: int
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
        dataset_id: str,
        media_id: str,
        back_reference: str,
        source: models.DataSource,
        archived: bool | None = False,
        scene_id: str | None = None,
        realWorldObject_id: str | None = None,
        visualisations: list[models.VisualisationUnion] | None = None,
        subset_ids: list | None = None,
        instance_id: str | None = None,
        object_category: str | None = None,
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
        reference_data = reference_data.dict() if reference_data else None
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/mediaObjects",
            json=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.MediaObject,
        )

    def create_media_objects(
        self,
        dataset_id: str,
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
        media_object_dicts = [media_object.dict() for media_object in media_objects]

        # 2. send media_objects to HARI
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/mediaObjects:bulk",
            json=media_object_dicts,
            success_response_item_model=models.BulkResponse,
        )

    def update_media_object(
        self,
        dataset_id: str,
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
        object_category: str | None = None,
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
        return self._request(
            "PATCH",
            f"/datasets/{dataset_id}/mediaObjects/{media_object_id}",
            json=self._pack(locals(), ignore=["dataset_id", "media_object_id"]),
            success_response_item_model=models.MediaObject,
        )

    def get_media_object(
        self,
        dataset_id: str,
        media_object_id: str,
        archived: bool | None = False,
        presign_media: bool | None = True,
        projection: dict | None = None,
    ) -> models.MediaObjectResponse:
        """Fetches a media_object by its id.

        Args:
            dataset_id: dataset id
            media_object_id: media object id
            archived: Archived
            presign_media: Presign Media
            projection: The fields to be returned (dictionary keys with value True are returned, keys with value False
                are not returned)

        Returns:
            List of media object projections

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
        dataset_id: str,
        archived: bool | None = False,
        presign_medias: bool | None = True,
        limit: int | None = None,
        skip: int | None = None,
        query: models.QueryList | None = None,
        sort: list[models.SortingParameter] | None = None,
    ) -> list[models.MediaObjectResponse]:
        """Queries the database based on the submitted parameters and returns a

        Args:
            dataset_id: dataset id
            archived: Archived
            presign_medias: Presign Medias
            limit: Limit
            skip: Skip
            query: Query
            sort: Sort

        Returns:
            list

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/mediaObjects",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=list[models.MediaObjectResponse],
        )

    def archive_media_object(self, dataset_id: str, media_object_id: str) -> str:
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
        self, dataset_id: str, subset_id: str | None = None
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
        dataset_id: str,
        archived: bool | None = False,
        query: models.QueryList | None = None,
    ) -> models.FilterCount:
        """Calculates the number of mediaObjects found in the db for a given filter setting

        Args:
            dataset_id: dataset id
            archived: Archived
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
        dataset_id: str,
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
    def trigger_thumbnails_creation_job(
        self,
        dataset_id: uuid.UUID,
        subset_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
        max_size: tuple[int, int] | None = None,
        aspect_ratio: tuple[int, int] | None = None,
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers the creation of thumbnails for a given dataset.

        Args:
            dataset_id: The dataset id
            subset_id: The subset id
            trace_id: An id to trace the processing job(s). Is created by the user
            max_size: The maximum size of the thumbnails
            aspect_ratio: The aspect ratio of the thumbnails

        Raises:
            APIException: If the request fails.

        Returns:
            list[models.BaseProcessingJobMethod]: the methods being executed
        """
        params = {"subset_id": subset_id}

        if trace_id is not None:
            params["trace_id"] = trace_id

        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/thumbnails",
            params=params,
            json=self._pack(locals(), ignore=["dataset_id", "subset_id", "trace_id"]),
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

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

    def trigger_crops_creation_job(
        self,
        dataset_id: uuid.UUID,
        subset_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
        padding_percent: int | None = None,
        padding_minimum: int | None = None,
        max_size: tuple[int, int] | None = None,
        aspect_ratio: tuple[int, int] | None = None,
    ) -> list[models.BaseProcessingJobMethod]:
        """Creates the crops for a given dataset if the correct api key is provided in the

        Args:
            dataset_id: The dataset id
            subset_id: The subset id
            trace_id: An id to trace the processing job(s). Is created by the user
            padding_percent: The padding (in percent) to add to the crops
            padding_minimum: The minimum padding to add to the crops
            max_size: The max size of the crops
            aspect_ratio: The aspect ratio of the crops

        Raises:
            APIException: If the request fails.

        Returns:
            list[models.BaseProcessingJobMethod]: The methods being executed
        """
        params = {"subset_id": subset_id}

        if trace_id is not None:
            params["trace_id"] = trace_id

        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/crops",
            params=params,
            json=self._pack(locals(), ignore=["dataset_id", "subset_id", "trace_id"]),
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

    def trigger_metadata_rebuild_job(
        self, dataset_ids: list[uuid.UUID], trace_id: uuid.UUID | None = None
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers execution of one or more jobs which (re-)build metadata for all provided datasets.

        Args:
            dataset_ids: dataset_ids to rebuild metadata for max 10.
            trace_id: An id to trace the processing job

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
            f"/metadata:rebuild",
            json=self._pack(locals()),
            success_response_item_model=list[models.BaseProcessingJobMethod],
        )

    def trigger_dataset_metadata_rebuild_job(
        self,
        dataset_id: uuid.UUID,
        subset_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
    ) -> list[models.BaseProcessingJobMethod]:
        """Triggers execution of one or more jobs which (re-)build metadata for the provided dataset.

        Args:
            dataset_id: dataset_id to rebuild metadata for
            subset_id: subset_id to rebuild metadata for
            trace_id: An id to trace the processing job

        Returns:
            The methods being executed
        """
        params = {}
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
        trace_id: str = None,
    ) -> list[models.ProcessingJob]:
        """
        Retrieves the list of processing jobs that the user has access to.

        Args:
            trace_id: Helps to identify related processing jobs. Use the trace_id that was specified when triggering a processing job

        Raises:
            APIException: If the request fails.

        Returns:
            list[models.ProcessingJob]: A list of processing jobs for the user
            or [] if there are no jobs of trace_id is not found.
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
        processing_job_id: str,
    ) -> models.ProcessingJob:
        """
        Retrieves a specific processing job by its id.

        Args:
            processing_job_id: The unique identifier of the processing job to retrieve.

        Raises:
            APIException: If the request fails.

        Returns:
            models.ProcessingJob: The ProcessingJob model retrieved from the API.
        """

        return self._request(
            "GET",
            f"/processingJobs/{processing_job_id}",
            success_response_item_model=models.ProcessingJob,
        )
