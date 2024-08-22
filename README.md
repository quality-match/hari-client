# hari-client

**hari-client** is the official open source API client package for [HARI (Highly Actionable Real-Time Insights)](https://www.quality-match.com/product) by Quality Match GmbH. This package allows you to interact with the HARI backend, enabling you to create datasets and upload your data with ease.

## Installation

Minimum python version: **3.11**

To install the hari-client package, use pip with the following command:

```bash
python -m pip install "hari_client @ git+https://github.com/quality-match/hari-client@v0.1.0"
```

## Quickstart

You can use the [quick start script](docs/example_code/quickstart.py) as basis for your development.
It's an example of how to use hari-client to create a dataset and upload images and annotations.
Every run of this script creates a new dataset.
You can find the referenced images here: `docs/example_code/images/`.
Copy the `docs/example_code/.env_example` file to `docs/example_code/.env` and fill in your HARI credentials there.
Run the script from the `docs/example_code` directory.

### Other annotation geometries

Have a look at the [geometries.py](docs/example_code/geometries.py) example script for examples on how to create other annotation geometries.

## Documentation

For more detailed documentation, including all available methods and their parameters, please refer to the official documentation https://docs.quality-match.com.

## Changelog

See: [CHANGELOG.md](CHANGELOG.md)

## Development Setup

To set up your local development environment, follow these steps:

- Clone the repository
- Setup a virtual environment with Python 3.11
- Install the package in editable mode with the following command:
  ```bash
  python -m pip install -e .[tests]
  ```
  - This also installs pytest and the [pre-commit](https://github.com/pre-commit/pre-commit) tool into the environment
- Install the pre-commit hooks with the following command:
  ```bash
  pre-commit install
  ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

Visit our website https://quality-match.com

```

```
