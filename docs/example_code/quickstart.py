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
