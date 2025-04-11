import sys
import time
import uuid

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models

# The Config class will look for a .env file in your script's current working directory.
# Copy the .env_example file as .env for that and store your HARI credentials in there.
config = Config()

# 1. Initialize the HARI client
hari = HARIClient(config=config)
# # 2. Create a dataset
# # Replace "CHANGEME" with your own user group!
new_dataset = hari.create_dataset(name="My first dataset")
print("Dataset created with id:", new_dataset.id)
#
dataset_id = new_dataset.id

attribute_object_1_id = uuid.uuid4()
attribute_media_1_id = uuid.uuid4()
medias = []

# 3. Set up your medias and all of their media objects and attributes.
# In this example we use 3 images with 1 media object each.
# The first media and media object have 1 attribute each.
scenes = {"scene1"}
object_categories = {"truck"}
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    scenes=scenes,
    object_categories=object_categories,
)
point_cloud = hari_uploader.HARIMedia(
    file_path="images/point_cloud.pcd",
    name="test_point_cloud",
    back_reference="point_cloud",
    frame_idx=0,
    scene_name="scene1",
    media_type=models.MediaType.POINT_CLOUD,
    metadata=models.PointCloudMetadata(
        sensor_id="lidar_sensor_1",
        lidar_sensor_pose={
            "test": models.Pose3D(heading=(0, 0, 0, 0), position=(0, 0, 0))
        },
    ),
)
media_object = hari_uploader.HARIMediaObject(
    back_reference="cuboid_center_point",
    reference_data=models.CuboidCenterPoint(
        type="cuboid_center_point",
        position=[-10.227567047441426, 19.460821128585394, 0.03743642453830098],
        dimensions=[2.312, 7.516, 3.093],
        heading=[
            0.9543446154177624,
            0.0016914195330597179,
            -0.0028850132191384366,
            -0.29868908721580645,
        ],
    ),
    scene_name="scene1",
    frame_idx=0,
)
media_object.set_object_category_subset_name("truck")
point_cloud.add_media_object(media_object)
image = hari_uploader.HARIMedia(
    file_path="images/acdcf2c4-9585-4c9c-90bb-cfa0883898f4.jpg",
    name="test_image_1",
    back_reference="test_image_1",
    frame_idx=0,
    scene_name="scene1",
    metadata=models.ImageMetadata(
        camera_intrinsics=models.CameraIntrinsics(
            camera_model=models.CameraModelType.PINHOLE,
            focal_length=(1266.417203046554, 1266.417203046554),
            principal_point=(816.2670197447984, 491.50706579294757),
            width_px=1600,
            height_px=900,
            distortion_coefficients=None,
        ),
        camera_extrinsics=models.Pose3D(
            position=(-0.012463384576629074, 0.76486688894964, -0.3109103442096659),
            heading=(
                0.713640516187247,
                -0.700501707318727,
                -0.0036449450274057653,
                -0.0011340525982261474,
            ),
        ),
        width=1600,
        height=900,
    ),
    media_type=models.MediaType.IMAGE,
)

uploader.add_media(image)
uploader.add_media(point_cloud)

# 4. Trigger the upload process
upload_results = uploader.upload()

# Inspect upload results
print(f"media upload status: {upload_results.medias.status.value}")
print(f"media upload summary\n  {upload_results.medias.summary}")

print(f"media object upload status: {upload_results.media_objects.status.value}")
print(f"media object upload summary\n  {upload_results.media_objects.summary}")

print(f"attribute upload status: {upload_results.attributes.status.value}")
print(f"attribute upload summary\n  {upload_results.attributes.summary}")

if (
    upload_results.medias.status != models.BulkOperationStatusEnum.SUCCESS
    or upload_results.media_objects.status != models.BulkOperationStatusEnum.SUCCESS
    or upload_results.attributes.status != models.BulkOperationStatusEnum.SUCCESS
):
    print(
        "The data upload wasn't fully successful. Subset and metadata creation are skipped. See the details below."
    )
    print(f"media upload details: {upload_results.medias.results}")
    print(f"media objects upload details: {upload_results.media_objects.results}")
    print(f"attributes upload details: {upload_results.attributes.results}")
    sys.exit(1)

# 5. Create a subset
print("Creating new subset...")
new_subset_id = hari.create_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="All media objects",
)
print(f"Created new subset with id {new_subset_id}")

# 6. Trigger metadata updates
print("Triggering metadata updates...")
# create a trace_id to track triggered metadata update jobs
metadata_rebuild_trace_id = uuid.uuid4()
print(f"metadata_rebuild jobs trace_id: {metadata_rebuild_trace_id}")
metadata_rebuild_jobs = hari.trigger_dataset_metadata_rebuild_job(
    dataset_id=dataset_id, trace_id=metadata_rebuild_trace_id
)

# track the status of all metadata rebuild jobs and wait for them to finish
job_statuses = []
jobs_are_still_running = True
while jobs_are_still_running:
    jobs = hari.get_processing_jobs(trace_id=metadata_rebuild_trace_id)
    job_statuses = [(job.process_name, job.status.value, job.id) for job in jobs]

    jobs_are_still_running = any(
        [
            status[1]
            in [models.ProcessingJobStatus.CREATED, models.ProcessingJobStatus.RUNNING]
            for status in job_statuses
        ]
    )
    if jobs_are_still_running:
        print(f"waiting for metadata_rebuild jobs to finish, {job_statuses=}")
        time.sleep(10)

print(f"metadata_rebuild jobs finished with status {job_statuses=}")
