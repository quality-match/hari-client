"""HARI Uploader for bulk uploading media and annotations."""
import copy
import typing
import uuid

import pydantic
import tqdm

from hari_client import HARIClient
from hari_client import HARIUploaderConfig
from hari_client import models
from hari_client import validation
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
    scene_back_reference: str | None = pydantic.Field(default=None, exclude=True)
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

    def set_scene_back_reference(self, scene_back_reference: str) -> None:
        self.scene_back_reference = scene_back_reference

    def set_frame_idx(self, frame_idx: int) -> None:
        self.frame_idx = frame_idx

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
        scenes: set[str] | None = None,
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
        """
        self.client: HARIClient = client
        self.dataset_id: uuid.UUID = dataset_id
        self.object_categories = object_categories or set()
        self.scenes = scenes or set()
        self._config: HARIUploaderConfig = self.client.config.hari_uploader
        self._medias: list[HARIMedia] = []
        self._media_back_references: set[str] = set()
        self._media_object_back_references: set[str] = set()
        self._media_object_cnt: int = 0
        self._attribute_cnt: int = 0
        # Initialize property mappings
        self._object_category_subsets: dict[str, str] = {}
        self._scenes: dict[str, str] = {}
        self._unique_attribute_ids: set[str] = set()

        # Set up the property validator for scene and object category validation
        self.validator = property_validator.PropertyValidator(
            allowed_values={
                "scene_back_reference": self.scenes,
                "object_category_subset_name": self.object_categories,
            },
            consistency_fields=["scene_back_reference", "frame_idx"],
        )

        # TODO: add_media shouldn't do validation logic, because that expects that a specific order of operation is necessary,
        # specifically that means that media_objects and attributes have to be added to media before the media is added to the uploader.
        # --> refactor this, so that all logic happenning in the add_* functions

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

    def _get_existing_scenes(self) -> list[models.Scene]:
        """Retrieves all existing scenes from the server."""
        return self.client.get_scenes(dataset_id=self.dataset_id)

    def get_existing_object_category_subsets(self) -> list[models.DatasetResponse]:
        """Fetch existing object_category subsets from the server."""
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

    def validate_all_attributes(self) -> None:
        """Validates all attributes of medias and media objects."""
        all_attributes = []
        for media in self._medias:
            all_attributes.extend(media.attributes)
            for media_object in media.media_objects:
                all_attributes.extend(media_object.attributes)
        validation.validate_attributes(all_attributes)

    def upload(self) -> HARIUploadResults | None:
        """
        Upload all Media and their MediaObjects to HARI.

        Returns:
            HARIUploadResults | None: All upload results and summaries for the
            upload of medias and media_objects, or None if nothing was uploaded

        Raises:
            HARIUniqueAttributesLimitExceeded: If the number of unique attribute ids
            exceeds the limit of MAX_ATTR_COUNT per dataset.
        """

        if len(self._medias) == 0:
            log.info(
                "No medias to upload. Add them with HARIUploader::add_media() first "
                "before calling HARIUploader::upload()."
            )
            return None

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

        self.validate_all_attributes()

        # Handle scene and object category setup and validation
        self._handle_scene_and_category_data()

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
            dataset_id=self.dataset_id, medias=medias_to_upload
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
        models.BulkOperationStatusEnum.SUCCESS in statuses
        or models.BulkOperationStatusEnum.PARTIAL_SUCCESS in statuses
    ):
        # if success appears at least once, it's a partial_success
        final_response.status = models.BulkOperationStatusEnum.PARTIAL_SUCCESS
    else:
        # any other case should be considered a failure
        final_response.status = models.BulkOperationStatusEnum.FAILURE

    return final_response
