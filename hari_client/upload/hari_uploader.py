import uuid

import pydantic
import tqdm

from hari_client import HARIClient
from hari_client import models
from hari_client.utils import logger

log = logger.setup_logger(__name__)


class HARIMediaObject(models.MediaObjectCreate):
    # overwrites the media_id field to not be required,
    # because it has to be set after the media has been uploaded
    media_id: str = ""

    def get_back_reference(self) -> str:
        """
        Returns a back reference id with which you can clearly identify this media object after it has been uploaded to HARI.

        Returns:
            str: The back reference id

        Raises:
            HARIMediaObjectMissingBackReferenceError: If the HARIMediaObject doesn't have a back_reference
        """
        if self.back_reference == "" or self.back_reference is None:
            raise HARIMediaObjectMissingBackReferenceError(self)
        return self.back_reference


class HARIMedia(models.MediaCreate):
    # media_objects is not part of the hari api, but is used to store the reference to the media_objects
    media_objects: list[HARIMediaObject] = pydantic.Field(default=[], exclude=True)

    def add_media_object(self, media_object: HARIMediaObject) -> None:
        self.media_objects.append(media_object)

    def get_back_reference(self) -> str:
        """
        Returns a back reference id with which you can clearly identify this media after it has been uploaded to HARI.

        Returns:
            str: The back reference id

        Raises:
            HARIMediaMissingBackReferenceError: If the MediaCreate object doesn't have a back_reference
        """
        if self.back_reference == "" or self.back_reference is None:
            raise HARIMediaMissingBackReferenceError(self)
        return self.back_reference


class DuplicateHARIMediaBackReferenceError(Exception):
    def __init__(self, back_reference: str):
        super().__init__(f"Duplicate media back_reference found: {back_reference=}")


class DuplicateHARIMediaObjectBackReferenceError(Exception):
    def __init__(self, back_reference: str):
        super().__init__(
            f"Duplicate media object back_reference found: {back_reference=}"
        )


class HARIMediaMissingBackReferenceError(Exception):
    def __init__(self, media: HARIMedia):
        super().__init__(f"HARIMedia object doesn't have a back_reference: {media=}")


class HARIMediaObjectMissingBackReferenceError(Exception):
    def __init__(self, media_object: HARIMediaObject):
        super().__init__(
            f"HARIMediaObject doesn't have a back_reference: {media_object=}"
        )


class HARIUploadResults(pydantic.BaseModel):
    medias: models.BulkResponse
    media_objects: models.BulkResponse


class HARIUploader:
    def __init__(self, client: HARIClient, dataset_id: uuid.UUID) -> None:
        self.client = client
        self.dataset_id: uuid.UUID = dataset_id
        # key: HARIMedia.back_reference
        self._medias: dict[str, HARIMedia] = {}
        self._media_object_back_references: set[str] = set()

    def add_media(self, hari_media: HARIMedia) -> None:
        """
        Add a HARIMedia object to the uploader. Only use this method to add medias to the uploader.
        The back_reference is used as a unique identifier.
        Also verifies that the media object back_references are unique across all media objects
        known to the uploader.

        Args:
            hari_media (HARIMedia): A HARIMedia object

        Raises:
            DuplicateHARIMediaBackReferenceError: If the provided media back_reference is already known to the uploader
            DuplicateHARIMediaObjectBackReferenceError: If a provided media object back_reference is already known to the uploader
        """
        back_reference = hari_media.get_back_reference()
        if back_reference in self._medias:
            raise DuplicateHARIMediaBackReferenceError(back_reference=back_reference)
        self._medias[back_reference] = hari_media

        for media_object in hari_media.media_objects:
            if media_object.back_reference in self._media_object_back_references:
                raise DuplicateHARIMediaObjectBackReferenceError(
                    back_reference=media_object.back_reference
                )
            self._media_object_back_references.add(media_object.back_reference)

    def upload(
        self,
    ) -> HARIUploadResults | None:
        """
        Upload all Media and their MediaObjects to HARI.

        Returns:
            HARIUploadResults | None: All bulk upload summaries for the
            medias (first element) and media objects (second element), or None if nothing was uploaded
        """

        if len(self._medias) == 0:
            log.info(
                "No medias to upload. Add them with HARIUploader::add_media() first before calling HARIUploader::upload()."
            )
            return None

        # upload batches of medias
        log.info(f"Starting upload of {len(self._medias)} medias to HARI.")
        media_upload_responses: list[models.BulkResponse] = []
        media_object_upload_responses: list[models.BulkResponse] = []
        medias_list = list(self._medias.values())
        progressbar = tqdm.tqdm(desc="HARI Media Upload", total=len(self._medias))

        for idx in range(0, len(medias_list), HARIClient.BULK_UPLOAD_LIMIT):
            medias_to_upload = medias_list[idx : idx + HARIClient.BULK_UPLOAD_LIMIT]
            media_response, media_object_responses = self._upload_media_batch(
                medias_to_upload=medias_to_upload
            )
            progressbar.update(len(medias_to_upload))
            media_upload_responses.append(media_response)
            media_object_upload_responses.extend(media_object_responses)

        progressbar.close()

        return HARIUploadResults(
            medias=_merge_bulk_responses(*media_upload_responses),
            media_objects=_merge_bulk_responses(*media_object_upload_responses),
        )

    def _upload_media_batch(
        self, medias_to_upload: list[HARIMedia]
    ) -> tuple[models.BulkResponse, list[models.BulkResponse]]:
        # upload media batch
        media_upload_response = self.client.create_medias(
            dataset_id=str(self.dataset_id), medias=medias_to_upload
        )
        self._update_hari_media_object_media_ids(
            media_upload_bulk_response=media_upload_response
        )

        # upload batches of media_objects
        all_media_objects: list[HARIMediaObject] = []
        media_object_upload_responses: list[models.BulkResponse] = []
        for media in medias_to_upload:
            all_media_objects.extend(media.media_objects)

        for idx in range(0, len(all_media_objects), HARIClient.BULK_UPLOAD_LIMIT):
            media_objects_to_upload = all_media_objects[
                idx : idx + HARIClient.BULK_UPLOAD_LIMIT
            ]
            response = self._upload_media_object_batch(
                media_objects_to_upload=media_objects_to_upload
            )
            media_object_upload_responses.append(response)

        return media_upload_response, media_object_upload_responses

    def _upload_media_object_batch(
        self, media_objects_to_upload: list[HARIMediaObject]
    ) -> models.BulkResponse:
        response = self.client.create_media_objects(
            dataset_id=str(self.dataset_id), media_objects=media_objects_to_upload
        )
        return response

    def _update_hari_media_object_media_ids(
        self, media_upload_bulk_response: models.BulkResponse
    ) -> None:
        for item_response in media_upload_bulk_response.results:
            # from the endpoints we used, we know that the item_response is a models.AnnotatableCreateResponse,
            # which contains a back_reference
            media = self._medias[item_response.back_reference]
            for media_object in media.media_objects:
                media_object.media_id = item_response.item_id


def _merge_bulk_responses(*args: models.BulkResponse) -> models.BulkResponse:
    """
    Merges multiple BulkResponse objects into a new one.
    If only one BulkResponse object is provided, it will be returned as is.

    Args:
        *args (models.BulkResponse): Multiple BulkResponse objects

    Returns:
        models.BulkResponse: The merged BulkResponse object
    """
    if len(args) == 1:
        return args[0]

    final_response = models.BulkResponse()

    statuses = set()

    for response in args:
        # merge results
        final_response.results.extend(response.results)

        # merge summaries
        final_response.summary.total += response.summary.total
        final_response.summary.successful += response.summary.successful
        final_response.summary.failed += response.summary.failed

        statuses.add(response.status)

    if len(statuses) == 1:
        # if all statuses are the same, use that status
        final_response.status = statuses.pop()
    elif models.BulkOperationStatusEnum.SUCCESS in statuses:
        # if success appears at least once, it's a partial_success
        final_response.status = models.BulkOperationStatusEnum.PARTIAL_SUCCESS
    else:
        # any other case should be considered a failure
        final_response.status = models.BulkOperationStatusEnum.FAILURE

    return final_response
