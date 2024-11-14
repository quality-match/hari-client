## [major.minor.patch] - DD-MM-YYYY

## [2.2.0] - 14.11.2024

### New Features

- added support for `anonymize` and `calculate_histograms` parameters to `trigger_metadata_rebuild_job` and `trigger_dataset_metadata_rebuild_job`

## [2.1.0] - 11.11.2024

### New Features

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
