# hari-client

**hari-client** is the official open source API client package for [HARI (Highly Actionable Real-Time Insights)](https://www.quality-match.com/product)
by Quality Match GmbH. This package allows you to interact with the HARI backend, enabling you to create datasets
and upload your data with ease.

## Installation

Minimum python version: **3.11**

To install the hari-client package, use pip with the following command:

```bash
python -m pip install "hari_client @ git+https://github.com/quality-match/hari-client@v6.0.0"
```

## Quickstart

You can use the [quick start script](docs/example_code/quickstart.py) as basis for your development.
It's an example of how to use hari-client to create a dataset and upload images and annotations.
Every run of this script creates a new dataset.
You can find the referenced images here: `docs/example_code/images/`.
Copy the `docs/example_code/.env_example` file to `docs/example_code/.env` and fill in your HARI credentials there.
Run the script from the `docs/example_code` directory.

## Configuration

This section describes the available configuration options for the hari-client.
You can find all available environment variables in the `docs/example_code/.env_example` file.
The optional environment variables are commented out.

### Required

To be able to use the hari-client, you need to provide your HARI credentials:

- `HARI_USERNAME`
- `HARI_PASSWORD`

### HARI Uploader configuration

#### Upload batch sizes

You can configure the bath size that's used to upload medias, media objects and attributes.
If you're experiencing timeout problems, we recommend reducing the media upload batch size.

- `HARI_UPLOADER__MEDIA_UPLOAD_BATCH_SIZE`
- `HARI_UPLOADER__MEDIA_OBJECT_UPLOAD_BATCH_SIZE`
- `HARI_UPLOADER__ATTRIBUTE_UPLOAD_BATCH_SIZE`

## Documentation

For more detailed documentation, including all available methods and their parameters, please refer to the official documentation https://docs.quality-match.com.

## Scripts

We provide in the folder `scripts` a collection of common use-cases for which the HARI client can be used.
Please check here before you implement your on script since we might have you already covered.

DISCLAIMER: This section is currently in development and is extended regularly.
DISCLAIMER: The scripts are currently not quality controlled and thus may include deprecated code.

## Changelog

See: [CHANGELOG.md](CHANGELOG.md)

## Development Setup

To set up your local development environment, follow these steps:

- Clone the repository
- Setup a virtual environment with Python 3.11
- Install the package in editable mode with the following command:
  ```bash
  python -m pip install -e '.[dev]'
  ```
  - This also installs pytest and the [pre-commit](https://github.com/pre-commit/pre-commit) tool into the environment
- Install the pre-commit hooks with the following command:
  ```bash
  pre-commit install
  ```

## Release guide

To create a new release, follow these steps:
1. Ensure the branch has the state you want to release. This means all tests and pre-commit hooks pass,
and the changelog is up to date. Changelog entry should have a new release version and date.

2. With the branch in a clean state, run bumpversion to update the version number:
   ```bash
   bumpversion [patch|minor|major]
   ```
depending on the type of release you want to create.
This will also update the version in the setup and readme files,
and create a new git tag with the version number.

3. Create a pull request with the changes to the main branch and merge it after approval.

4. Push the tag to the remote repository:
   ```bash
   git push --tags
   ```

Now the new version is available on the GitHub repository.
After that, the new installation link on the [documentation website](https://docs.quality-match.com/hari_client/installation/#installation) could be updated as well.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

Visit our website https://quality-match.com
