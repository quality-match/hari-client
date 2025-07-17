## [major.minor.patch] - DD-MM-YYYY

### Breaking Changes

- skip already uploaded media and media objects during upload by default (by comparing existing back references)
- get existing attribute metadata and reuse the existing ids on new attributes.
- removed _`media_back_references`, _`media_object_back_references`, _`media_object_cnt` and _`attribute_cnt` fields from the HARIUploader

### New features

- added `skip_uploaded_medias` and `skip_uploaded_media_objects` flags to uploader to enable/disable uploading
existing medias and media objects (defaulting to `True`)

### Fixes

- handle bulk responses parsing properly in hari uploader if bulk response status is `FAILURE` and 4xx error is returned
  - now no error is raised, but the response is parsed again to `BulkResponse` model
- remove all validation and other type of logic from `add_media` method of the uploader
- assign attribute annotatable type in `add_attribute` method

### Internal

- added `id` and `uploaded` fields to `HARIMedia` and `HARIMediaObject` to check later on whether the entity was uploaded,
and assign existing media/annotatable id
- created method for media and media objects validation that is executed before upload and move all validations there
- removed subset creation from `check_and_upload_dataset` utility

## [4.0.0] - 15-07-2025

### Breaking Changes

- Deleted `name_filter` from get multiple datasets endpoint [PR#91](https://github.com/quality-match/hari-client/pull/91)
- removed `lidar_sensor_pose` from `PointCloudMetadata` model, because it's not supported in the HARI backend [PR#90](https://github.com/quality-match/hari-client/pull/90)
- Changed type of `CuboidCenterPoint.dimensions` from `Point3DTuple` to `CuboidDimensionsTuple` [PR#95](https://github.com/quality-match/hari-client/pull/95)
  - the underlying data type is still a `NamedTuple` with three float attributes
- Validate that mediaObject type makes sense for the media it's being assigned to. [PR#96](https://github.com/quality-match/hari-client/pull/96)
- Validate that mediaObjects have a geometry. [PR#96](https://github.com/quality-match/hari-client/pull/96)
- Remove arguments for aint endpoints that were deleted from API models. [PR#103](https://github.com/quality-match/hari-client/pull/103)

### New Features

- Add pagination, sorting and filtering to the get annotation runs, pipelines, AINT learning data, ML annotation models, AI annotation runs methods [PR#91](https://github.com/quality-match/hari-client/pull/91)
- Add count annotation runs, pipelines, AINT learning data, ML annotation models, AI annotation runs methods [PR#91](https://github.com/quality-match/hari-client/pull/91)
- Add `ilike` query operator [PR#91](https://github.com/quality-match/hari-client/pull/91)
- Add method to download media files from dataset [PR#94](https://github.com/quality-match/hari-client/pull/94)
- Add `CompositeLidarViewerVisualisationConfigParameters` model as possible visualisation configuration [PR#90](https://github.com/quality-match/hari-client/pull/90)
  - update field `type` of all `*VisualisationConfigParameters` models to be defined with enum values of `VisualisationParameterType`
- Create separate bulk size limits in the config for medias, objects and attributes (500, 5000 and 750 respectively) [PR#106](https://github.com/quality-match/hari-client/pull/106)
  - Set presigned url maximum batch size to 500 accordingly

#### 3D

- added automatic scene creation to HARIUploader to support setting up a dataset with 3D data [PR#86](https://github.com/quality-match/hari-client/pull/86)
  - added `quickstart_3D.py` example script to show how to upload 3D data with the HARIUploader
- added small example 3D dataset which is used by the `quickstart_3D.py` script [PR#98](https://github.com/quality-match/hari-client/pull/98)
- added `sensor_id` and `timestamp` to `PointCloudMetadata` and `ImageMetadata` models [PR#90](https://github.com/quality-match/hari-client/pull/90)

### Fixes

- Prepare projection query parameter converting it to json string [PR#101](https://github.com/quality-match/hari-client/pull/101)

### Internal
- Add internal methods for getting annotation run metrics [PR#108](https://github.com/quality-match/hari-client/pull/108)
  - get_annotation_run_metrics
  - get_annotation_run_node_metrics
  - get_annotation_run_project_status
  - get_annotation_run_project

#### Consistency in partially failed uploads

- partially failed bulk uploads of medias and media objects are now handled consistently [PR#80](https://github.com/quality-match/hari-client/pull/80)
  - for failed media uploads, any media_objects and attributes for these medias will not be tried to be uploaded
  - for media_objects, any attributes for these media_objects will not be tried to be uploaded

#### Better reporting of failed and skipped uploads

- improved reporting of failed and skipped uploads [PR#80](https://github.com/quality-match/hari-client/pull/80)
  - failed uploads are now reported in the `HARIUploadResults.failures` field

### Internal

- Add automatic parsing of pydantic BaseModels in CustomJSONEncoder remove unnecessary parsing. [PR#102](https://github.com/quality-match/hari-client/pull/102)

## [3.5.0] - 24-04-2025

### New Features

- updated pydantic models [PR#63](https://github.com/quality-match/hari-client/pull/63)
  - added pydantic models for AINTLearningData, MLAnnotationModel, AIAnnotationRun, AttributeValue
- added new client endpoint methods [PR#63](https://github.com/quality-match/hari-client/pull/63)
  - paginated download of media, media_objects and attributes to the client to enable download of large dataset data to prevent download timeout
  - added handling of attribute values
  - added methods for AINTLearningData, MLAnnotationModel and AIAnnotationRun
- added helper/example scripts for usage of `AI Nano Tasks` (AINT) [PR#63](https://github.com/quality-match/hari-client/pull/63)
  - `aint/start_ai_annotation_run.py`,
  - `aint/create_aint_model.py`,
  - `aint/get_aint_attribute_info.py`
- added new client endpoint methods and models for pipelines and annotation runs [PR#65](https://github.com/quality-match/hari-client/pull/65):
  - `get_pipelines`
  - `get_pipeline`
  - `get_annotation_runs`
  - `get_annotation_run`
  - `create_annotation_run`
- added helper/example scripts for data upload [PR#58](https://github.com/quality-match/hari-client/pull/58)
  - added script `data_upload/trigger_metadata_rebuild.py`
  - added script `data_upload/upload_coco_like_dataset.py`
  - added script `data_upload/upload_yolo_like_dataset.py`
  - added script `data_upload/upload_single_image.py`
  - added script `data_upload/upload_dataset_with_own_annotation_attributes.py`
- added upload utilities [PR#58](https://github.com/quality-match/hari-client/pull/58)
  - added helper methods to check for existing datasets and subsets before upload
  - added helper method to trigger metadata rebuild and track its progress
- added user group as a possible argument in the update dataset method

### Fixes

- made `media_url` and `pii_media_url` optional in the `Media` model [PR#83](https://github.com/quality-match/hari-client/pull/83)

### Internal

- set new default value for `hari_api_base_url` in the config model [PR#85](https://github.com/quality-match/hari-client/pull/85)
- increase internal token expiration time buffer from 1 to 10 seconds

## [3.4.0] - 07-03-2025

### New features

#### Support for external media sources

- added support for defining external media sources when creating a dataset
  - new field `external_media_source` in the `create_dataset` method [PR#73](https://github.com/quality-match/hari-client/pull/73)
- added new endpoint `get_external_media_source` [PR#73](https://github.com/quality-match/hari-client/pull/73)
- added new arg to client method `create_medias` [PR#74](https://github.com/quality-match/hari-client/pull/74)
  - `with_media_files_upload` (default: `True`). Set this to `False` if you want to skip the upload of media files. This way the upload will only create medias in HARI without uploading media files to QM storage.
- added new arg to client method `create_media` [PR#74](https://github.com/quality-match/hari-client/pull/74)
  - `with_media_files_upload` (default: `True`). Set this to `False` if you want to skip the upload of the media file. This way the upload will only create medias in HARI without uploading media files to QM storage.
- added new field `file_key` to models `Media`, `MediaCreate` and `MediaResponse` [PR#77](https://github.com/quality-match/hari-client/pull/77)
- updated HARIUploader utility to support using a dataset with an external media source [PR#74](https://github.com/quality-match/hari-client/pull/74) [PR#77](https://github.com/quality-match/hari-client/pull/77)
  - when your dataset is using an external media source, make sure to set the `file_key` field of `HARIMedia` to the key of the media file in your cloud storage and don't set the `file_path`.
  - when your dataset isn't using an external media source, make sure to set the `file_path` field of `HARIMedia` and don't set the `file_key`.

### Internal

- removed obsolete `trigger_thumbnails_creation_job` and `trigger_crops_creation_job` client methods [PR#75](https://github.com/quality-match/hari-client/pull/75)

## [3.3.1] - 2025-02-28

### Fixes

- added `compute_auto_attributes` param to `trigger_dataset_metadata_rebuild_job` [PR#78](https://github.com/quality-match/hari-client/pull/78)

## [3.3.0] - 2025-02-27

### New Features

- added support for media objects of type segment [PR#62](https://github.com/quality-match/hari-client/pull/62)

## [3.2.0] - 25-02-2025

### New features

- added `compute_auto_attributes` param to `trigger_metadata_rebuild_job` [PR#71](https://github.com/quality-match/hari-client/pull/71)
- add `skip`, `limit`, `sort`, `query`, `name_filter` and `archived` parameters to `get_datasets` method [PR#67](https://github.com/quality-match/hari-client/pull/67)
- add `get_datasets_count` method [PR#67](https://github.com/quality-match/hari-client/pull/67)
- restricted attribute `possible_values` to be a list of strings [PR#66](https://github.com/quality-match/hari-client/pull/66)

## [3.1.0] - 14-01-2025

### New Features

- added a limit for the number of unique attribute ids that can be created for the dataset. [PR#51](https://github.com/quality-match/hari-client/pull/51) [PR#57](https://github.com/quality-match/hari-client/pull/57)
- added support for mixed file extensions in `create_medias` [PR#42](https://github.com/quality-match/hari-client/pull/42), [PR#54](https://github.com/quality-match/hari-client/pull/54)
- added scripts [PR#43](https://github.com/quality-match/hari-client/pull/43)
  - added script `create_subsets_from_attribute`
- added new client endpoint methods [PR#43](https://github.com/quality-match/hari-client/pull/43) [PR#56](https://github.com/quality-match/hari-client/pull/56)
  - get_attribute_metadata
  - get_visualisation_configs
- batch sizes for bulk uploads are configurable and the default for media upload was reduced to 30 [PR#50](https://github.com/quality-match/hari-client/pull/50)
  - see the `.env_example` for how to set the batch sizes with your .env file.
  - defaults:
    - media upload: 30 (was 500 previously)
    - media object upload: 500 (as before)
    - attribute upload: 500 (as before)
- instead of a single progressbar, the hari_uploader shows three separate ones [PR#50](https://github.com/quality-match/hari-client/pull/50)
  - media
  - media object
  - attributes
- added attribute validations to hari_uploader [PR#55](https://github.com/quality-match/hari-client/pull/55)
  - attribute value types have to be consistent
  - attributes with a list as value have to have a single consistent value type for their list elements
  - attributes with the same name and annotatable_type have to reuse the same attribute id

### Fixes

- correct typo in development installation guidelines [PR#43](https://github.com/quality-match/hari-client/pull/43)
- `query` argument of multiple methods is now serialized properly to fit the backend's implementation of a query parameter array [PR#49](https://github.com/quality-match/hari-client/pull/49)
  - get_medias
  - get_media_count
  - get_media_objects
  - get_media_object_count
  - get_attributes
  - get_attribute_metadata

### Internal

- introduced `any_response_type = str | int | float | list | dict | None` in models so that endpoints with response schema `any` can be parsed correctly [PR#43](https://github.com/quality-match/hari-client/pull/43)
- use `requests.Session` with retry strategy to upload medias in `_upload_media_files_with_presigned_urls` (used by the method `create_medias`) [#PR53](https://github.com/quality-match/hari-client/pull/53)

## [3.0.0] - 06.12.2024

### New Features

- added cant solve ratio to all attribute models. [PR#47](https://github.com/quality-match/hari-client/pull/47)

### Breaking Changes

- added repeats and possible values to all attribute models and methods.
  - these fields, as well as frequency and cant_solves are required for annotation attributes of type Binary and Categorical. [PR#47](https://github.com/quality-match/hari-client/pull/47) [PR#48](https://github.com/quality-match/hari-client/pull/48)

## [2.1.0] - 26.11.2024

### New Features

- added support for `anonymize` and `calculate_histograms` parameters to `trigger_metadata_rebuild_job` and `trigger_dataset_metadata_rebuild_job`
- added support for `force_recreate` flag for these methods:
  - `trigger_crops_creation_job`
  - `trigger_thumbnails_creation_job`
  - `trigger_dataset_metadata_rebuild_job`
  - `trigger_metadata_rebuild_job`

## [2.0.3] - 07.11.2024

### Fixes

- added support for serialization of `datetime` objects to the HARIClient. They're serialized to ISO-8601 strings now. [PR#38](https://github.com/quality-match/hari-client/pull/38)

## [2.0.2] - 30.10.2024

### Internal

- added `bulk_operation_annotatable_id` presence validation for bulk media/media objects creation models [PR#36](https://github.com/quality-match/hari-client/pull/36)

## [2.0.1] - 24.10.2024

### Internal

- updated create_subset endpoint used during object_category creation [PR#35](https://github.com/quality-match/hari-client/pull/35)

## [2.0.0] - 23.10.2024

### New Features

- added support for object categories [PR#26](https://github.com/quality-match/hari-client/pull/26)
- added support for attributes bulk upload with hari-uploader [PR#17](https://github.com/quality-match/hari-client/pull/17)
- added support for Attribute endpoints to client [PR#18](https://github.com/quality-match/hari-client/pull/18)

### Fixes

- fixed merge_bulk_responses for the case when no responses are given, therefore uploading media without media_objects isn't identified as an unsuccessful upload anymore [PR#20](https://github.com/quality-match/hari-client/pull/20)
- fixed bug updating media/annotatable ids for media objects and attributes when shared [PR#27](https://github.com/quality-match/hari-client/pull/27)

### Breaking Changes

- Object category field on MediaObjects enforced as UUID. [PR#29](https://github.com/quality-match/hari-client/pull/29)

### Internal

- updated occurrences of old type-hinting conventions (e.g. using pipe (`|`) instead of `typing.Optional` and `typing.Union`) [PR#19](https://github.com/quality-match/hari-client/pull/19)
- fixed some str/uuid inconsistencies for models [PR#19](https://github.com/quality-match/hari-client/pull/19)
- updated media object source to be optional defaulting to `REFERENCE` during media object(s) creation [PR#24](https://github.com/quality-match/hari-client/pull/24)

## [1.0.0] - 27.09.2024

### New Features

- added support for media and media object bulk creation endpoints [PR#2](https://github.com/quality-match/hari-client/pull/2)
- added support for processingJobs endpoints [PR#3](https://github.com/quality-match/hari-client/pull/3)
- added new hari_uploader interface to simplify the usage of the media and media object creation endpoints [PR#7](https://github.com/quality-match/hari-client/pull/7)
- added support for new metadata rebuild endpoints. One method is enough to trigger all necessary metadata update prcessing jobs [PR#15](https://github.com/quality-match/hari-client/pull/15)

### Updates

- update create_subset method: added args `filter_options` and `secondary_filter_options` [PR#14](https://github.com/quality-match/hari-client/pull/14)
- updated all API models to keep extra fields in the parsed models by using [pydantic model config setting `extra="allow"`](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.extra) [PR#14](https://github.com/quality-match/hari-client/pull/14)
  - this means that if the backend responds with new fields, the response parser doesn't break and the fields that are unknown to the hari-client will still be accessible
- updated the quickstart example code to use the new hari_uploader interface and the new metadata rebuild endpoint [PR#15](https://github.com/quality-match/hari-client/pull/15)

### Breaking Changes

- changed HARIClient metadata processing job creation method names to be more descriptive [PR#6](https://github.com/quality-match/hari-client/pull/6)
  - create_thumbnails --> trigger_thumbnails_creation_job
  - update_histograms --> trigger_histograms_update_job
  - create_crops --> trigger_crops_creation_job
- Renamed field `customer` of Dataset model and create_dataset endpoint to `user_group` [PR#15](https://github.com/quality-match/hari-client/pull/15)

### Internal

- updated response parser logic to behave more consistently. If you expect a list from the endpoint, you have to specify the response type as a list as well: `list[MyModel]` [PR#14](https://github.com/quality-match/hari-client/pull/14)
  - previously specifying `MyModel` as response type could've still resulted in parsing the response data to `list[MyModel]` even though this wasn't specified as the expected response type.
- added new error classes: `ParameterNumberRangeError` and `ParameterListLengthError` [PR#15](https://github.com/quality-match/hari-client/pull/15)

## [0.2.0] - 2024-08-23

### Fixes

- added response types for metadata creation endpoints [PR#1](https://github.com/quality-match/hari-client/pull/1)

### Breaking Changes

- update minimum python version to be 3.11 [PR#4](https://github.com/quality-match/hari-client/pull/4)

### Internal

- updated generic parser to work with list of parametrized generics [PR#1](https://github.com/quality-match/hari-client/pull/1)

## [0.1.0] - 2024-07-25

Initial Release of hari-client with version 0.1.0
