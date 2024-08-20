from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

config = Config()
client = HARIClient(config)

# setup hari uploader
uploader = hari_uploader.HARIUploader(client=client, dataset_id="CHANGEME")

# setup medias and all of its media objects
media_1 = hari_uploader.HARIMedia(
    file_path="busy_street.jpg",
    back_reference="img 1 - backref",
    name="my image 1",
    media_type=models.MediaType.IMAGE,
)
media_1.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img 1 obj 1 - backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1600.0,
            y=2106.0,
            width=344.0,
            height=732.0,
        ),
    )
)
media_1.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img 1 obj 2 - backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1600.0,
            y=2106.0,
            width=344.0,
            height=732.0,
        ),
    )
)

# make the media known to the uploader
uploader.add_media(media_1)

media_2 = hari_uploader.HARIMedia(
    file_path="busy_street.jpg",
    back_reference="img 2 - backref",
    name="my image 2",
    media_type=models.MediaType.IMAGE,
)
media_2.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img 2 obj 1 - backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1600.0,
            y=2106.0,
            width=344.0,
            height=732.0,
        ),
    )
)
uploader.add_media(media_2)

media_3 = hari_uploader.HARIMedia(
    file_path="busy_street.jpg",
    back_reference="img 3 - backref",
    name="my image 3",
    media_type=models.MediaType.IMAGE,
)
media_3.add_media_object(
    hari_uploader.HARIMediaObject(
        source=models.DataSource.REFERENCE,
        back_reference="img 3 obj 1 - backref",
        reference_data=models.BBox2DCenterPoint(
            type=models.BBox2DType.BBOX2D_CENTER_POINT,
            x=1800.0,
            y=2206.0,
            width=100.0,
            height=300.0,
        ),
    )
)
uploader.add_media(media_3)

# trigger upload
upload_results = uploader.upload()

# inspect upload results
print(f"media upload status: {upload_results.medias.status}")
print(f"media upload summary\n  {upload_results.medias.summary}")
if upload_results.medias.status != models.BulkOperationStatusEnum.SUCCESS:
    print(upload_results.medias.results)

print(f"media_object upload status: {upload_results.media_objects.status}")
print(f"media object upload summary\n  {upload_results.media_objects.summary}")
if upload_results.media_objects.status != models.BulkOperationStatusEnum.SUCCESS:
    print(upload_results.media_objects.results)
