from hari_client import Config
from hari_client import HARIClient
from hari_client import models

# Replace by your own credentials!
config = Config(hari_username="jane.doe@gmail.com", hari_password="SuperSecretPassword")


class ExampleMediaAndObject:
    def __init__(
        self, media: models.MediaCreate, media_object: models.MediaObjectCreate
    ):
        self.media = media
        self.media_object = media_object


def get_example_medias_and_objects() -> list[ExampleMediaAndObject]:
    return [
        ExampleMediaAndObject(
            media=models.MediaCreate(
                file_path="images/image1.jpg",
                name="A busy street 1",
                back_reference="image 1",
                media_type=models.MediaType.IMAGE,
            ),
            media_object=models.MediaObjectCreate(
                media_id="",  # will be filled in when corresponding media is created
                source=models.DataSource.REFERENCE,
                back_reference="pedestrian",
                reference_data=models.BBox2DCenterPoint(
                    type=models.BBox2DType.BBOX2D_CENTER_POINT,
                    x=1400.0,
                    y=1806.0,
                    width=344.0,
                    height=732.0,
                ),
            ),
        ),
        ExampleMediaAndObject(
            media=models.MediaCreate(
                file_path="images/image2.jpg",
                name="A busy street 2",
                back_reference="image 2",
                media_type=models.MediaType.IMAGE,
            ),
            media_object=models.MediaObjectCreate(
                media_id="",  # will be filled in when corresponding media is created
                source=models.DataSource.REFERENCE,
                back_reference="motorcycle wheel",
                media_type=models.MediaType.IMAGE,
                reference_data=models.Point2DXY(x=975.0, y=2900.0),
            ),
        ),
        ExampleMediaAndObject(
            media=models.MediaCreate(
                file_path="images/image3.jpg",
                name="A busy street 3",
                back_reference="image 3",
                media_type=models.MediaType.IMAGE,
            ),
            media_object=models.MediaObjectCreate(
                media_id="",  # will be filled in when corresponding media is created
                source=models.DataSource.REFERENCE,
                back_reference="road marking",
                media_type=models.MediaType.IMAGE,
                reference_data=models.PolyLine2DFlatCoordinates(
                    coordinates=[1450, 1550, 1450, 1000],
                    closed=False,
                ),
            ),
        ),
    ]


if __name__ == "__main__":
    # 1. Initialize the HARI client
    hari = HARIClient(config=config)

    # 2. Create a dataset
    # Replace "CHANGEME" with you own user group!
    user_group = "CHANGEME"
    new_dataset = hari.create_dataset(name="My first dataset", customer=user_group)
    print("Dataset created with id:", new_dataset.id)

    # create example medias and media objects
    example_medias_and_objects_list = get_example_medias_and_objects()
    medias = [example.media for example in example_medias_and_objects_list]
    media_objects = [
        example.media_object for example in example_medias_and_objects_list
    ]

    # 3. Create medias
    create_medias_response = hari.create_medias(new_dataset.id, medias)
    print(
        f"Create medias status={create_medias_response.status.value}, summary={create_medias_response.summary}"
    )

    # 4. Create media objects
    # update media_id with created media id for each media object
    for i, media_object in enumerate(media_objects):
        media_objects[i].media_id = create_medias_response.results[i].item_id

    create_media_objects_response = hari.create_media_objects(
        new_dataset.id, media_objects
    )
    print(
        f"Create media objects status={create_media_objects_response.status.value}, summary={create_media_objects_response.summary}"
    )

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
    print("Metadata successfully updated")
