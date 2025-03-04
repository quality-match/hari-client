import copy
import uuid

import tqdm

from hari_client import HARIClient
from hari_client import HARIUploaderConfig
from hari_client import models
from hari_client import validation
from hari_client.client.client import _parse_response_model
from hari_client.client.errors import APIError
from hari_client.upload.hari_uploader import _merge_bulk_responses
from hari_client.upload.hari_uploader import HARIAttribute
from hari_client.upload.hari_uploader import HARIMedia
from hari_client.upload.hari_uploader import HARIMediaObject
from hari_client.upload.hari_uploader import (
    HARIMediaObjectUnknownObjectCategorySubsetNameError,
)
from hari_client.upload.hari_uploader import HARIMediaObjectUploadError
from hari_client.upload.hari_uploader import HARIMediaUploadError
from hari_client.upload.hari_uploader import HARIUniqueAttributesLimitExceeded
from hari_client.upload.hari_uploader import HARIUploadResults
from hari_client.utils import logger

log = logger.setup_logger(__name__)

# the maximum attributes number for the whole dataset/upload
MAX_ATTR_COUNT = 1000


class HARIUploader:
    def __init__(
        self,
        client: HARIClient,
        dataset_id: uuid.UUID,
        object_categories: set[str] | None = None,
        check_duplicate_medias=True,
        check_duplicate_media_objects=True,
    ) -> None:
        """Initializes the HARIUploader.

        Args:
            client: A HARIClient object.
            dataset_id: ID of the dataset to upload to.
            object_categories: A set of object categories present in the media_objects.
                If media_objects have an object_category_subset_name assigned, it has to be from this set.
                HARIUploader will create a HARI subset for each object_category and add the corresponding medias and media_objects to it.
            check_duplicate_media_objects: Defines if backreferences are used to check before upload if media objects exists.
             It is recommended to use this check but for large datasets it might be inefficient if this is handled before the upload.
             check_duplicate_medias: Defines if backreferences are used to check before upload if media exists.
             It is recommended to use this check but for large datasets it might be inefficient if this is handled before the upload.
        """
        self.client: HARIClient = client
        self.dataset_id: uuid.UUID = dataset_id
        self.object_categories = object_categories or set()
        self._config: HARIUploaderConfig = self.client.config.hari_uploader
        self._medias: list[HARIMedia] = []
        self._media_back_references: set[str] = set()
        self._media_object_back_references: set[str] = set()
        # TODO: this should be a dict[str, uuid.UUID] as soon as the api models are updated
        self._object_category_subsets: dict[str, str] = {}
        self._unique_attribute_ids: set[str] = set()
        self.check_duplicate_medias = check_duplicate_medias
        self.check_duplicate_media_objects = check_duplicate_media_objects

    def add_media(self, *args: HARIMedia) -> None:
        """
        Add one or more HARIMedia objects to the uploader. Only use this method to add
        medias to the uploader.

        Args:
            *args: Multiple HARIMedia objects

        Raises:
            HARIMediaUploadError: If an unrecoverable problem with the media upload
                was detected
        """

        self._medias.extend(args)

    def _add_object_category_subset(self, object_category: str, subset_id: str) -> None:
        """
        Store the subset ID for the specified object category in an internal dictionary.

        Args:
            object_category: The name or label of the object category.
            subset_id: The subset identifier corresponding to this object category.
        """
        self._object_category_subsets[object_category] = subset_id

    def _create_object_category_subsets(self, object_categories: list[str]) -> None:
        """
        Create and register new object_category subsets on the server for any categories
        that do not yet exist.

        Args:
            object_categories: The list of object categories that need subsets.
        """
        log.info(f"Creating {len(object_categories)} object_category subsets.")
        # create only the object_category subsets that don't exist on the server, yet
        newly_created_object_category_subsets = {}
        # sort object_categories to ensure consistent subset creation order
        for object_category in sorted(object_categories):
            subset_id = self.client.create_empty_subset(
                dataset_id=self.dataset_id,
                subset_type=models.SubsetType.MEDIA_OBJECT,
                subset_name=object_category,
                object_category=True,
            )
            self._add_object_category_subset(object_category, subset_id)
            newly_created_object_category_subsets[object_category] = subset_id
        log.info(
            f"Successfully created object_category subsets: {newly_created_object_category_subsets=}"
        )

    def _get_and_validate_media_objects_object_category_subset_names(
        self,
    ) -> tuple[set[str], list[HARIMediaObjectUnknownObjectCategorySubsetNameError]]:
        """Retrieves and validates the consistency of the object_category_subset_names that were assigned to media_objects.
        To be consistent, all media_object.object_category_subset_name values must be available in the set of object_categories specified in the HARIUploader constructor.
        A media_object isn't required to be assigned an object_category_subset_name, though.

        Returns:
            tuple[set[str], list[HARIMediaObjectUnknownObjectCategorySubsetError]]: The first return value is the set of found object_category_subset_names,
                the second return value is the list of errors that were found during the validation.
        """
        errors = []
        found_object_category_subset_names = set()
        for media in self._medias:
            for media_object in media.media_objects:
                # was the media_object assigned an object_category_subset_name?
                if media_object.object_category_subset_name:
                    # was the object_category_subset_name specified in the HARIUploader constructor?
                    found_object_category_subset_names.add(
                        media_object.object_category_subset_name
                    )
                    if (
                        media_object.object_category_subset_name
                        not in self.object_categories
                    ):
                        errors.append(
                            HARIMediaObjectUnknownObjectCategorySubsetNameError(
                                f"A subset for the specified object_category_subset_name ({media_object.object_category_subset_name}) wasn't specified."
                                f"Only the object_categories that were specified in the HARIUploader constructor are allowed: {self.object_categories}"
                                f"media_object: {media_object}"
                            )
                        )
        return found_object_category_subset_names, errors

    def _assign_object_category_subsets(self) -> None:
        """Asssigns object_category_subsets to media_objects and media based on media_object.object_category_subset_name"""
        if len(self._object_category_subsets) > 0:
            for media in self._medias:
                for media_object in media.media_objects:
                    # was the media_object assigned an object_category_subset_name?
                    if media_object.object_category_subset_name:
                        object_category_subset_id_str = (
                            self._object_category_subsets.get(
                                media_object.object_category_subset_name
                            )
                        )
                        media_object.object_category = uuid.UUID(
                            object_category_subset_id_str
                        )
                        # does a subset_id exist for the media_object's object_category_subset_name?
                        if media_object.object_category is None:
                            raise HARIMediaObjectUnknownObjectCategorySubsetNameError(
                                f"A subset for the specified object_category_subset_name ({media_object.object_category_subset_name}) wasn't created."
                                f"Only the object_categories that were specified in the HARIUploader constructor are allowed: {self.object_categories}"
                                f"media_object: {media_object}"
                            )
                        # also add the object_category subset_id to the overall list of subset_ids
                        if media_object.subset_ids:
                            media_object.subset_ids.append(
                                object_category_subset_id_str
                            )
                        else:
                            media_object.subset_ids = [object_category_subset_id_str]
                        # also add the object_category subset_id to the overall list of subset_ids for the media
                        if media.subset_ids:
                            media.subset_ids.append(object_category_subset_id_str)
                        else:
                            media.subset_ids = [object_category_subset_id_str]
                        # avoid duplicates in the subset_ids list
                        media.subset_ids = list(set(media.subset_ids))

    def get_existing_object_category_subsets(self) -> list[models.DatasetResponse]:
        """
        Fetch existing object_category subsets for the current dataset.

        Returns:
            A list of DatasetResponse objects representing subsets that have
            object_category set to True.
        """
        # fetch existing object_category subsets
        subsets = self.client.get_subsets_for_dataset(dataset_id=self.dataset_id)
        # filter out subsets that are object_category subsets
        object_category_subsets = [
            subset for subset in subsets if subset.object_category is True
        ]
        log.info(f"All existing object_category subsets: {object_category_subsets=}")
        return object_category_subsets

    def _handle_object_categories(self) -> None:
        """
        Validates consistency of object_categories across media objects,
        gets all existing object_category subsets from the server,
        then creates missing object_category subsets.
        """
        # set up object category subsets
        log.info(f"Initializing object_category subsets.")
        (
            media_object_category_subset_names,
            media_object_object_category_subset_name_errors,
        ) = self._get_and_validate_media_objects_object_category_subset_names()
        if media_object_object_category_subset_name_errors:
            log.error(
                f"Found {len(media_object_object_category_subset_name_errors)} errors with object_category_subset_name consistency."
            )
            raise ExceptionGroup(
                f"Found {len(media_object_object_category_subset_name_errors)} errors with object_category_subset_name consistency.",
                media_object_object_category_subset_name_errors,
            )

        backend_object_category_subsets = self.get_existing_object_category_subsets()
        # add already existing subsets to the object_category_subsets dict
        for obj_category_subset in backend_object_category_subsets:
            self._add_object_category_subset(
                obj_category_subset.name, str(obj_category_subset.id)
            )

        # check whether all required object_category subsets already exist
        object_categories_without_existing_subsets = [
            subset_name
            for subset_name in media_object_category_subset_names
            if subset_name
            not in [
                obj_cat_subset.name
                for obj_cat_subset in backend_object_category_subsets
            ]
        ]

        self._create_object_category_subsets(object_categories_without_existing_subsets)
        log.info(
            f"All object category subsets of this dataset: {self._object_category_subsets=}"
        )
        self._assign_object_category_subsets()

    def validate_all_attributes(self) -> list[HARIAttribute]:
        """
        Validate all attributes for both media and media objects, ensuring they meet the
        dataset's requirements and do not exceed the allowed unique attribute limit.

        Returns:
            A list of all validated attributes from the media and media objects.

        Raises:
            HARIUniqueAttributesLimitExceeded: If the number of unique attribute ids exceeds
            the limit of MAX_ATTR_COUNT per dataset.
        """

        # Get existing attributes
        existing_attr_metadata = self.client.get_attribute_metadata(
            dataset_id=self.dataset_id
        )
        attribute_name_to_ids: dict[str, str | uuid.UUID] = {
            attr.name: attr.id for attr in existing_attr_metadata
        }

        all_attributes = []
        for media in self._medias:
            all_attributes.extend(media.attributes)

            # set annotatable type
            for attr in media.attributes:
                # check that all attribute ids are correctly set or create new ones
                if attr.name not in attribute_name_to_ids:
                    attribute_name_to_ids[attr.name] = uuid.uuid4()
                attr.id = attribute_name_to_ids[attr.name]

                # annotatable_type is optional for a HARIAttribute, but can already be set here
                attr.annotatable_type = models.DataBaseObjectType.MEDIA

            for media_object in media.media_objects:
                all_attributes.extend(media_object.attributes)

                # set annotatable type
                for attr in media_object.attributes:
                    # check that all attribute ids are correctly set or create new ones
                    if attr.name not in attribute_name_to_ids:
                        attribute_name_to_ids[attr.name] = uuid.uuid4()
                    attr.id = attribute_name_to_ids[attr.name]

                    # annotatable_type is optional for a HARIAttribute, but can already be set here
                    attr.annotatable_type = models.DataBaseObjectType.MEDIAOBJECT

        # Raises an error if any requirements for attribute consistency aren't met.
        validation.validate_attributes(all_attributes)

        if len(attribute_name_to_ids) > MAX_ATTR_COUNT:
            raise HARIUniqueAttributesLimitExceeded(
                new_attributes_number=len(attribute_name_to_ids)
                - len(existing_attr_metadata),
                existing_attributes_number=len(existing_attr_metadata),
                intended_attributes_number=len(attribute_name_to_ids),
            )

        return all_attributes

    def validate_all_media_and_media_objects(self) -> list[HARIMediaObject]:
        """
        Validate media and media object back_references for duplicates, collect all
        media objects into a single list, and log warnings for any repeated references.

        Returns:
            A list containing all media objects across the loaded medias.
        """
        all_media_objects = []
        for media in self._medias:
            # check and remember media back_references
            if media.back_reference in self._media_back_references:
                log.warning(
                    f"Found duplicate media back_reference: {media.back_reference}. If "
                    f"you want to be able to match HARI objects 1:1 to your own, "
                    f"consider using unique back_references."
                )
            else:
                self._media_back_references.add(media.back_reference)

            # check and remember media object back_references
            for media_object in media.media_objects:
                if media_object.back_reference in self._media_object_back_references:
                    log.warning(
                        f"Found duplicate media_object back_reference: "
                        f"{media.back_reference}. If you want to be able to match HARI "
                        f"objects 1:1 to your own, consider using unique "
                        f"back_references."
                    )
                else:
                    self._media_object_back_references.add(media_object.back_reference)

                all_media_objects.append(media_object)

        return all_media_objects

    def check_duplicates_medias(self, medias: list[HARIMedia]) -> None:
        """
        Check if any medias about to be uploaded already exist on the server by comparing
        back_references.

        Args:
            medias: The list of medias intended for upload.
        """
        uploaded_medias = self.client.get_medias(
            self.dataset_id
        )  # TODO paging and faster query, might be needed for larger datasets

        self._check_duplicates_media_media_objects(medias, uploaded_medias)

    def check_duplicates_media_objects(
        self, media_objects: list[HARIMediaObject]
    ) -> None:
        """
        Check if any media objects about to be uploaded already exist on the server by comparing
        back_references.

        Args:
            media_objects: The list of media objects intended for upload.
        """
        uploaded_mos = self.client.get_media_objects(
            self.dataset_id
        )  # TODO paging and faster query, might be needed for larger datasets

        self._check_duplicates_media_media_objects(media_objects, uploaded_mos)

    def _check_duplicates_media_media_objects(
        self,
        objectsToUpload: list[HARIMediaObject] | list[HARIMedia],
        objectsUploaded: list[HARIMediaObject] | list[HARIMedia],
    ) -> None:
        """
        Mark items in objectsToUpload as already uploaded if their back_references appear
        among the objectsUploaded. Prints warnings if multiple references are found.

        Args:
            objectsToUpload: The list of media or media objects to be uploaded.
            objectsUploaded: The media or media objects already in the dataset.
        """
        # build look up table for back references
        # add warning if multiple of the same backreference are given, value will be overwritten
        uploaded_back_references = {}
        for m in objectsUploaded:
            if m.back_reference in uploaded_back_references:
                log.warning(
                    f"Multiple of the same backreference '{m.back_reference}' encountered; "
                    f"overwriting previous value."
                )
            uploaded_back_references[m.back_reference] = m.id

        for m in objectsToUpload:
            # ensure uploaded marked are always having an id
            m.uploaded = m.back_reference in uploaded_back_references
            m.id = uploaded_back_references.get(m.back_reference, None)

    def upload(
        self,
    ) -> HARIUploadResults | None:
        """
        Uploads all HARIMedia items along with their media objects and attributes to the HARI backend.

        This method:
          1. Validates media, media_objects and attributes to be consistent and do not include duplicates.
          2. Recommended, but optionally query the server for media and media_objects to mark already uploaded items to prevent reuploading.
          3. Ensure all object categories are either reused or created based on the value when creating the hari_uploader instance.
          4. Batches the actual uploading of medias, media objects, and attributes. The items are uploaded as media batches, if medias are uploaded, the corresponding media objects and attributes for this media batch are uploaded.

        Returns:
          A summary of the upload results, containing details of successes and failures for
          medias, media objects, and attributes. Returns None if no HARIMedia items are queued
          for upload.

        Raises:
          HARIUniqueAttributesLimitExceeded: If the total number of unique attributes in the
          dataset would exceed the configured limit (MAX_ATTR_COUNT).
        """

        if len(self._medias) == 0:
            log.info(
                "No medias to upload. Add them with HARIUploader::add_media() first "
                "before calling HARIUploader::upload()."
            )
            return None

        # validate intended upload, this only checks for incosistency which can be checked locally
        validated_media_objects = self.validate_all_media_and_media_objects()
        validated_attributes = self.validate_all_attributes()

        # validate that the intended uploads do not already exists on the server
        # for attributes the check is automatically done via the server during upload

        # check upload status of medias
        if self.check_duplicate_medias:
            self.check_duplicates_medias(self._medias)

        # check upload status of media objects
        if self.check_duplicate_media_objects:
            self.check_duplicates_media_objects(validated_media_objects)

        # make sure all needed object categories exists otherwise create them
        self._handle_object_categories()

        # upload batches of medias
        log.info(
            f"Starting upload of {len(self._medias)} medias with "
            f"{len(validated_media_objects)} media_objects and {len(validated_attributes)} "
            f"attributes to HARI. "
            f"Only not already uploaded values will be uploaded."
        )
        self._media_upload_progress = tqdm.tqdm(
            desc="Media Upload", total=len(self._medias)
        )
        self._media_object_upload_progress = tqdm.tqdm(
            desc="Media Object Upload", total=len(validated_media_objects)
        )
        self._attribute_upload_progress = tqdm.tqdm(
            desc="Attribute Upload", total=len(validated_attributes)
        )

        media_upload_responses: list[models.BulkResponse] = []
        media_object_upload_responses: list[models.BulkResponse] = []
        attribute_upload_responses: list[models.BulkResponse] = []

        for idx in range(0, len(self._medias), self._config.media_upload_batch_size):
            medias_to_upload = self._medias[
                idx : idx + self._config.media_upload_batch_size
            ]
            (
                media_response,
                media_object_responses,
                attribute_responses,
            ) = self._upload_media_batch(medias_to_upload=medias_to_upload)
            media_upload_responses.append(media_response)
            media_object_upload_responses.extend(media_object_responses)
            attribute_upload_responses.extend(attribute_responses)

        self._media_upload_progress.close()
        self._media_object_upload_progress.close()
        self._attribute_upload_progress.close()

        return HARIUploadResults(
            medias=_merge_bulk_responses(*media_upload_responses),
            media_objects=_merge_bulk_responses(*media_object_upload_responses),
            attributes=_merge_bulk_responses(*attribute_upload_responses),
        )

    def _upload_media_batch(
        self, medias_to_upload: list[HARIMedia]
    ) -> tuple[
        models.BulkResponse, list[models.BulkResponse], list[models.BulkResponse]
    ]:
        """
        Upload a batch of medias, then update their IDs so that subsequent media object
        and attribute uploads can correctly reference them.
        Subsequently, calls the upload associated media objects and attributes via `_upload_attributes_in_batches` and `_upload_media_objects_in_batches`.

        Args:
            medias_to_upload: A subset of HARIMedia to upload.

        Returns:
            A tuple containing:
            1. The bulk response for medias.
            2. A list of bulk responses for media objects.
            3. A list of bulk responses for attributes.
        """
        for media in medias_to_upload:
            self._set_bulk_operation_annotatable_id(item=media)

        # ensure only non-uploaded medias are actually uploaded
        medias_need_upload = [media for media in medias_to_upload if not media.uploaded]

        # upload media batch
        media_upload_response = self.client.create_medias(
            dataset_id=self.dataset_id, medias=medias_need_upload
        )
        self._media_upload_progress.update(len(medias_to_upload))

        # need to add filter out ones as manual responses
        medias_skipped = [media for media in medias_to_upload if media.uploaded]
        media_upload_response.summary.failed += len(medias_skipped)
        media_upload_response.summary.total += len(medias_skipped)
        media_upload_response.results.extend(
            [
                # TODO we add here manually error messages for skipped entries
                # Motivation for attributes we also show these errors
                # We realigned and the default behavior should that they are successful, this is also true for attributes
                models.AnnotatableCreateResponse(
                    bulk_operation_annotatable_id=media.bulk_operation_annotatable_id,
                    status=models.ResponseStatesEnum.CONFLICT,
                    item_id=media.id,
                    errors=[
                        f"Skipped the upload of media {media.id} "
                        f"since media with back reference {media.back_reference} already exists."
                    ],
                )
                for media in medias_skipped
            ]
        )

        # TODO: what if upload failures occur in the media upload above? -> Just restart should be robust enough
        # Enable checking for errors and abort here
        self._update_hari_media_object_media_ids(
            medias_to_upload=medias_to_upload,
            media_upload_bulk_response=media_upload_response,
        )
        self._update_hari_attribute_media_ids(
            medias_to_upload=medias_to_upload,
            media_upload_bulk_response=media_upload_response,
        )

        # upload media_objects of this batch of media in batches
        all_media_objects: list[HARIMediaObject] = []
        all_attributes: list[HARIAttribute] = []
        for media in medias_to_upload:
            all_media_objects.extend(media.media_objects)
            all_attributes.extend(media.attributes)

        media_object_upload_responses = self._upload_media_objects_in_batches(
            all_media_objects
        )
        for media_object in all_media_objects:
            all_attributes.extend(media_object.attributes)

        # upload attributes of this batch of media in batches
        attributes_upload_responses = self._upload_attributes_in_batches(all_attributes)

        return (
            media_upload_response,
            media_object_upload_responses,
            attributes_upload_responses,
        )

    def _upload_attributes_in_batches(
        self, attributes: list[HARIAttribute]
    ) -> list[models.BulkResponse]:
        """
        Upload attributes in configured batch sizes, aggregating bulk responses.

        Args:
            attributes: The attribute objects to be uploaded.

        Returns:
            A list of BulkResponse objects, one for each batch of attributes uploaded.
        """
        attributes_upload_responses: list[models.BulkResponse] = []
        for idx in range(0, len(attributes), self._config.attribute_upload_batch_size):
            attributes_to_upload = attributes[
                idx : idx + self._config.attribute_upload_batch_size
            ]
            response = self._upload_attribute_batch(
                attributes_to_upload=attributes_to_upload
            )
            attributes_upload_responses.append(response)
            self._attribute_upload_progress.update(len(attributes_to_upload))
        return attributes_upload_responses

    def _upload_media_objects_in_batches(
        self, media_objects: list[HARIMediaObject]
    ) -> list[models.BulkResponse]:
        """
        Upload media objects in configured batch sizes, aggregating bulk responses.

        Args:
            media_objects: The media objects to be uploaded.

        Returns:
            A list of BulkResponse objects, one for each batch of media objects uploaded.
        """
        media_object_upload_responses: list[models.BulkResponse] = []
        for idx in range(
            0, len(media_objects), self._config.media_object_upload_batch_size
        ):
            media_objects_to_upload = media_objects[
                idx : idx + self._config.media_object_upload_batch_size
            ]
            response = self._upload_media_object_batch(
                media_objects_to_upload=media_objects_to_upload
            )
            media_object_upload_responses.append(response)
            self._media_object_upload_progress.update(len(media_objects_to_upload))
        return media_object_upload_responses

    def _upload_attribute_batch(
        self, attributes_to_upload: list[HARIAttribute]
    ) -> models.BulkResponse:
        """
        Upload a batch of attributes, returning the bulk response from the server.
        If a conflict or other API error occurs, it attempts to parse the response into
        a BulkResponse object to provide detailed feedback.

        Args:
            attributes_to_upload: A batch of attributes to be uploaded.

        Returns:
            The BulkResponse result of uploading these attributes.
        """
        try:
            response = self.client.create_attributes(
                dataset_id=self.dataset_id, attributes=attributes_to_upload
            )
        except APIError as e:
            # TODO try to parse as Bulk response, might only be a conflict
            # Motivation for attributes we also show these errors
            # We realigned and the default behavior should that they are successful, this is also true for attributes
            #
            response = _parse_response_model(
                response_data=e.message, response_model=models.BulkResponse
            )
        return response

    def _upload_media_object_batch(
        self, media_objects_to_upload: list[HARIMediaObject]
    ) -> models.BulkResponse:
        """
        Upload a batch of media objects, then update relevant IDs so attributes can reference them.

        Args:
            media_objects_to_upload: A batch of media objects to be uploaded.

        Returns:
            The BulkResponse result of uploading these media objects.
        """
        for media_object in media_objects_to_upload:
            self._set_bulk_operation_annotatable_id(item=media_object)

        # filter out already marked as uploaded
        media_objects_need_upload = [
            mo for mo in media_objects_to_upload if not mo.uploaded
        ]

        response = self.client.create_media_objects(
            dataset_id=self.dataset_id, media_objects=media_objects_need_upload
        )

        # need to add filter out ones as manual responses
        media_objects_skipped = [mo for mo in media_objects_to_upload if mo.uploaded]
        response.summary.failed += len(media_objects_skipped)
        response.summary.total += len(media_objects_skipped)

        # TODO we add here manually error messages for skipped entries
        # Motivation for attributes we also show these errors
        # We realigned and the default behavior should that they are successful, this is also true for attributes
        response.results.extend(
            [
                models.AnnotatableCreateResponse(
                    bulk_operation_annotatable_id=mo.bulk_operation_annotatable_id,
                    status=models.ResponseStatesEnum.CONFLICT,
                    item_id=mo.id,
                    errors=[
                        f"Skipped the upload of media object {mo.id} "
                        f"since object with back reference {mo.back_reference} already exists."
                    ],
                )
                for mo in media_objects_skipped
            ]
        )

        self._update_hari_attribute_media_object_ids(
            media_objects_to_upload=media_objects_to_upload,
            media_object_upload_bulk_response=response,
        )
        return response

    def _update_hari_media_object_media_ids(
        self,
        medias_to_upload: list[HARIMedia],
        media_upload_bulk_response: models.BulkResponse,
    ) -> None:
        """
        Update the media_id field for each media object's references using the server-generated
        IDs from the media upload response.

        Args:
            medias_to_upload: The batch of HARIMedia that was just uploaded (or skipped).
            media_upload_bulk_response: The server response for the batch upload of medias.
        """
        for media in medias_to_upload:
            if len(media.media_objects) == 0:
                continue
            # from the endpoints we used, we know that the results items are of type
            # models.AnnotatableCreateResponse, which contains
            # the bulk_operation_annotatable_id.
            filtered_upload_response = list(
                filter(
                    lambda x: x.bulk_operation_annotatable_id
                    == media.bulk_operation_annotatable_id,
                    media_upload_bulk_response.results,
                )
            )
            if len(filtered_upload_response) == 0:
                raise HARIMediaUploadError(
                    f"Media upload response doesn't match expectation. Couldn't find "
                    f"{media.bulk_operation_annotatable_id=} in the upload response."
                )
            elif (len(filtered_upload_response)) > 1:
                raise HARIMediaUploadError(
                    f"Media upload response contains multiple items for "
                    f"{media.bulk_operation_annotatable_id=}."
                )
            media_upload_response: models.AnnotatableCreateResponse = (
                filtered_upload_response[0]
            )

            media_id = media_upload_response.item_id

            for i, media_object in enumerate(media.media_objects):
                # Create a copy of the media object to avoid changing shared attributes
                media.media_objects[i] = copy.deepcopy(media_object)
                media.media_objects[i].media_id = media_id

    def _update_hari_attribute_media_object_ids(
        self,
        media_objects_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_object_upload_bulk_response: models.BulkResponse,
    ) -> None:
        """
        Update the annotatable_id field for attributes belonging to media objects, using
        the IDs from the server's media object upload response.

        Args:
            media_objects_to_upload: The batch of HARIMediaObjects that was just uploaded (or skipped).
            media_object_upload_bulk_response: The server response for uploading these media objects.
        """
        for media_object in media_objects_to_upload:
            if len(media_object.attributes) == 0:
                continue
            # from the endpoints we used, we know that the results items are of type
            # models.AnnotatableCreateResponse, which contains
            # the bulk_operation_annotatable_id.
            filtered_upload_response = list(
                filter(
                    lambda x: x.bulk_operation_annotatable_id
                    == media_object.bulk_operation_annotatable_id,
                    media_object_upload_bulk_response.results,
                )
            )
            if len(filtered_upload_response) == 0:
                raise HARIMediaObjectUploadError(
                    f"MediaObject upload response doesn't match expectation. Couldn't find "
                    f"{media_object.bulk_operation_annotatable_id=} in the upload response."
                )
            elif (len(filtered_upload_response)) > 1:
                raise HARIMediaObjectUploadError(
                    f"MediaObject upload response contains multiple items for "
                    f"{media_object.bulk_operation_annotatable_id=}."
                )
            media_object_upload_response: models.AnnotatableCreateResponse = (
                filtered_upload_response[0]
            )
            media_object_id = media_object_upload_response.item_id

            for i, attribute in enumerate(media_object.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media_object.attributes[i] = copy.deepcopy(attribute)
                media_object.attributes[i].annotatable_id = media_object_id
                media_object.attributes[
                    i
                ].annotatable_type = models.DataBaseObjectType.MEDIAOBJECT

    def _update_hari_attribute_media_ids(
        self,
        medias_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_upload_bulk_response: models.BulkResponse,
    ) -> None:
        """
        Update the annotatable_id field for attributes belonging to media, using
        the IDs from the server's media upload response.

        Args:
            medias_to_upload: The batch of HARIMedia that was just uploaded (or skipped).
            media_upload_bulk_response: The server response for uploading these medias.
        """
        for media in medias_to_upload:
            if len(media.attributes) == 0:
                continue
            # from the endpoints we used, we know that the results items are of type
            # models.AnnotatableCreateResponse, which contains
            # the bulk_operation_annotatable_id.
            filtered_upload_response = list(
                filter(
                    lambda x: x.bulk_operation_annotatable_id
                    == media.bulk_operation_annotatable_id,
                    media_upload_bulk_response.results,
                )
            )

            if len(filtered_upload_response) == 0:
                raise HARIMediaUploadError(
                    f"Media upload response doesn't match expectation. Couldn't find "
                    f"{media.bulk_operation_annotatable_id=} in the upload response."
                )
            elif (len(filtered_upload_response)) > 1:
                raise HARIMediaUploadError(
                    f"Media upload response contains multiple items for "
                    f"{media.bulk_operation_annotatable_id=}."
                )
            media_upload_response: models.AnnotatableCreateResponse = (
                filtered_upload_response[0]
            )
            media_id = media_upload_response.item_id

            for i, attribute in enumerate(media.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media.attributes[i] = copy.deepcopy(attribute)
                media.attributes[i].annotatable_id = media_id
                media.attributes[i].annotatable_type = models.DataBaseObjectType.MEDIA

    def _set_bulk_operation_annotatable_id(self, item: HARIMedia | HARIMediaObject):
        """
        Assign a random UUID as the bulk_operation_annotatable_id for items that do not already
        have one, enabling the server to match each upload to the correct response entry.

        Args:
            item: The HARIMedia or HARIMediaObject whose bulk_operation_annotatable_id
                  should be set if not already present.
        """
        if not item.bulk_operation_annotatable_id:
            item.bulk_operation_annotatable_id = str(uuid.uuid4())
