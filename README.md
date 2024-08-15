# hari-client

**hari-client** is the official open source API client package for [HARI (Highly Actionable Real-Time Insights)](https://www.quality-match.com/product) by Quality Match GmbH. This package allows you to interact with the HARI backend, enabling you to create datasets and upload your data with ease.

## Installation

Minimum python version: **3.11**

To install the hari-client package, use pip with the following command:

```bash
python -m pip install "hari_client @ git+https://github.com/quality-match/hari-client@v0.1.0"
```

## Quickstart

Here's a quick example of how to use the HARI Client to create a dataset and upload data and annotations.
You can find the referenced image here: `docs/example_code/busy_street.jpg`.
Every run of this script creates a new dataset.

```python
# docs/example_code/quickstart.py
# run from docs/example_code

from hari_client import Config
from hari_client import HARIClient
from hari_client import models

# Replace by your own credentials!
config = Config(hari_username="jane.doe@gmail.com", hari_password="SuperSecretPassword")

if __name__ == "__main__":
    # 1. Initialize the HARI client
    hari = HARIClient(config=config)

    # 2. Create a dataset
    # Replace "CHANGEME" with you own user group!
    user_group = "CHANGEME"
    new_dataset = hari.create_dataset(name="My first dataset", customer=user_group)
    print("Dataset created with id:", new_dataset.id)

    # 3. Upload an image
    file_path = "busy_street.jpg"
    new_media = hari.create_media(
        dataset_id=new_dataset.id,
        file_path=file_path,
        name="A busy street",
        media_type=models.MediaType.IMAGE,
        back_reference=file_path,
    )
    print("New media created with id: ", new_media.id)

    # 4. Create a geometry on the image
    geometry = models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1600.0,
        y=2106.0,
        width=344.0,
        height=732.0,
    )
    new_media_object = hari.create_media_object(
        dataset_id=new_dataset.id,
        media_id=new_media.id,
        back_reference="Pedestrian-1",
        source=models.DataSource.REFERENCE,
        reference_data=geometry,
    )
    print("New media object created with id:", new_media_object.id)

    # 5. Create a subset
    new_subset_id = hari.create_subset(
        dataset_id=new_dataset.id,
        subset_type=models.SubsetType.MEDIA_OBJECT,
        subset_name="All media objects",
    )
    print(f"Created new subset with id {new_subset_id}")

    # 6. Update metadata
    print("Triggering metadata updates...")
    hari.create_thumbnails(new_dataset.id, new_subset_id)
    hari.update_histograms(new_dataset.id, compute_for_all_subsets=True)
    # The create_crops method requires the thumbnail creation to be finished.
    # If it fails, try only this method again after a few minutes.
    hari.create_crops(dataset_id=new_dataset.id, subset_id=new_subset_id)
```

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
