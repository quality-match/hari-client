import json
import pathlib
import sys
import time
import uuid

from hari_client import Config
from hari_client import hari_uploader
from hari_client import HARIClient
from hari_client import models


def load_local_3d_dataset() -> tuple[list[hari_uploader.HARIMedia], set[str], set[str]]:
    """
    This functions loads the 3d example dataset from the `3d_dataset` directory and is built to this specific dataset's requirements.
    The dataset doesn't follow any specific common directory structure.
    It follows the HARI 3D conventions, though, so no further transformations are required to make it compatible with HARI.
    You can find the description of the HARI 3D conventions and requirements in the HARI documentation:
        - https://docs.quality-match.com/hari_client/3d_data_requirements/#hari-3d-conventions-and-requirements

    Dataset structure:
        - The dataset contains 3 frames, each with 4 cameras and a point cloud.
        - Each camera has a corresponding image file, and the point cloud is stored in a PCD file.
        - The cameras' extrinsics and intrinsics, as well as the objects in the scene, are stored in a JSON file.

    In order to load your own dataset, you have to adapt the data loading to your own dataset requirements,
    directory structure and apply the necessary transformations to make it compatible with the HARI 3D conventions.

    Returns:
        A list of HARIMedia representing all data of the dataset, a set of scene names, a set of object categories.
    """
    base_dir = pathlib.Path(__file__).parent / "3d_dataset"
    # we know that the dataset consists of only one scene, 3 frames and 4 cameras
    frame_indices = [0, 1, 2]
    camera_names = ["Camera_Front", "Camera_Back", "Camera_Right", "Camera_Left"]
    # there's only one scene in this example dataset, so we use a static scene name
    scene_name = "scene_0"

    medias = []
    scene_names = set([scene_name])
    object_categories = set()

    for frame_idx in frame_indices:
        frame_dir = base_dir / f"frame_{frame_idx}"
        data_filename = frame_dir / f"data_{frame_idx}.json"
        pointcloud_filename = frame_dir / f"pointcloud_{frame_idx}.pcd"

        # Load data: camera extrinsics, camera intrinsics, objects
        with open(data_filename, "r") as f:
            frame_data = json.load(f)

        cameras = frame_data["cameras"]
        objects = frame_data["objects"]

        # Create HARIMedia for every camera image
        for camera_name in camera_names:
            camera = cameras[camera_name]
            image_name = f"{camera_name}_{frame_idx}.jpg"
            medias.append(
                hari_uploader.HARIMedia(
                    file_path=str(frame_dir / image_name),
                    name=image_name,
                    back_reference=image_name,
                    frame_idx=frame_idx,
                    scene_back_reference=scene_name,
                    media_type=models.MediaType.IMAGE,
                    metadata=models.ImageMetadata(
                        sensor_id=camera_name,
                        camera_intrinsics=models.CameraIntrinsics(
                            camera_model=models.CameraModelType.PINHOLE,
                            focal_length=(camera["fx"], camera["fy"]),
                            principal_point=(camera["cx"], camera["cy"]),
                            # we know that all images are 1920x1080, so we can set these values directly
                            width_px=1920,
                            height_px=1080,
                            distortion_coefficients=None,
                        ),
                        camera_extrinsics=models.Pose3D(
                            position=camera["location"],
                            heading=camera["rotation_quaternion_wxyz"],
                        ),
                        width=1920,
                        height=1080,
                    ),
                )
            )

        # Create HARIMedia for the pointcloud
        pointcloud_media = hari_uploader.HARIMedia(
            file_path=str(pointcloud_filename),
            name=f"pointcloud_{frame_idx}.pcd",
            back_reference=f"pointcloud_{frame_idx}",
            frame_idx=frame_idx,
            scene_back_reference=scene_name,
            media_type=models.MediaType.POINT_CLOUD,
            metadata=models.PointCloudMetadata(
                sensor_id="lidar_sensor",
            ),
        )
        medias.append(pointcloud_media)

        # Create HARIMediaObjects for each object in the frame
        for object_name, object in objects.items():
            media_object = hari_uploader.HARIMediaObject(
                scene_back_reference=scene_name,
                frame_idx=frame_idx,
                # in this dataset, the object names aren't unique across frames, so append the frame_idx to
                # make the back_reference unique
                back_reference=f"{object_name}_{frame_idx}",
                reference_data=models.CuboidCenterPoint(
                    type="cuboid_center_point",
                    position=object["location"],
                    dimensions=object["dimensions"],
                    heading=object["rotation_quaternion_wxyz"],
                ),
            )
            media_object.set_object_category_subset_name(object["class"])
            object_categories.add(object["class"])
            pointcloud_media.add_media_object(media_object)

    return medias, scene_names, object_categories


# The Config class will look for a .env file in your script's current working directory.
# Copy the .env_example file as .env for that and store your HARI credentials in there.
config = Config()

# 0. Load the local 3D dataset
medias, scene_names, object_categories = load_local_3d_dataset()

# 1. Initialize the HARI client
hari = HARIClient(config=config)

# 2. Create a dataset
# Replace "CHANGEME" with your own user group!
new_dataset = hari.create_dataset(name="My first 3D dataset", user_group="CHANGEME")
print("Dataset created with id:", new_dataset.id)
dataset_id = new_dataset.id

# 3. Set up hari uploader
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    scenes=scene_names,
    object_categories=object_categories,
)
uploader.add_media(*medias)

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
    print(f"media upload failures\n  {upload_results.failures.failed_medias}")

    print(f"media objects upload details: {upload_results.media_objects.results}")
    print(
        f"media object upload failures\n  {upload_results.failures.failed_media_objects}"
    )

    print(f"attributes upload details: {upload_results.attributes.results}")
    print(
        f"media-attribute upload failures\n  {upload_results.failures.failed_media_attributes}"
    )
    print(
        f"media object-attribute upload failures\n  {upload_results.failures.failed_media_object_attributes}"
    )
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
    dataset_id=dataset_id,
    trace_id=metadata_rebuild_trace_id,
    compute_auto_attributes=True,
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
