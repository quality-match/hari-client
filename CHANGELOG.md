## TBD - TBD

### New Features

- added response types for metadata creation endpoints [PR#1](https://github.com/quality-match/hari-client/pull/1)
- added support for media and media object bulk creation endpoints [PR#2](https://github.com/quality-match/hari-client/pull/2)
- added support for processingJobs endpoints [PR#3](https://github.com/quality-match/hari-client/pull/3)
- added new hari_uploader interface to simplify the usage of the media and media object creation endpoints [PR#7](https://github.com/quality-match/hari-client/pull/7)

### Internal

- updated generic parser to work with list of parametrized generics [PR#1](https://github.com/quality-match/hari-client/pull/1)

### Breaking Changes

- update minimum python version to be 3.11 [PR#4](https://github.com/quality-match/hari-client/pull/4)
- changed HARIClient metadata processing job creation method names to be more descriptive [PR#6](https://github.com/quality-match/hari-client/pull/6)
  - create_thumbnails --> trigger_thumbnails_creation_job
  - update_histograms --> trigger_histograms_update_job
  - create_crops --> trigger_crops_creation_job

## [0.1.0] - 2024-07-25

Initial Release of hari-client with version 0.1.0
