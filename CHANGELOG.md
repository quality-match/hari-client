## [major.minor.patch] - DD-MM-YYYY

## [3.3.0] - DD-MM-YYYY

### New features

#### Support for external media sources

- added support for defining external media sources when creating a dataset
  - new field `external_media_source` in the `create_dataset` method [PR#73](https://github.com/quality-match/hari-client/pull/73)
- added new endpoint `get_external_media_source` [PR#73](https://github.com/quality-match/hari-client/pull/73)
- added new arg to client method `create_medias` [PR#74](https://github.com/quality-match/hari-client/pull/74)
  - `with_media_file_upload` (default: `True`). Set this to `False` if you want to skip the upload of media files.
  - the method will then only send the `BulkMediaCreate` instance to HARI.
- added format validations for `HARIMedia` field `media_url` [PR#74](https://github.com/quality-match/hari-client/pull/74)
  - the field was previously set automatically through the process of uploading media files.
  - in order to work with a dataset that uses an external media source, you have to set the field explicitly.
- updated usage of HARIUploader utility [PR#74](https://github.com/quality-match/hari-client/pull/74)
  - when using an external media source, make sure to only set the `media_url` field of a `HARIMedia` and don't set the `file_path`.
  - if all medias have a set `media_url` field, then media files will not be uploaded to HARI, but they're only setup with the api.
  - if all medias have a set `file_path` field, then the uploader utility behaves as before and will upload media files to HARI.

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
