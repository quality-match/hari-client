import copy
import typing
import uuid

import pydantic
import tqdm

from hari_client import HARIClient
from hari_client import HARIUploaderConfig
from hari_client import models
from hari_client import validation
from hari_client.client import client
from hari_client.client import errors
from hari_client.upload import property_validator
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
    scene_back_reference: str | None = pydantic.Field(default=None, exclude=True)

    # state aware uploader
    # id of existing media object used for its attributes
    id: str = pydantic.Field(default=None, exclude=True)
    # whether the object was already uploaded and identified by back reference
    uploaded: bool = pydantic.Field(default=None, exclude=True)

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
            if not attribute.annotatable_type:
                attribute.annotatable_type = models.DataBaseObjectType.MEDIAOBJECT
            self.attributes.append(attribute)

    def set_object_category_subset_name(self, object_category_subset_name: str) -> None:
        self.object_category_subset_name = object_category_subset_name

    def set_scene_back_reference(self, scene_back_reference: str) -> None:
        self.scene_back_reference = scene_back_reference

    def set_frame_idx(self, frame_idx: int) -> None:
        self.frame_idx = frame_idx

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


class HARIUnknownSceneNameError(Exception):
    pass


class HARIInconsistentFieldError(Exception):
    """Error raised when a Media and its MediaObject have inconsistent fields."""


class HARIMediaValidationError(Exception):
    pass


class HARIUniqueAttributesLimitExceeded(Exception):
    existing_attributes_number: int
    intended_attributes_number: int

    message: str

    def __init__(
        self,
        existing_attributes_number: int,
        intended_attributes_number: int,
    ):
        self.existing_attributes_number = existing_attributes_number
        self.intended_attributes_number = intended_attributes_number

        message = (
            f"You are trying to upload too many different attributes for one dataset"
            f" when the limit for different attribute ids per dataset is {MAX_ATTR_COUNT}. "
        )

        if existing_attributes_number > 0:
            message += (
                f"There are already {existing_attributes_number} different attribute ids uploaded. "
                f"The intended number of all attribute ids per dataset would be {intended_attributes_number}"
            )

        message += (
            " Please make sure to reuse attribute ids you've already generated "
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
    scene_back_reference: str | None = pydantic.Field(default=None, exclude=True)
    # overwrites the bulk_operation_annotatable_id field to not be required,
    # because it's set internally by the HARIUploader
    bulk_operation_annotatable_id: str | None = ""

    # state aware uploader
    # id of existing media object used for its objects and attributes
    id: str = pydantic.Field(default=None, exclude=True)
    # whether the media was already uploaded and identified by back reference
    uploaded: bool = pydantic.Field(default=None, exclude=True)

    # overrides the BulkMediaCreate validator to not raise error if the bulk_operation_annotatable_id is not set;
    # the field is set internally by the HARIUploader
    @pydantic.model_validator(mode="before")
    @classmethod
    def check_bulk_operation_annotatable_id_omitted(
        cls, data: typing.Any
    ) -> typing.Any:
        return data

    def set_scene_back_reference(self, scene_back_reference: str) -> None:
        self.scene_back_reference = scene_back_reference

    def set_frame_idx(self, frame_idx: int) -> None:
        self.frame_idx = frame_idx

    def add_media_object(self, *args: HARIMediaObject) -> None:
        for media_object in args:
            self.media_objects.append(media_object)

    def add_attribute(self, *args: HARIAttribute) -> None:
        for attribute in args:
            if not attribute.annotatable_type:
                attribute.annotatable_type = models.DataBaseObjectType.MEDIA
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


class HARIUploadFailures(pydantic.BaseModel):
    """Tracks failed uploads and their dependencies with the reason for the failure."""

    failed_medias: list[tuple[HARIMedia, list[str]]] = pydantic.Field(
        default_factory=list
    )
    failed_media_objects: list[tuple[HARIMediaObject, list[str]]] = pydantic.Field(
        default_factory=list
    )
    failed_media_attributes: list[tuple[HARIAttribute, list[str]]] = pydantic.Field(
        default_factory=list
    )
    failed_media_object_attributes: list[
        tuple[HARIAttribute, list[str]]
    ] = pydantic.Field(default_factory=list)


class HARIUploadResults(pydantic.BaseModel):
    medias: models.BulkResponse
    media_objects: models.BulkResponse
    attributes: models.BulkResponse
    failures: HARIUploadFailures


class HARIUploader:
    def __init__(
        self,
        client: HARIClient,
        dataset_id: uuid.UUID,
        object_categories: set[str] | None = None,
        scenes: set[str] | None = None,
        skip_uploaded_medias=True,
        skip_uploaded_media_objects=True,
    ) -> None:
        """Initializes the HARIUploader.

        Args:
            client: A HARIClient object.
            dataset_id: ID of the dataset to upload to.
            object_categories: A set of object categories present in the media_objects.
                If media_objects have an object_category_subset_name assigned, it has to be from this set.
                HARIUploader will create a HARI subset for each object_category and add the corresponding medias and media_objects to it.
            scenes: A set of scenes present in the media_objects.
                If media_objects have a scene_back_reference assigned, it has to be from this set.
            skip_uploaded_media_objects: Whether to skip media objects that have already been uploaded by comparing their back references.
                It is recommended to use this check but for large datasets it might be inefficient if this is handled before the upload.
            skip_uploaded_medias: Whether to skip medias that have already been uploaded by comparing their back references.
                It is recommended to use this check but for large datasets it might be inefficient if this is handled before the upload.
        """
        self.client: HARIClient = client
        self.dataset_id: uuid.UUID = dataset_id
        self.object_categories = object_categories or set()
        self.scenes = scenes or set()
        self.skip_uploaded_medias = skip_uploaded_medias
        self.skip_uploaded_media_objects = skip_uploaded_media_objects

        self._config: HARIUploaderConfig = self.client.config.hari_uploader
        self._medias: list[HARIMedia] = []
        # Initialize property mappings
        self._object_category_subsets: dict[str, str] = {}
        self._scenes: dict[str, str] = {}
        self._with_media_files_upload: bool = True
        self.failures: HARIUploadFailures = HARIUploadFailures()

        # Set up the property validator for scene and object category validation
        self.validator = property_validator.PropertyValidator(
            allowed_values={
                "scene_back_reference": self.scenes,
                "object_category_subset_name": self.object_categories,
            },
            consistency_fields=["scene_back_reference", "frame_idx"],
        )

    def add_media(self, *args: HARIMedia) -> None:
        """
        Add one or more HARIMedia objects to the uploader.

        Args:
            *args: Multiple HARIMedia objects
        """
        self._medias.extend(args)

    def _get_existing_scenes(self) -> list[models.Scene]:
        """Retrieves all existing scenes from the server."""
        return self.client.get_scenes(dataset_id=self.dataset_id)

    def get_existing_object_category_subsets(self) -> list[models.DatasetResponse]:
        """
        Fetch existing object_category subsets for the current dataset from the server.

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

    def _handle_scene_and_category_data(self) -> None:
        """Handle scene and object category setup and validation."""
        log.info("Initializing scenes and object categories.")

        # 1. Validate all properties
        is_valid, validation_result, to_create = self.validator.validate_properties(
            self._medias,
            HARIUnknownSceneNameError,
            HARIMediaObjectUnknownObjectCategorySubsetNameError,
            HARIInconsistentFieldError,
        )

        # Check for validation errors
        if not is_valid:
            all_errors = validation_result.get_all_errors()
            log.error(f"Found {len(all_errors)} validation errors.")
            raise ExceptionGroup("Property validation failed", all_errors)

        # 2. Fetch existing properties from server
        existing_scenes = self._get_existing_scenes()
        backend_object_category_subsets = self.get_existing_object_category_subsets()

        # 3. Create mappings for existing properties
        property_mappings = {
            "scene_back_reference": {
                scene.back_reference: str(scene.id) for scene in existing_scenes
            },
            "object_category_subset_name": {
                subset.name: str(subset.id)
                for subset in backend_object_category_subsets
            },
        }

        # 4. Filter out properties that already exist
        scenes_to_create = [
            scene
            for scene in to_create["scene_back_reference"]
            if scene and scene not in property_mappings["scene_back_reference"]
        ]

        categories_to_create = [
            category
            for category in to_create["object_category_subset_name"]
            if category
            and category not in property_mappings["object_category_subset_name"]
        ]

        # 5. Create missing properties
        self._create_missing_properties(
            scenes_to_create=scenes_to_create,
            categories_to_create=categories_to_create,
            property_mappings=property_mappings,
        )

        # 6. Store mappings for later reference
        self._scenes = property_mappings["scene_back_reference"]
        self._object_category_subsets = property_mappings["object_category_subset_name"]

        # 7. Assign IDs to objects
        self._assign_property_ids()

        log.info(f"All scenes of this dataset: {self._scenes=}")
        log.info(
            f"All object category subsets of this dataset: {self._object_category_subsets=}"
        )

    def _create_missing_properties(
        self,
        property_mappings: dict[str, dict[str, str]],
        scenes_to_create: list[str] | None = None,
        categories_to_create: list[str] | None = None,
    ) -> None:
        """Create missing properties on the server.

        Args:
            property_mappings: Dictionary to store property mappings.
            scenes_to_create: Scene back references to create.
            categories_to_create: Object category subset names to create.
        """
        # Create missing scenes
        if scenes_to_create:
            # Collect frame information for scenes
            frame_info = self.validator.collect_frame_info(
                self._medias, "scene_back_reference"
            )

            # Create the scenes
            for scene_back_reference in sorted(scenes_to_create):
                frames = [
                    models.Frame(index=idx)
                    for idx in sorted(frame_info.get(scene_back_reference, set()))
                ]
                scene = self.client.create_scene(
                    dataset_id=self.dataset_id,
                    back_reference=scene_back_reference,
                    frames=frames,
                )
                property_mappings["scene_back_reference"][scene_back_reference] = str(
                    scene.id
                )
                log.info(f"Created scene: {scene_back_reference} with id {scene.id}")

        # Create missing object categories
        if categories_to_create:
            for category_name in sorted(categories_to_create):
                subset_id = self.client.create_empty_subset(
                    dataset_id=self.dataset_id,
                    subset_type=models.SubsetType.MEDIA_OBJECT,
                    subset_name=category_name,
                    object_category=True,
                )
                property_mappings["object_category_subset_name"][
                    category_name
                ] = subset_id
                log.info(
                    f"Created object category: {category_name} with id {subset_id}"
                )

    def _assign_property_ids(self) -> None:
        """Assign scene and object category IDs to medias and media objects."""
        for media in self._medias:
            # Track subset_ids to avoid duplicates
            media_subset_ids = set(media.subset_ids or [])

            # Handle scene assignment for media
            if hasattr(media, "scene_back_reference") and media.scene_back_reference:
                media.scene_id = self._scenes[media.scene_back_reference]
                if media.frame_idx is None:
                    raise ValueError("Frame index must be set when specifying scenes")

            for media_object in media.media_objects:
                # Handle scene assignment for media object
                if (
                    hasattr(media_object, "scene_back_reference")
                    and media_object.scene_back_reference
                ):
                    media_object.scene_id = self._scenes[
                        media_object.scene_back_reference
                    ]
                    if media_object.frame_idx is None:
                        raise ValueError(
                            "Frame index must be set when specifying scenes"
                        )

                # Handle object category assignment
                if (
                    hasattr(media_object, "object_category_subset_name")
                    and media_object.object_category_subset_name
                ):
                    category_id = self._object_category_subsets[
                        media_object.object_category_subset_name
                    ]

                    # Assign the object category ID
                    media_object.object_category = uuid.UUID(category_id)

                    # Add to subset_ids for media_object
                    media_object_subset_ids = set(media_object.subset_ids or [])
                    media_object_subset_ids.add(category_id)
                    media_object.subset_ids = list(media_object_subset_ids)

                    # Also add to media's subset_ids
                    media_subset_ids.add(category_id)

            # Update media subset_ids
            if media_subset_ids:
                media.subset_ids = list(media_subset_ids)

    def _load_dataset(self) -> models.DatasetResponse:
        """Get the dataset from the HARI API."""
        return self.client.get_dataset(dataset_id=self.dataset_id)

    def _dataset_uses_external_media_source(self) -> bool:
        """Returns whether the dataset uses an external media source."""
        dataset = self._load_dataset()
        return dataset and dataset.external_media_source is not None

    def validate_medias(self) -> None:
        media_back_references = set()
        for media in self._medias:
            # validate back reference uniqueness
            if media.back_reference in media_back_references:
                log.warning(
                    f"Found duplicate media back_reference: {media.back_reference}. If "
                    f"you want to be able to match HARI objects 1:1 to your own, "
                    f"consider using unique back_references."
                )
            else:
                media_back_references.add(media.back_reference)

    def validate_media_objects(self, media_objects: list[HARIMediaObject]) -> None:
        media_object_back_references = set()
        for media_object in media_objects:
            # validate back reference uniqueness
            if media_object.back_reference in media_object_back_references:
                log.warning(
                    f"Found duplicate media_object back_reference: "
                    f"{media_object.back_reference}. If you want to be able to match HARI "
                    f"objects 1:1 to your own, consider using unique "
                    f"back_references."
                )
            else:
                media_object_back_references.add(media_object.back_reference)

    def validate_all_attributes(self) -> int:
        """
        Validates all attributes for both media and media objects, ensuring they meet the
        dataset's requirements and do not exceed the allowed unique attribute limit.
        Reuses existing attribute ids and new attributes ids if they have the same name and annotatable type,

        Returns:
            Number of all attributes.

        Raises:
            HARIUniqueAttributesLimitExceeded: If the number of unique attribute ids exceeds
            the limit of MAX_ATTR_COUNT per dataset.
            Any validation errors raised by the validate_attributes function.
        """

        # Get existing attributes
        existing_attr_metadata = self.client.get_attribute_metadata(
            dataset_id=self.dataset_id
        )
        attribute_name_to_ids: dict[tuple[str, str], str | uuid.UUID] = {
            (attr.name, attr.annotatable_type): attr.id
            for attr in existing_attr_metadata
        }

        all_attributes = self.reuse_existing_attribute_ids(attribute_name_to_ids)

        # Raises an error if any requirements for attribute consistency aren't met.
        validation.validate_attributes(all_attributes)

        if len(attribute_name_to_ids) > MAX_ATTR_COUNT:
            raise HARIUniqueAttributesLimitExceeded(
                existing_attributes_number=len(existing_attr_metadata),
                intended_attributes_number=len(attribute_name_to_ids),
            )

        return len(all_attributes)

    def reuse_existing_attribute_ids(
        self, attribute_name_to_ids: dict[tuple[str, str], str | uuid.UUID]
    ) -> None:
        """
        Reuses existing attribute ids for attributes that have the same name and annotatable type.
        Args:
            attribute_name_to_ids: A dictionary mapping attribute names and annotatable types to their ids.

        Returns:
            attributes with reused ids.
        """

        attributes = []

        for media in self._medias:
            attributes.extend(media.attributes)

            for attr in media.attributes:
                # assign an existing id if attribute with the same name exists, otherwise create a new one
                if (attr.name, attr.annotatable_type) not in attribute_name_to_ids:
                    attribute_name_to_ids[(attr.name, attr.annotatable_type)] = attr.id
                else:
                    log.info(
                        f"reusing existing attribute id for attribute name {attr.name}"
                    )
                    attr.id = attribute_name_to_ids[(attr.name, attr.annotatable_type)]

            for media_object in media.media_objects:
                attributes.extend(media_object.attributes)

                for attr in media_object.attributes:
                    # assign an existing id if attribute with the same name exists, otherwise create a new one
                    if (attr.name, attr.annotatable_type) not in attribute_name_to_ids:
                        attribute_name_to_ids[
                            (attr.name, attr.annotatable_type)
                        ] = attr.id
                    else:
                        log.info(
                            f"reusing existing attribute id for attribute name {attr.name}"
                        )
                        attr.id = attribute_name_to_ids[
                            (attr.name, attr.annotatable_type)
                        ]

        return attributes

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

            log.info(
                "Dataset uses an external media source. No media files will be uploaded."
            )
            self._with_media_files_upload = False
        else:
            if any(not media.file_path for media in self._medias):
                raise HARIMediaValidationError(
                    f"Dataset with id {self.dataset_id} requires media files to be uploaded, "
                    "but not all medias have a file_path set. Make sure to set their file_path."
                )
            self._with_media_files_upload = True

    def mark_already_uploaded_medias(self, medias: list[HARIMedia]) -> None:
        """
        Checks medias that already exist on the server by comparing back_references and mark them as uploaded.

        Args:
            medias: The list of medias intended for upload.
        """
        uploaded_medias = self.client.get_medias_paginated(self.dataset_id)

        self._mark_already_uploaded_entities(medias, uploaded_medias)

    def mark_already_uploaded_media_objects(
        self, media_objects: list[HARIMediaObject]
    ) -> None:
        """
        Check media objects that already exist on the server by comparing back_references and mark them as uploaded.

        Args:
            media_objects: The list of media objects intended for upload.
        """
        uploaded_media_objects = self.client.get_media_objects_paginated(
            self.dataset_id
        )

        self._mark_already_uploaded_entities(media_objects, uploaded_media_objects)

    def _mark_already_uploaded_entities(
        self,
        entities_to_upload: list[HARIMediaObject] | list[HARIMedia],
        entities_uploaded: list[models.MediaResponse]
        | list[models.MediaObjectResponse],
    ) -> None:
        """
        Marks items in entities_to_upload as already uploaded if their back_references appear
        among the entities_uploaded. Prints warnings if multiple references are found.

        Args:
            entities_to_upload: The list of media or media objects to be uploaded.
            entities_uploaded: The media or media objects already present in the dataset.
        """
        # build look up table for back references
        # add warning if multiple of the same back reference are given, value will be overwritten
        uploaded_back_references = {}
        for entity in entities_uploaded:
            if entity.back_reference in uploaded_back_references:
                log.warning(
                    f"Multiple of the same back reference '{entity.back_reference}' encountered on the server; "
                    f"using the last found id."
                )
            uploaded_back_references[entity.back_reference] = entity.id

        for entity in entities_to_upload:
            # ensure uploaded marked are always having an id
            entity.uploaded = entity.back_reference in uploaded_back_references
            entity.id = uploaded_back_references.get(entity.back_reference)

    def upload(
        self,
    ) -> HARIUploadResults | None:
        """
        Uploads all HARIMedia items along with their media objects and attributes to HARI.

        This method:
          1. Validates media, media_objects and attributes to be consistent and do not include duplicates.
          2. (Optionally) skips already uploaded medias and media objects by comparing their back references, if specified.
          3.Ensures all object categories subsets are either reused or created if not yet exist.
          4. Batches the actual uploading of medias, media objects, and attributes. The items are uploaded as media batches,
            if medias are uploaded, the corresponding media objects and attributes for this media batch are uploaded.

        Returns:
            All upload results and summaries for the upload of medias media_objects and attributes, or None if nothing was uploaded.

        Raises:
          - Any critical validation error that prevents the upload.
          - Any error that occurs during the upload process.
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

        all_media_objects = []
        for media in self._medias:
            for media_object in media.media_objects:
                all_media_objects.append(media_object)

        self.validate_medias()
        self.validate_media_objects(all_media_objects)
        attr_count = self.validate_all_attributes()

        # Handle scene and object category setup and validation
        self._handle_scene_and_category_data()

        if self.skip_uploaded_medias:
            self.mark_already_uploaded_medias(self._medias)

        if self.skip_uploaded_media_objects:
            self.mark_already_uploaded_media_objects(all_media_objects)

        (
            media_upload_responses,
            media_object_upload_responses,
            attribute_upload_responses,
        ) = self.upload_data_in_batches(attr_count, len(all_media_objects))

        return HARIUploadResults(
            medias=_merge_bulk_responses(*media_upload_responses),
            media_objects=_merge_bulk_responses(*media_object_upload_responses),
            attributes=_merge_bulk_responses(*attribute_upload_responses),
            failures=self.failures,
        )

    def _upload_media_batch(
        self, medias_to_upload: list[HARIMedia]
    ) -> models.BulkResponse:
        """
        Uploads medias from one batch.

        Args:
            medias_to_upload: A list of HARIMedia to upload.

        Returns:
            the bulk response for medias.
        """
        medias_need_upload = []
        medias_skipped = []
        for media in medias_to_upload:
            self._set_bulk_operation_annotatable_id(item=media)
            if media.uploaded:
                medias_skipped.append(media)
            else:
                medias_need_upload.append(media)

        # upload only needed media for batch
        if medias_need_upload:
            # prevents failing if bulk response status is failure
            try:
                media_upload_response = self.client.create_medias(
                    dataset_id=self.dataset_id,
                    medias=medias_need_upload,
                    with_media_files_upload=self._with_media_files_upload,
                )
            except errors.APIError as e:
                media_upload_response = client._parse_response_model(
                    response_data=e.message, response_model=models.BulkResponse
                )
        else:
            # if no media needs to be uploaded, return an empty response
            media_upload_response = models.BulkResponse(
                status=models.ResponseStatesEnum.SUCCESS,
            )

        # manually mark medias that were skipped as successful
        media_upload_response.summary.successful += len(medias_skipped)
        media_upload_response.summary.total += len(medias_skipped)
        media_upload_response.results.extend(
            [
                models.AnnotatableCreateResponse(
                    bulk_operation_annotatable_id=media.bulk_operation_annotatable_id,
                    status=models.ResponseStatesEnum.SUCCESS,
                    item_id=media.id,
                )
                for media in medias_skipped
            ]
        )
        self._update_hari_media_object_media_ids(
            medias_to_upload=medias_to_upload,
            media_upload_bulk_response=media_upload_response,
        )
        self._update_hari_attribute_media_ids(
            medias_to_upload=medias_to_upload,
            media_upload_bulk_response=media_upload_response,
        )
        self._media_upload_progress.update(len(medias_to_upload))
        return media_upload_response

    def _upload_attributes_in_batches(
        self, attributes: list[HARIAttribute]
    ) -> list[models.BulkResponse]:
        """
        Uploads attributes in configured batch sizes, aggregating bulk responses.

        Args:
            attributes: A list of HARIAttribute objects to be uploaded.

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
        Uploads media objects in configured batch sizes, aggregating bulk responses.

        Args:
            media_objects: a list of HARIMediaObject objects to be uploaded.

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
            self._update_hari_attribute_media_object_ids(
                media_objects_to_upload=media_objects_to_upload,
                media_object_upload_bulk_response=response,
            )

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
        # prevents failing if bulk response status is failure
        try:
            response = self.client.create_attributes(
                dataset_id=self.dataset_id, attributes=attributes_to_upload
            )
        except errors.APIError as e:
            response = client._parse_response_model(
                response_data=e.message, response_model=models.BulkResponse
            )
        self._mark_already_uploaded_attributes_as_successful(response)
        return response

    def _mark_already_uploaded_attributes_as_successful(
        self, response: models.BulkResponse
    ) -> None:
        """
        Marks attributes that were already uploaded as successful in the BulkResponse
        and reevaluates the overall response.
        Args:
            response: The BulkResponse containing the results of the attribute upload.
        """
        for result in response.results:
            if result.status == models.ResponseStatesEnum.ALREADY_EXISTS:
                result.status = models.ResponseStatesEnum.SUCCESS
                result.errors = []

        # reevaluate the overall status
        unique_statuses = {result.status for result in response.results}
        if unique_statuses == {models.ResponseStatesEnum.SUCCESS}:
            response.status = models.BulkOperationStatusEnum.SUCCESS
        elif models.ResponseStatesEnum.SUCCESS in unique_statuses:
            response.status = models.BulkOperationStatusEnum.PARTIAL_SUCCESS
        else:
            response.status = models.BulkOperationStatusEnum.FAILURE

        # recalculate summary
        total = len(response.results)
        successful = sum(
            1 for r in response.results if r.status == models.ResponseStatesEnum.SUCCESS
        )
        failed = total - successful

        response.summary = models.BulkUploadSuccessSummary(
            total=total,
            successful=successful,
            failed=failed,
        )

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
        media_objects_need_upload = []
        media_objects_skipped = []
        for media_object in media_objects_to_upload:
            self._set_bulk_operation_annotatable_id(item=media_object)
            if media_object.uploaded:
                media_objects_skipped.append(media_object)
            else:
                media_objects_need_upload.append(media_object)

        if media_objects_need_upload:
            # prevents failing if bulk response status is failure
            try:
                response = self.client.create_media_objects(
                    dataset_id=self.dataset_id, media_objects=media_objects_need_upload
                )
            except errors.APIError as e:
                response = client._parse_response_model(
                    response_data=e.message, response_model=models.BulkResponse
                )
        else:
            # if no media objects need to be uploaded, return an empty response
            response = models.BulkResponse(
                status=models.ResponseStatesEnum.SUCCESS,
            )

        # manually mark media objects that were skipped as successful
        response.summary.successful += len(media_objects_skipped)
        response.summary.total += len(media_objects_skipped)
        response.results.extend(
            [
                models.AnnotatableCreateResponse(
                    bulk_operation_annotatable_id=media_object.bulk_operation_annotatable_id,
                    status=models.ResponseStatesEnum.SUCCESS,
                    item_id=media_object.id,
                )
                for media_object in media_objects_skipped
            ]
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

            for i, media_object in enumerate(media.media_objects):
                # Create a copy of the media object to avoid changing shared attributes
                media.media_objects[i] = copy.deepcopy(media_object)
                media.media_objects[i].media_id = media_upload_response.item_id

    def _update_hari_attribute_media_object_ids(
        self,
        media_objects_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_object_upload_bulk_response: models.BulkResponse,
    ) -> None:
        """
        Update the annotatable_id field for attributes belonging to media objects, using
        the IDs from the server's media object upload response.

        Args:
            media_objects_to_upload: The batch of HARIMediaObjects that was just uploaded.
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
            for i, attribute in enumerate(media_object.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media_object.attributes[i] = copy.deepcopy(attribute)
                media_object.attributes[
                    i
                ].annotatable_id = media_object_upload_response.item_id

    # Note: The following methods are here to allow the tests to demonstrate Idempotency.

    def _get_and_validate_media_objects_object_category_subset_names(
        self,
    ) -> tuple[set[str], list[HARIMediaObjectUnknownObjectCategorySubsetNameError]]:
        """Retrieves and validates the consistency of the object_category_subset_names that were assigned to media_objects.
        To be consistent, all media_object.object_category_subset_name values must be available in the set of object_categories specified in the HARIUploader constructor.
        A media_object isn't required to be assigned an object_category_subset_name, though.

        Returns:
            The first return value is the set of found object_category_subset_names,
                the second return value is the list of errors that were found during the validation.
        """
        # Use the validator to get object category subset information
        _, validation_result, _ = self.validator.validate_properties(
            self._medias,
            HARIUnknownSceneNameError,
            HARIMediaObjectUnknownObjectCategorySubsetNameError,
            HARIInconsistentFieldError,
        )

        found_obj_categories = validation_result.found_values.get(
            "object_category_subset_name", set()
        )
        obj_category_errors = validation_result.errors.get(
            "object_category_subset_name", []
        )

        return found_obj_categories, obj_category_errors

    def _get_and_validate_scene_back_references(
        self,
    ) -> tuple[set[str], list[HARIUnknownSceneNameError]]:
        """Retrieves and validates the consistency of the scene_back_references that were assigned to annotatables.
        To be consistent, all scene_back_reference values must be available in the set of scenes specified in the HARIUploader constructor.
        An annotatable isn't required to be assigned a scene_back_reference, though.

        Returns:
            The first return value is the set of found scenes,
                the second return value is the list of errors that were found during the validation.
        """
        # Use the validator to get scene back reference information
        _, validation_result, _ = self.validator.validate_properties(
            self._medias,
            HARIUnknownSceneNameError,
            HARIMediaObjectUnknownObjectCategorySubsetNameError,
            HARIInconsistentFieldError,
        )

        found_scenes = validation_result.found_values.get("scene_back_reference", set())
        obj_scene_errors = validation_result.errors.get("scene_back_reference", [])

        return found_scenes, obj_scene_errors

    def _validate_consistency(self) -> list[HARIInconsistentFieldError]:
        """Validates that scenes and frames are consistent between medias and their media_objects"""
        _, validation_result, _ = self.validator.validate_properties(
            self._medias,
            HARIUnknownSceneNameError,
            HARIMediaObjectUnknownObjectCategorySubsetNameError,
            HARIInconsistentFieldError,
        )

        consistency_errors = validation_result.errors.get("consistency", [])
        return consistency_errors

    def _assign_object_category_subsets(self) -> None:
        """Assigns object_category_subsets to media_objects and media based on media_object.object_category_subset_name"""
        # Use the renamed method that handles all entity ID assignments
        self._assign_property_ids()

    def _create_object_category_subsets(self, object_categories: list[str]) -> None:
        """Creates object_category subsets for the specified object_categories.

        Args:
            object_categories: List of object category names to create.
        """
        # Create empty entity mappings if they don't exist yet
        property_mappings = {
            "scene_back_reference": self._scenes,
            "object_category_subset_name": self._object_category_subsets,
        }

        # Create the object categories using the new method
        self._create_missing_properties(
            categories_to_create=object_categories, property_mappings=property_mappings
        )

    def _create_scenes(self, scenes: list[str]) -> None:
        """Creates scenes for the specified scene_back_references.

        Args:
            scenes: List of scene back references to create.
        """
        # Create empty entity mappings if they don't exist yet
        property_mappings = {
            "scene_back_reference": self._scenes,
            "object_category_subset_name": self._object_category_subsets,
        }

        # Create the scenes using the new method
        self._create_missing_properties(
            scenes_to_create=scenes,
            categories_to_create=[],
            property_mappings=property_mappings,
        )

    def _update_hari_attribute_media_ids(
        self,
        medias_to_upload: list[HARIMedia] | list[HARIMediaObject],
        media_upload_bulk_response: models.BulkResponse,
    ) -> None:
        """
        Update the annotatable_id field for attributes belonging to media, using
        the IDs from the server's media upload response.

        Args:
            medias_to_upload: The batch of HARIMedia that was just uploaded.
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
            for i, attribute in enumerate(media.attributes):
                # Create a copy of the attribute to avoid changing shared attributes
                media.attributes[i] = copy.deepcopy(attribute)
                media.attributes[i].annotatable_id = media_upload_response.item_id

    def _set_bulk_operation_annotatable_id(
        self, item: HARIMedia | HARIMediaObject
    ) -> None:
        """
        Assign a random UUID as the bulk_operation_annotatable_id for items that do not already
        have one, enabling the server to match each upload to the correct response entry.

        Args:
            item: The HARIMedia or HARIMediaObject whose bulk_operation_annotatable_id
            should be set if not already present.
        """
        if not item.bulk_operation_annotatable_id:
            item.bulk_operation_annotatable_id = str(uuid.uuid4())

    def _upload_single_batch(
        self, medias_to_upload: list[HARIMedia]
    ) -> tuple[
        models.BulkResponse, list[models.BulkResponse], list[models.BulkResponse]
    ]:
        """Uploads a batch of medias and their media_objects and attributes.
        Skips media_objects and attributes that have failed uploads.
        Returns: The response of the media upload, the responses of the media_object uploads, and the responses of the attribute uploads.
        """
        media_upload_response = self._upload_media_batch(
            medias_to_upload=medias_to_upload
        )

        failed_medias = []
        failed_media_attributes = []
        failed_media_objects = []
        failed_media_object_attributes = []

        if media_upload_response.status in [
            models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
            models.BulkOperationStatusEnum.FAILURE,
        ]:
            # build a lookup to map medias to their upload response results using the bulk_operation_annotatable_id
            media_upload_response_result_lookup = {
                result.bulk_operation_annotatable_id: result
                for result in media_upload_response.results
            }
            for media in medias_to_upload:
                media_upload_response_result = media_upload_response_result_lookup.get(
                    media.bulk_operation_annotatable_id
                )
                if (
                    media_upload_response_result
                    and media_upload_response_result.status
                    is not models.ResponseStatesEnum.SUCCESS
                ):
                    failed_medias.append(media)
                    self.failures.failed_medias.append(
                        (media, media_upload_response_result.errors)
                    )
                    # Media objects and their attributes will also be marked as failed since their related media failed
                    self.failures.failed_media_attributes.extend(
                        map(
                            lambda attribute: (
                                attribute,
                                ["Parent media upload failed. Skipping attribute."],
                            ),
                            media.attributes,
                        )
                    )
                    failed_media_attributes.extend(media.attributes)

                    self.failures.failed_media_objects.extend(
                        map(
                            lambda media_object: (
                                media_object,
                                ["Parent media upload failed. Skipping media object."],
                            ),
                            media.media_objects,
                        )
                    )
                    failed_media_objects.extend(media.media_objects)

                    for media_object in media.media_objects:
                        self.failures.failed_media_object_attributes.extend(
                            map(
                                lambda attribute: (
                                    attribute,
                                    [
                                        "Parent media object upload failed. Skipping media object attribute."
                                    ],
                                ),
                                media_object.attributes,
                            )
                        )
                        failed_media_object_attributes.extend(media_object.attributes)

        # filter out media_objects and attributes that should be skipped because its media failed to upload
        media_objects_to_upload: list[HARIMediaObject] = [
            media_object
            for media in medias_to_upload
            for media_object in media.media_objects
            if media_object not in failed_media_objects
        ]
        attributes_to_upload: list[HARIAttribute] = [
            attribute
            for media in medias_to_upload
            for attribute in media.attributes
            if attribute not in failed_media_attributes
        ]

        media_object_upload_responses = self._upload_media_objects_in_batches(
            media_objects_to_upload
        )

        # build a lookup to map media objects to their upload response results using the bulk_operation_annotatable_id
        media_object_upload_response_result_lookup = {}
        for media_object_upload_response in media_object_upload_responses:
            media_object_upload_response_result_lookup.update(
                {
                    result.bulk_operation_annotatable_id: result
                    for result in media_object_upload_response.results
                }
            )
        response_statuses = {result.status for result in media_object_upload_responses}

        # did any of the responses indicate a failure?
        if {
            models.BulkOperationStatusEnum.PARTIAL_SUCCESS,
            models.BulkOperationStatusEnum.FAILURE,
        }.intersection(set(response_statuses)):
            for media_object in media_objects_to_upload:
                media_object_upload_response_result = (
                    media_object_upload_response_result_lookup.get(
                        media_object.bulk_operation_annotatable_id
                    )
                )
                if (
                    media_object_upload_response_result
                    and media_object_upload_response_result.status
                    is not models.ResponseStatesEnum.SUCCESS
                ):
                    self.failures.failed_media_objects.append(
                        (media_object, media_object_upload_response_result.errors)
                    )
                    # Attributes will be marked as failed since their related media object failed
                    self.failures.failed_media_object_attributes.extend(
                        map(
                            lambda attribute: (
                                attribute,
                                [
                                    "Parent media object upload failed. Skipping media object attribute."
                                ],
                            ),
                            media_object.attributes,
                        )
                    )
                    failed_media_object_attributes.extend(media_object.attributes)

        # update attributes to upload with the media_object attributes that should not be skipped
        for media_object in media_objects_to_upload:
            media_object_attributes_to_upload = [
                attribute
                for attribute in media_object.attributes
                if attribute not in failed_media_object_attributes
            ]
            attributes_to_upload.extend(media_object_attributes_to_upload)
        # upload attributes of this batch of media in batches
        attributes_upload_responses = self._upload_attributes_in_batches(
            attributes_to_upload
        )
        return (
            media_upload_response,
            media_object_upload_responses,
            attributes_upload_responses,
        )

    def upload_data_in_batches(
        self, attribute_cnt: int, media_object_cnt: int
    ) -> tuple[list[models.BulkResponse], ...]:
        """Uploads all medias and their media_objects and attributes in batches.
        Args:
            attribute_cnt: The total number of attributes to upload, used for progress tracking.
            media_object_cnt: The total number of media objects to upload, used for progress tracking.
        """
        # upload batches of medias
        log.info(
            f"Starting upload of {len(self._medias)} medias with "
            f"{media_object_cnt} media_objects and {attribute_cnt} "
            f"attributes to HARI."
        )
        self._media_upload_progress = tqdm.tqdm(
            desc="Media Upload", total=len(self._medias)
        )
        self._media_object_upload_progress = tqdm.tqdm(
            desc="Media Object Upload", total=media_object_cnt
        )
        self._attribute_upload_progress = tqdm.tqdm(
            desc="Attribute Upload", total=attribute_cnt
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
                attributes_responses,
            ) = self._upload_single_batch(medias_to_upload)
            media_upload_responses.append(media_response)
            media_object_upload_responses.extend(media_object_responses)
            attribute_upload_responses.extend(attributes_responses)

        self._media_upload_progress.close()
        self._media_object_upload_progress.close()
        self._attribute_upload_progress.close()

        return (
            media_upload_responses,
            media_object_upload_responses,
            attribute_upload_responses,
        )


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
        models.BulkOperationStatusEnum.SUCCESS in statuses
        or models.BulkOperationStatusEnum.PARTIAL_SUCCESS in statuses
    ):
        # if success appears at least once, it's a partial_success
        final_response.status = models.BulkOperationStatusEnum.PARTIAL_SUCCESS
    else:
        # any other case should be considered a failure
        final_response.status = models.BulkOperationStatusEnum.FAILURE

    return final_response
