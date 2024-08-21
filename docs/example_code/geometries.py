from hari_client import Config
from hari_client import HARIClient
from hari_client import models

# Replace by your own credentials!
config = Config(hari_username="jane.doe@gmail.com", hari_password="SuperSecretPassword")


if __name__ == "__main__":
    # 1. Initialize the HARI client & dataset and media that we want to work with
    hari = HARIClient(config=config)

    # Replace by your own dataset_id and media_id!
    dataset_id = "MY_DATASET_ID"
    media_id = "MY_MEDIA_ID"

    # 2. Create a bounding box
    bb = models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=1600.0,
        y=2106.0,
        width=344.0,
        height=732.0,
    )
    bb_media_object = hari.create_media_object(
        dataset_id=dataset_id,
        media_id=media_id,
        back_reference="Pedestrian-1",
        source=models.DataSource.REFERENCE,
        reference_data=bb,
    )
    print("New bounding box created with id:", bb_media_object.id)

    # 3. Create a keypoint
    keypoint = models.Point2DXY(x=1652.0, y=1780.0)
    keypoint_media_object = hari.create_media_object(
        dataset_id=dataset_id,
        media_id=media_id,
        back_reference="Pedestrian's head",
        source=models.DataSource.REFERENCE,
        reference_data=keypoint,
    )
    print("New keypoint created with id:", keypoint_media_object.id)

    # 4. Create a polyline
    polyline = models.PolyLine2DFlatCoordinates(
        coordinates=[1836, 2636, 1768, 2144, 1756, 1924, 1884, 1860], closed=False
    )
    polyline_media_object = hari.create_media_object(
        dataset_id=dataset_id,
        media_id=media_id,
        back_reference="Direction of the street",
        source=models.DataSource.REFERENCE,
        reference_data=polyline,
    )
    print("New polyline created with id:", polyline_media_object.id)

    # 5. Create a polygon
    polygon = models.PolyLine2DFlatCoordinates(
        coordinates=[
            0,
            3456,
            0,
            2756,
            152,
            1904,
            404,
            1800,
            1188,
            1780,
            1376,
            2004,
            1492,
            2940,
            1464,
            3456,
        ],
        closed=True,
    )
    polygon_media_object = hari.create_media_object(
        dataset_id=dataset_id,
        media_id=media_id,
        back_reference="Riders on a scooter",
        source=models.DataSource.REFERENCE,
        reference_data=polygon,
    )
    print("New polygon created with id:", polygon_media_object.id)

    # 6. Create a subset & Update metadata
    new_subset_id = hari.create_subset(
        dataset_id=dataset_id,
        subset_type=models.SubsetType.MEDIA_OBJECT,
        subset_name="All geometries",
    )
    hari.trigger_thumbnails_creation_job(dataset_id, new_subset_id)
    hari.trigger_histograms_update_job(dataset_id, compute_for_all_subsets=True)
    hari.trigger_crops_creation_job(dataset_id=dataset_id, subset_id=new_subset_id)
