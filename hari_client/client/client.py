import datetime
import pathlib
import typing

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
        - isinstance(response_data, response_model) == True (for example both are int, list, dict, etc.)
            - the response_data is returned without modification
        - both response_data and response_model are None (meaning you expect to receive None as response)
            - None is returned
        - response_data is a dict, then response_model is treated like a pydantic model and the response_data
          is parsed into an instance of the response_model.
        - response_data is a list and response_model isn't, then response_model will be treated like a pydantic model
          and every item in the list as a dict to be parsed into an instance of the response_model.


    Args:
        response_data (typing.Any): the input data
        response_model (typing.Type[T]): the generic response_model type

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
        elif isinstance(response_data, response_model):
            # this case works when the response_json is already an instance of the expected response_model.
            # For example any of the basic builtins (str, int, etc.) or dict or list.
            return response_data
        elif isinstance(response_data, dict):
            return response_model(**response_data)
        elif isinstance(response_data, list):
            # this case works when the response_data is a list of dicts and the expectation is that each
            # dict can be parsed into the response_model.
            return [response_model(**item_dict) for item_dict in response_data]
        else:
            raise errors.ParseResponseModelError(
                response_data=response_data,
                response_model=response_model,
                message=f"Can't parse response_data into response_model {response_model},"
                + "because the combination of received data and expected response_model is unhandled."
                + f"{response_data=}.",
            )
    except Exception as err:
        raise errors.ParseResponseModelError(
            response_data=response_data,
            response_model=response_model,
            message=f"Failed to parse response_data into response_model {response_model}. {response_data=}",
        ) from err


class HARIClient:
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
    ) -> typing.Union[T, None]:
        """Make a request to the API.

        Args:
            method (str): The HTTP method to use.
            url (str): The URL to request.
            success_response_item_model (typing.Type[T]): The response model class to parse the response
                json body into when the request status is a success code.
            error_response_item_model (typing.Type[U]): The response model class to parse the response
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

    def _upload_to_presigned_url(
        self,
        dataset_id: str,
        file_path: str,
        visualisation_config_id: typing.Optional[str] = None,
    ) -> str:
        """Upload a single file to a presigned url of AWS (media or visualisation).

        Args:
            dataset_id: The dataset id
            file_path: The path to the file to upload
            visualisation_config_id: If it is set, the file is uploaded as a visualisation with that visualisation
                 config id, otherwise as a media.

        Returns:
            The URL where the file was uploaded to
        """

        def upload_file(filename: str, upload_url: str):
            with open(filename, "rb") as fp:
                response = requests.put(upload_url, data=fp)
                response.raise_for_status()

        # 1. get presigned upload url for the image
        file_extension = pathlib.Path(file_path).suffix
        if visualisation_config_id is not None:
            presign_response = self.get_presigned_visualisation_upload_url(
                dataset_id=dataset_id,
                file_extension=file_extension,
                visualisation_config_id=visualisation_config_id,
                batch_size=1,
            )
        else:
            presign_response = self.get_presigned_media_upload_url(
                dataset_id=dataset_id, file_extension=file_extension, batch_size=1
            )

        # 2. upload the image
        upload_file(filename=file_path, upload_url=presign_response[0].upload_url)

        return (
            presign_response[0].visualisation_url
            if visualisation_config_id is not None
            else presign_response[0].media_url
        )

    ### dataset ###
    def create_dataset(
        self,
        name: str,
        mediatype: typing.Optional[models.MediaType] = "image",
        customer: typing.Optional[str] = None,
        creation_timestamp: typing.Optional[str] = None,
        reference_files: typing.Optional[list] = None,
        num_medias: typing.Optional[int] = 0,
        num_media_objects: typing.Optional[int] = 0,
        num_annotations: typing.Optional[int] = None,
        num_attributes: typing.Optional[int] = None,
        num_instances: typing.Optional[int] = 0,
        color: typing.Optional[str] = "#FFFFFF",
        archived: typing.Optional[bool] = False,
        is_anonymized: typing.Optional[bool] = False,
        license: typing.Optional[str] = None,
        owner: typing.Optional[str] = None,
        current_snapshot_id: typing.Optional[int] = None,
        visibility_status: typing.Optional[
            models.VisibilityStatus
        ] = models.VisibilityStatus.VISIBLE,
        data_root: typing.Optional[str] = "custom_upload",
        id: typing.Optional[str] = None,
    ) -> models.Dataset:
        """Creates an empty dataset in the database.

        Args:
            name: Name of the dataset
            mediatype: MediaType of the dataset
            customer: User group the new dataset shall be avaialble to
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
        id: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        mediatype: typing.Optional[models.MediaType] = None,
        is_anonymized: typing.Optional[bool] = None,
        color: typing.Optional[str] = None,
        archived: typing.Optional[bool] = None,
        owner: typing.Optional[str] = None,
        current_snapshot_id: typing.Optional[int] = None,
        num_medias: typing.Optional[int] = None,
        num_media_objects: typing.Optional[int] = None,
        num_annotations: typing.Optional[int] = None,
        num_attributes: typing.Optional[int] = None,
        num_instances: typing.Optional[int] = None,
        visibility_status: typing.Optional[models.VisibilityStatus] = None,
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
        subset: typing.Optional[bool] = False,
        visibility_statuses: typing.Optional[tuple] = (
            models.VisibilityStatus.VISIBLE,
        ),
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
            success_response_item_model=models.DatasetResponse,
        )

    def get_subsets_for_dataset(
        self,
        dataset_id: str,
        visibility_statuses: typing.Optional[tuple] = (
            models.VisibilityStatus.VISIBLE,
        ),
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
            success_response_item_model=models.DatasetResponse,
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
        dataset_id: str,
        subset_type: models.SubsetType,
        subset_name: str,
        object_category: typing.Optional[bool] = False,
        visualisation_config_id: typing.Optional[str] = None,
    ) -> str:
        """creates a new subset based on a filter and uploads it to the database

        Args:
            dataset_id: Dataset Id
            subset_type: Type of the subset (media, media_object, instance, attribute)
            subset_name: The name of the subset
            object_category: True if the new subset shall be shown as a category for objects in HARI
            visualisation_config_id: Visualisation Config Id

        Returns:
            The new subset id

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "POST",
            f"/subsets:createFiltered",
            params=self._pack(locals()),
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
        scene_id: typing.Optional[str] = None,
        realWorldObject_id: typing.Optional[str] = None,
        frame_idx: typing.Optional[int] = None,
        frame_timestamp: typing.Optional[str] = None,
        back_reference_json: typing.Optional[str] = None,
        visualisations: typing.Optional[list[models.VisualisationUnion]] = None,
        subset_ids: typing.Union[set[str], None] = None,
        metadata: typing.Optional[
            typing.Union[models.ImageMetadata, models.PointCloudMetadata]
        ] = None,
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

        # 1. upload file to presigned URL
        media_url = self._upload_to_presigned_url(dataset_id, file_path)

        # 2. create the media in HARI
        json_body = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
            ],
        )
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/medias",
            json=json_body,
            success_response_item_model=models.Media,
        )

    def update_media(
        self,
        dataset_id: str,
        media_id: str,
        back_reference: typing.Optional[str] = None,
        archived: typing.Optional[bool] = None,
        scene_id: typing.Optional[str] = None,
        realWorldObject_id: typing.Optional[str] = None,
        visualisations: typing.Optional[list[models.VisualisationUnion]] = None,
        subset_ids: typing.Optional[list] = None,
        name: typing.Optional[str] = None,
        metadata: typing.Optional[
            typing.Union[models.ImageMetadata, models.PointCloudMetadata]
        ] = None,
        frame_idx: typing.Optional[int] = None,
        media_type: typing.Optional[models.MediaType] = None,
        frame_timestamp: typing.Optional[str] = None,
        back_reference_json: typing.Optional[str] = None,
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
        presign_media: typing.Optional[bool] = True,
        archived: typing.Optional[bool] = False,
        projection: typing.Optional[dict] = None,
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
        archived: typing.Optional[bool] = False,
        presign_medias: typing.Optional[bool] = True,
        limit: typing.Optional[int] = None,
        skip: typing.Optional[int] = None,
        query: typing.Optional[models.QueryList] = None,
        sort: typing.Optional[list[models.SortingParameter]] = None,
        projection: typing.Optional[dict[str, bool]] = None,
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
            success_response_item_model=models.MediaResponse,
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
            dataset_id (str): id of the dataset to which the visualisation will belong
            file_extension (str): the file extension of the file to be uploaded. For example: ".jpg", ".png"
            visualisation_config_id (str): id of the visualisation configuration of the visualisation
            batch_size (int): number of upload links and ids to generate. Valid range: 1 <= batch_size <= 500.

        Returns:
            list[models.VisualisationUploadUrlInfo]: A list with UploadUrlInfo objects containing the presigned
                upload URL and the media_url which should be used when creating the media.

        Raises:
            APIException: If the request fails.
            ValueError: If the validating input args fails.
        """
        if batch_size < 1 or batch_size > 500:
            raise ValueError(
                f"Expected batch_size to be in range 1 <= batch_size <= 500, but received: {batch_size}."
            )
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/visualisations/uploadUrl",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.VisualisationUploadUrlInfo,
        )

    def get_media_histograms(
        self, dataset_id: str, subset_id: typing.Optional[str] = None
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
            success_response_item_model=models.AttributeHistogram,
        )

    def get_instance_histograms(
        self, dataset_id: str, subset_id: typing.Optional[str] = None
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
            success_response_item_model=models.AttributeHistogram,
        )

    def get_media_object_count_statistics(
        self,
        dataset_id: str,
        subset_id: typing.Optional[str] = None,
        archived: typing.Optional[bool] = False,
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
        archived: typing.Optional[bool] = False,
        query: typing.Optional[models.QueryList] = None,
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
        parameters: typing.Union[
            models.CropVisualisationConfigParameters,
            models.TileVisualisationConfigParameters,
            models.RenderedVisualisationConfigParameters,
        ],
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
        visualisation_url = self._upload_to_presigned_url(
            dataset_id,
            file_path,
            visualisation_config_id=visualisation_configuration_id,
        )

        # 2. create the visualisation in HARI
        query_params = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
                "media_id",
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
            dataset_id (str): id of the dataset to which the media will belong
            file_extension (str): the file extension of the file to be uploaded. For example: ".jpg", ".png"
            batch_size (int): number of upload links and ids to generate. Valid range: 1 <= batch_size <= 500.

        Returns:
            list[models.MediaUploadUrlInfo]: A list with MediaUploadUrlInfo objects containing the presigned
                upload URL and the media_url which should be used when creating the media.

        Raises:
            APIException: If the request fails.
            ValueError: If the validating input args fails.
        """
        if batch_size < 1 or batch_size > 500:
            raise ValueError(
                f"Expected batch_size to be in range 1 <= batch_size <= 500, but received: {batch_size}."
            )
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/medias/uploadUrl",
            params=self._pack(locals(), ignore=["dataset_id"]),
            success_response_item_model=models.MediaUploadUrlInfo,
        )

    ### media object ###
    def create_media_object(
        self,
        dataset_id: str,
        media_id: str,
        back_reference: str,
        source: models.DataSource,
        archived: typing.Optional[bool] = False,
        scene_id: typing.Optional[str] = None,
        realWorldObject_id: typing.Optional[str] = None,
        visualisations: typing.Optional[list[models.VisualisationUnion]] = None,
        subset_ids: typing.Optional[list] = None,
        instance_id: typing.Optional[str] = None,
        object_category: typing.Optional[str] = None,
        qm_data: typing.Optional[list[models.GeometryUnion]] = None,
        reference_data: typing.Optional[models.GeometryUnion] = None,
        frame_idx: typing.Optional[int] = None,
        media_object_type: typing.Optional[models.MediaObjectType] = None,
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

    def update_media_object(
        self,
        dataset_id: str,
        media_object_id: str,
        back_reference: typing.Optional[str] = None,
        archived: typing.Optional[bool] = None,
        scene_id: typing.Optional[str] = None,
        realWorldObject_id: typing.Optional[str] = None,
        visualisations: typing.Optional[list[models.VisualisationUnion]] = None,
        subset_ids: typing.Optional[list] = None,
        media_id: typing.Optional[str] = None,
        instance_id: typing.Optional[str] = None,
        source: typing.Optional[models.DataSource] = None,
        object_category: typing.Optional[str] = None,
        qm_data: typing.Optional[list[models.GeometryUnion]] = None,
        reference_data: typing.Optional[models.GeometryUnion] = None,
        frame_idx: typing.Optional[int] = None,
        media_object_type: typing.Optional[models.MediaObjectType] = None,
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
        archived: typing.Optional[bool] = False,
        presign_media: typing.Optional[bool] = True,
        projection: typing.Optional[dict] = None,
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
        archived: typing.Optional[bool] = False,
        presign_medias: typing.Optional[bool] = True,
        limit: typing.Optional[int] = None,
        skip: typing.Optional[int] = None,
        query: typing.Optional[models.QueryList] = None,
        sort: typing.Optional[list[models.SortingParameter]] = None,
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
            success_response_item_model=models.MediaObjectResponse,
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
        self, dataset_id: str, subset_id: typing.Optional[str] = None
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
            success_response_item_model=models.AttributeHistogram,
        )

    def get_media_object_count(
        self,
        dataset_id: str,
        archived: typing.Optional[bool] = False,
        query: typing.Optional[models.QueryList] = None,
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
        visualisation_url = self._upload_to_presigned_url(
            dataset_id,
            file_path,
            visualisation_config_id=visualisation_configuration_id,
        )

        # 2. create the visualisation in HARI
        query_params = self._pack(
            locals(),
            ignore=[
                "file_path",
                "dataset_id",
                "media_object_id",
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
    def create_thumbnails(
        self,
        dataset_id: str,
        subset_id: str,
        max_size: typing.Optional[tuple[int]] = None,
        aspect_ratio: typing.Optional[tuple[int]] = None,
    ) -> None:
        """Triggers the creation of thumbnails for a given dataset.

        Args:
            dataset_id: The dataset id
            subset_id: The subset id
            max_size: The maximum size of the thumbnails
            aspect_ratio: The aspect ratio of the thumbnails

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/thumbnails",
            params={"subset_id": subset_id},
            json=self._pack(locals(), ignore=["dataset_id", "subset_id"]),
            success_response_item_model=None,
        )

    def update_histograms(
        self, dataset_id: str, compute_for_all_subsets: typing.Optional[bool] = False
    ) -> None:
        """Triggers the update of the histograms for a given dataset.

        Args:
            dataset_id: The dataset id
            compute_for_all_subsets: Update histograms for all subsets

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/histograms",
            params={"compute_for_all_subsets": compute_for_all_subsets},
            success_response_item_model=None,
        )

    def create_crops(
        self,
        dataset_id: str,
        subset_id: str,
        box_type: typing.Optional[list[models.DataSource]] = None,
        aspect_ratio: typing.Optional[tuple[int]] = None,
        max_size: typing.Optional[tuple[int]] = None,
        padding_minimum: typing.Optional[int] = None,
        padding_percent: typing.Optional[int] = None,
    ) -> None:
        """Creates the crops for a given dataset if the correct api key is provided in the

        Args:
            dataset_id: The dataset id
            subset_id: The subset id
            box_type: The box type to create crops for (QM or REFERENCE), default: QM
            aspect_ratio: The aspect ratio of the crops
            max_size: The max size of the crops
            padding_minimum: The minimum padding to add to the crops
            padding_percent: The padding (in percent) to add to the crops

        Raises:
            APIException: If the request fails.
        """
        return self._request(
            "PUT",
            f"/datasets/{dataset_id}/crops",
            params={"subset_id": subset_id},
            json=self._pack(locals(), ignore=["dataset_id", "subset_id"]),
            success_response_item_model=None,
        )
