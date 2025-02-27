import copy
import typing
import uuid

import pydantic
import tqdm

from hari_client import HARIClient
from hari_client import HARIUploaderConfig
from hari_client import models
from hari_client import validation
from hari_client.utils import logger

log = logger.setup_logger(__name__)

# the maximum attributes number for the whole dataset/upload
MAX_ATTR_COUNT = 1000


class HARIAttribute(models.BulkAttributeCreate):
    # overwrites the annotatable_id and _type fields to not be required,
    # because it has to be set after the media has been uploaded
    annotatable_id: str = ""
    annotatable_type: str = ""


class HARIMediaObject(models.BulkMediaObjectCreate):
    # the attributes field is not part of the lower level MediaObjectCreate model of the hari
    # api, but we need it to add media_objects to a media before uploading the media.
    attributes: list[HARIAttribute] = pydantic.Field(default=[], exclude=True)
    # overwrites the media_id field to not be required,
    # because it has to be set after the media has been uploaded
    media_id: str = ""
    # overwrites the bulk_operation_annotatable_id field to not be required,
    # because it's set internally by the HARIUploader
    bulk_operation_annotatable_id: str | None = None
    # the object_category_subset_name field is not part of the lower level MediaObjectCreate model
    # of the hari api, but is needed to store which object category subset the media object should belong to.
    object_category_subset_name: str | None = pydantic.Field(default=None, exclude=True)

    # overrides the BulkMediaObjectCreate validator to not raise error if the bulk_operation_annotatable_id is not set;
    # the field is set internally by the HARIUploader
    @pydantic.model_validator(mode="before")
    @classmethod
    def check_bulk_operation_annotatable_id_omitted(
        cls, data: typing.Any
    ) -> typing.Any:
        return data

    def add_attribute(self, *args: HARIAttribute) -> None:
        for attribute in args:
            self.attributes.append(attribute)

    def set_object_category_subset_name(self, object_category_subset_name: str) -> None:
        self.object_category_subset_name = object_category_subset_name

    @pydantic.field_validator("media_id", "bulk_operation_annotatable_id")
    @classmethod
    def field_must_not_be_set(cls, v: str) -> str:
        if v:
            raise ValueError(
                "The field must not be set on object instantiation. It's used and set "
                "by HARIUploader internals."
            )
        return v

    @pydantic.field_validator("back_reference")
    @classmethod
    def empty_back_reference(cls, v: str) -> str:
        if not v:
            log.warning(
                "Detected empty back_reference in HARIMediaObject. It's encouraged "
                "that you use a back_reference so that you can match HARI objects to"
                " your own."
            )
        return v


class HARIMediaUploadError(Exception):
    pass


class HARIMediaObjectUploadError(Exception):
    pass


class HARIMediaObjectUnknownObjectCategorySubsetNameError(Exception):
    pass


class HARIMediaValidationError(Exception):
    pass


class HARIUniqueAttributesLimitExceeded(Exception):
    new_attributes_number: int
    existing_attributes_number: int
    intended_attributes_number: int

    message: str

    def __init__(
        self,
        new_attributes_number: int,
        existing_attributes_number: int,
        intended_attributes_number: int,
    ):
        self.new_attributes_number = new_attributes_number
        self.existing_attributes_number = existing_attributes_number
        self.intended_attributes_number = intended_attributes_number

        message = f"You are trying to upload too many attributes with {new_attributes_number} different ids for one dataset"

        if existing_attributes_number > 0:
            message += (
                f", and there are already {existing_attributes_number} different attribute ids uploaded. "
                f"The intended number of all attribute ids per dataset would be {intended_attributes_number},"
            )

        message += (
            f" when the limit is {MAX_ATTR_COUNT}. "
            "Please make sure to reuse attribute ids you've already generated "
            "for attributes that have the same name and annotatable type. "
            "See how attributes work in HARI here: "
            "https://docs.quality-match.com/hari_client/faq/#how-do-attributes-work-in-hari."
        )
        super().__init__(message)


class HARIMedia(models.BulkMediaCreate):
    # the media_objects and attributes fields are not part of the lower level
    # MediaCreate model of the hari api, but we need them to add media objects and
    # attributes to a media before uploading the media
    media_objects: list[HARIMediaObject] = pydantic.Field(default=[], exclude=True)
    attributes: list[HARIAttribute] = pydantic.Field(default=[], exclude=True)
    # overwrites the bulk_operation_annotatable_id field to not be required,
    # because it's set internally by the HARIUploader
    bulk_operation_annotatable_id: str | None = ""

    # overrides the BulkMediaCreate validator to not raise error if the bulk_operation_annotatable_id is not set;
    # the field is set internally by the HARIUploader
    @pydantic.model_validator(mode="before")
    @classmethod
    def check_bulk_operation_annotatable_id_omitted(
        cls, data: typing.Any
    ) -> typing.Any:
        return data

    def add_media_object(self, *args: HARIMediaObject) -> None:
        for media_object in args:
            self.media_objects.append(media_object)

    def add_attribute(self, *args: HARIAttribute) -> None:
        for attribute in args:
            self.attributes.append(attribute)

    @pydantic.field_validator("bulk_operation_annotatable_id")
    @classmethod
    def field_must_not_be_set(cls, v: str) -> str:
        if v:
            raise ValueError(
                "The field must not be set on object instantiation. It's used and set "
                "by HARIUploader internals."
            )
        return v

    @pydantic.field_validator("back_reference")
    @classmethod
    def empty_back_reference(cls, v: str) -> str:
        if not v:
            log.warning(
                "Detected empty back_reference in HARIMedia. It's encouraged that you "
                "use a back_reference so that you can match HARI objects to your own."
            )
        return v


class HARIUploadResults(pydantic.BaseModel):
    medias: models.BulkResponse
    media_objects: models.BulkResponse
    attributes: models.BulkResponse


class HARIUploader:
    def __init__(
        self,
        client: HARIClient,
        dataset_id: uuid.UUID,
        object_categories: set[str] | None = None,
    ) -> None:
        """Initializes the HARIUploader.

        Args:
            client: A HARIClient object.
            dataset_id: ID of the dataset to upload to.
            object_categories: A set of object categories present in the media_objects.
                If media_objects have an object_category_subset_name assigned, it has to be from this set.
                HARIUploader will create a HARI subset for each object_category and add the corresponding medias and media_objects to it.
        """
        self.client: HARIClient = client
        self.dataset_id: uuid.UUID = dataset_id
        self.object_categories = object_categories or set()
        self._config: HARIUploaderConfig = self.client.config.hari_uploader
        self._medias: list[HARIMedia] = []
        self._media_back_references: set[str] = set()
        self._media_object_back_references: set[str] = set()
        self._media_object_cnt: int = 0
        self._attribute_cnt: int = 0
        # TODO: this should be a dict[str, uuid.UUID] as soon as the api models are updated
        self._object_category_subsets: dict[str, str] = {}
        self._unique_attribute_ids: set[str] = set()
        self._with_media_files_upload: bool = True

    # TODO: add_media shouldn't do validation logic, because that expects that a specific order of operation is necessary,
    # specifically that means that media_objects and attributes have to be added to media before the media is added to the uploader.
    # --> refactor this, so that all logic happenning in the add_* functions happens when the upload method is run.
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
        for media in args:
            # check and remember media back_references
            if media.back_reference in self._media_back_references:
                log.warning(
                    f"Found duplicate media back_reference: {media.back_reference}. If "
                    f"you want to be able to match HARI objects 1:1 to your own, "
                    f"consider using unique back_references."
                )
            else:
                self._media_back_references.add(media.back_reference)

            self._medias.append(media)
            self._attribute_cnt += len(media.attributes)
            for attr in media.attributes:
                self._unique_attribute_ids.add(str(attr.id))
                # annotatable_type is optional for a HARIAttribute, but can already be set here
                if not attr.annotatable_type:
                    attr.annotatable_type = models.DataBaseObjectType.MEDIA

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
                self._media_object_cnt += 1
                self._attribute_cnt += len(media_object.attributes)
                for attr in media_object.attributes:
                    self._unique_attribute_ids.add(str(attr.id))
                    # annotatable_type is optional for a HARIAttribute, but can already be set here
                    if not attr.annotatable_type:
                        attr.annotatable_type = models.DataBaseObjectType.MEDIAOBJECT

    def _add_object_category_subset(self, object_category: str, subset_id: str) -> None:
        self._object_category_subsets[object_category] = subset_id

    def _create_object_category_subsets(self, object_categories: list[str]) -> None:
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

    def _load_dataset(self) -> models.DatasetResponse:
        """Get the dataset from the HARI API."""
        return self.client.get_dataset(dataset_id=self.dataset_id)

    def _dataset_uses_external_media_source(self) -> bool:
        """Returns whether the dataset uses an external media source."""
        dataset = self._load_dataset()
        return dataset and dataset.external_media_source is not None

    def validate_all_attributes(self) -> None:
        """Validates all attributes of medias and media objects."""
        all_attributes = []
        for media in self._medias:
            all_attributes.extend(media.attributes)
            for media_object in media.media_objects:
                all_attributes.extend(media_object.attributes)
        validation.validate_attributes(all_attributes)

    def validate_unique_attributes_limit(self) -> None:
        existing_attr_metadata = self.client.get_attribute_metadata(
            dataset_id=self.dataset_id
        )
        existing_attribute_ids = {attr.id for attr in existing_attr_metadata}
        all_attribute_ids = existing_attribute_ids.union(self._unique_attribute_ids)

        if len(all_attribute_ids) > MAX_ATTR_COUNT:
            raise HARIUniqueAttributesLimitExceeded(
                new_attributes_number=len(self._unique_attribute_ids),
                existing_attributes_number=len(existing_attr_metadata),
                intended_attributes_number=len(all_attribute_ids),
            )

    def _determine_media_files_upload_behavior(self) -> None:
        """Checks whether media file_path or file_key are set according to whether the dataset uses an external media source or not.
        When using an external media source, the file_key must be set, otherwise the file_path must be set.
        """
        if self._dataset_uses_external_media_source():
            if any(not media.file_key for media in self._medias):
                raise HARIMediaValidationError(
                    f"Dataset with id {self.dataset_id} uses an external media source, "
                    "but not all medias have a file_key set. Make sure to set their file_key."
                )
            self._with_media_files_upload = False
        else:
            if any(not media.file_path for media in self._medias):
                raise HARIMediaValidationError(
                    f"Dataset with id {self.dataset_id} requires media files to be uploaded, "
                    "but not all medias have a file_path set. Make sure to set their file_path."
                )
            self._with_media_files_upload = True

    def upload(
        self,
    ) -> HARIUploadResults | None:
        """
        Upload all Media and their MediaObjects to HARI.

        Returns:
            HARIUploadResults | None: All upload results and summaries for the
            upload of medias and media_objects, or None if nothing was uploaded

        Raises:
            HARIUniqueAttributesLimitExceeded: If the number of unique attribute ids
            exceeds the limit of MAX_ATTR_COUNT per dataset.
        """

        # sync important information with the BE
        self._determine_media_files_upload_behavior()

        # validations
        if len(self._medias) == 0:
            log.info(
                "No medias to upload. Add them with HARIUploader::add_media() first "
                "before calling HARIUploader::upload()."
            )
            return None

        self.validate_unique_attributes_limit()
        self.validate_all_attributes()

        # validation and object_category subset syncing
        self._handle_object_categories()

        # upload batches of medias
        log.info(
            f"Starting upload of {len(self._medias)} medias with "
            f"{self._media_object_cnt} media_objects and {self._attribute_cnt} "
            f"attributes to HARI."
        )
        self._media_upload_progress = tqdm.tqdm(
            desc="Media Upload", total=len(self._medias)
        )
        self._media_object_upload_progress = tqdm.tqdm(
            desc="Media Object Upload", total=self._media_object_cnt
        )
        self._attribute_upload_progress = tqdm.tqdm(
            desc="Attribute Upload", total=self._attribute_cnt
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
        for media in medias_to_upload:
            self._set_bulk_operation_annotatable_id(item=media)

        # upload media batch
        media_upload_response = self.client.create_medias(
            dataset_id=self.dataset_id,
            medias=medias_to_upload,
            with_media_files_upload=self._with_media_files_upload,
        )
        self._media_upload_progress.update(len(medias_to_upload))

        # TODO: what if upload failures occur in the media upload above?
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
        response = self.client.create_attributes(
            dataset_id=self.dataset_id, attributes=attributes_to_upload
        )
        return response

    def _upload_media_object_batch(
        self, media_objects_to_upload: list[HARIMediaObject]
    ) -> models.BulkResponse:
        for media_object in media_objects_to_upload:
            self._set_bulk_operation_annotatable_id(item=media_object)
        response = self.client.create_media_objects(
            dataset_id=self.dataset_id, media_objects=media_objects_to_upload
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

            for i, media_object in enumerate(media.media_objects):
                # Create a copy of the media object to avoid changing shared attributes
                media.media_objects[i] = copy.deepcopy(media_object)
                media.media_objects[i].media_id = media_upload_response.item_id

    def _update_hari_attribute_media_object_ids(
        self,
        media_objects_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_object_upload_bulk_response: models.BulkResponse,
    ) -> None:
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
            for i, attribute in enumerate(media_object.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media_object.attributes[i] = copy.deepcopy(attribute)
                media_object.attributes[
                    i
                ].annotatable_id = media_object_upload_response.item_id
                media_object.attributes[
                    i
                ].annotatable_type = models.DataBaseObjectType.MEDIAOBJECT

    def _update_hari_attribute_media_ids(
        self,
        medias_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_upload_bulk_response: models.BulkResponse,
    ) -> None:
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
            for i, attribute in enumerate(media.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media.attributes[i] = copy.deepcopy(attribute)
                media.attributes[i].annotatable_id = media_upload_response.item_id
                media.attributes[i].annotatable_type = models.DataBaseObjectType.MEDIA

    def _set_bulk_operation_annotatable_id(self, item: HARIMedia | HARIMediaObject):
        if not item.bulk_operation_annotatable_id:
            item.bulk_operation_annotatable_id = str(uuid.uuid4())


def _merge_bulk_responses(*args: models.BulkResponse) -> models.BulkResponse:
    """
    Merges multiple BulkResponse objects into one.
    If no BulkResponse objects are provided, an empty BulkResponse object with status SUCCESS is returned.
    If only one BulkResponse object is provided, it will be returned as is.

    Args:
        *args: Multiple BulkResponse objects

    Returns:
        models.BulkResponse: The merged BulkResponse object
    """
    final_response = models.BulkResponse()

    if len(args) == 0:
        final_response.status = models.BulkOperationStatusEnum.SUCCESS
        return final_response

    if len(args) == 1:
        return args[0]

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
    elif (
        models.BulkOperationStatusEnum.SUCCESS
        or models.BulkOperationStatusEnum.PARTIAL_SUCCESS in statuses
    ):
        # if success appears at least once, it's a partial_success
        final_response.status = models.BulkOperationStatusEnum.PARTIAL_SUCCESS
    else:
        # any other case should be considered a failure
        final_response.status = models.BulkOperationStatusEnum.FAILURE

    return final_response
