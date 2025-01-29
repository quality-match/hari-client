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

# 2. Create a dataset
# Replace "CHANGEME" with your own user group!
dataset_id = "fdc5d0fb-cfa1-47f8-b1a4-5816ccb0f1b8"
new_dataset = hari.create_dataset(
    name="azure test 0",
    user_group="QM-devs",
    external_media_source=models.ExternalMediaSourceAPICreate(
        credentials=models.ExternalMediaSourceAzureCredentials(
            account_name="faboi",
            container_name="test-faboi",
            sas_token="sp=r&st=2025-02-27T13:27:27Z&se=2025-03-07T21:27:27Z&spr=https&sv=2022-11-02&sr=c&sig=EQr%2FyLih5pz%2Fub406JL1FsqdLAfDJsZGZP0xGfQVM7E%3D",
        ),
    ),
)
print("Dataset created with id:", new_dataset.id)

dataset_id = new_dataset.id

# 3. Set up your medias and all of their media objects and attributes.
# In this example we use 3 images with 1 media object each.
# The first media and media object have 1 attribute each.
weather_condition_id = (
    uuid.uuid4()
)  # Generate once and reuse for all weather_condition attributes
is_walking_id = uuid.uuid4()  # Generate once and reuse for all is_walking attributes
is_moving_id = uuid.uuid4()  # Generate once and reuse for all is_moving attributes
is_parked_id = uuid.uuid4()  # Generate once and reuse for all is_parked attributes

# Original media entries
media_1 = hari_uploader.HARIMedia(
    # note: the file_path won't be saved in HARI, it's only used during uploading
    file_key="Images/ecp1.png",
    name="A busy street 1",
    back_reference="image 1",
    media_type=models.MediaType.IMAGE,
)
media_object_1 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=400.0,
        y=806.0,
        width=344.0,
        height=232.0,
    ),
)
attribute_object_1 = hari_uploader.HARIAttribute(
    id=is_walking_id,  # Reuse the same ID for all is_walking attributes
    name="is_walking",
    value=True,
)

attribute_media_1 = hari_uploader.HARIAttribute(
    id=weather_condition_id,  # Reuse the same ID for all weather_condition attributes
    name="weather_condition",
    value="sunny",
)
media_1.add_attribute(attribute_media_1)
media_object_1.add_attribute(attribute_object_1)
media_object_1.set_object_category_subset_name("pedestrian")
media_1.add_media_object(media_object_1)

media_2 = hari_uploader.HARIMedia(
    file_key="Images/ecp12.png",
    name="A busy street 2",
    back_reference="image 2",
    media_type=models.MediaType.IMAGE,
)
media_object_2 = hari_uploader.HARIMediaObject(
    back_reference="motorcycle_wheel_1",
    reference_data=models.Point2DXY(x=375.0, y=700.0),
)
media_object_2.set_object_category_subset_name("wheel")
media_2.add_media_object(media_object_2)

media_3 = hari_uploader.HARIMedia(
    file_key="Images/ecp15.png",
    name="A busy street 3",
    back_reference="image 3",
    media_type=models.MediaType.IMAGE,
)
media_object_3 = hari_uploader.HARIMediaObject(
    back_reference="road marking",
    reference_data=models.PolyLine2DFlatCoordinates(
        coordinates=[450, 550, 450, 300],
        closed=False,
    ),
)
media_object_3.set_object_category_subset_name("road_marking")
media_3.add_media_object(media_object_3)

media_4 = hari_uploader.HARIMedia(
    file_key="Images/ecp18.png",
    name="A busy street 4",
    back_reference="image 4",
    media_type=models.MediaType.IMAGE,
)
media_object_4 = hari_uploader.HARIMediaObject(
    back_reference="road marking",
    reference_data=models.PolyLine2DFlatCoordinates(
        coordinates=[450, 550, 450, 300],
        closed=False,
    ),
)
media_object_4.set_object_category_subset_name("road_marking")
media_4.add_media_object(media_object_4)

media_5 = hari_uploader.HARIMedia(
    file_key="Images/ecp20.png",
    name="A busy street 5",
    back_reference="image 5",
    media_type=models.MediaType.IMAGE,
)
media_object_5 = hari_uploader.HARIMediaObject(
    back_reference="motorcycle_wheel_1",
    reference_data=models.Point2DXY(x=375.0, y=700.0),
)
media_object_5.set_object_category_subset_name("wheel")
media_5.add_media_object(media_object_5)

media_6 = hari_uploader.HARIMedia(
    # note: the file_path won't be saved in HARI, it's only used during uploading
    file_key="Images/ecp5.png",
    name="A busy street 6",
    back_reference="image 6",
    media_type=models.MediaType.IMAGE,
)
media_object_6 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=400.0,
        y=806.0,
        width=344.0,
        height=232.0,
    ),
)
attribute_object_6 = hari_uploader.HARIAttribute(
    id=is_walking_id,  # Reuse the same ID for all is_walking attributes
    name="is_walking",
    value=True,
)

attribute_media_6 = hari_uploader.HARIAttribute(
    id=weather_condition_id,  # Reuse the same ID for all weather_condition attributes
    name="weather_condition",
    value="sunny",
)
media_6.add_attribute(attribute_media_6)
media_object_6.add_attribute(attribute_object_6)
media_object_6.set_object_category_subset_name("pedestrian")
media_6.add_media_object(media_object_6)

# Additional images with media objects
media_7 = hari_uploader.HARIMedia(
    file_key="Images/ecp8.png",
    name="A busy street 7",
    back_reference="image 7",
    media_type=models.MediaType.IMAGE,
)
media_object_7 = hari_uploader.HARIMediaObject(
    back_reference="car_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=500.0,
        y=600.0,
        width=400.0,
        height=250.0,
    ),
)
media_object_7.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "car" to "pedestrian"
media_7.add_media_object(media_object_7)

media_8 = hari_uploader.HARIMedia(
    file_key="Images/ecp10.png",
    name="A busy street 8",
    back_reference="image 8",
    media_type=models.MediaType.IMAGE,
)
media_object_8 = hari_uploader.HARIMediaObject(
    back_reference="traffic_light_1",
    reference_data=models.Point2DXY(x=800.0, y=200.0),
)
media_object_8.set_object_category_subset_name(
    "wheel"
)  # Changed from "traffic_light" to "wheel"
media_8.add_media_object(media_object_8)

media_9 = hari_uploader.HARIMedia(
    file_key="Images/ecp13.png",
    name="A busy street 9",
    back_reference="image 9",
    media_type=models.MediaType.IMAGE,
)
media_object_9 = hari_uploader.HARIMediaObject(
    back_reference="bicycle_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=350.0,
        y=500.0,
        width=200.0,
        height=150.0,
    ),
)
media_object_9.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "bicycle" to "pedestrian"
media_9.add_media_object(media_object_9)

media_10 = hari_uploader.HARIMedia(
    file_key="Images/ecp16.png",
    name="A busy street 10",
    back_reference="image 10",
    media_type=models.MediaType.IMAGE,
)
media_object_10 = hari_uploader.HARIMediaObject(
    back_reference="crosswalk",
    reference_data=models.PolyLine2DFlatCoordinates(
        coordinates=[200, 800, 800, 800],
        closed=False,
    ),
)
media_object_10.set_object_category_subset_name("road_marking")
media_10.add_media_object(media_object_10)

media_11 = hari_uploader.HARIMedia(
    file_key="Images/ecp19.png",
    name="A busy street 11",
    back_reference="image 11",
    media_type=models.MediaType.IMAGE,
)
media_object_11 = hari_uploader.HARIMediaObject(
    back_reference="bus_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=600.0,
        y=400.0,
        width=450.0,
        height=300.0,
    ),
)
attribute_object_11 = hari_uploader.HARIAttribute(
    id=is_moving_id,  # Reuse the same ID for all is_moving attributes
    name="is_moving",
    value=True,
)
media_object_11.add_attribute(attribute_object_11)
media_object_11.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "bus" to "pedestrian"
media_11.add_media_object(media_object_11)

media_12 = hari_uploader.HARIMedia(
    file_key="Images/ecp3.png",
    name="A busy street 12",
    back_reference="image 12",
    media_type=models.MediaType.IMAGE,
)
media_object_12 = hari_uploader.HARIMediaObject(
    back_reference="street_sign_1",
    reference_data=models.Point2DXY(x=750.0, y=150.0),
)
media_object_12.set_object_category_subset_name(
    "wheel"
)  # Changed from "street_sign" to "wheel"
media_12.add_media_object(media_object_12)

media_13 = hari_uploader.HARIMedia(
    file_key="Images/ecp6.png",
    name="A busy street 13",
    back_reference="image 13",
    media_type=models.MediaType.IMAGE,
)
media_object_13 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_2",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=300.0,
        y=650.0,
        width=150.0,
        height=300.0,
    ),
)
media_object_13.set_object_category_subset_name("pedestrian")
media_13.add_media_object(media_object_13)

media_14 = hari_uploader.HARIMedia(
    file_key="Images/ecp9.png",
    name="A busy street 14",
    back_reference="image 14",
    media_type=models.MediaType.IMAGE,
)
media_object_14 = hari_uploader.HARIMediaObject(
    back_reference="motorcycle_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=450.0,
        y=550.0,
        width=200.0,
        height=120.0,
    ),
)
media_object_14.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "motorcycle" to "pedestrian"
media_14.add_media_object(media_object_14)

media_15 = hari_uploader.HARIMedia(
    file_key="Images/ecp11.png",
    name="A busy street 15",
    back_reference="image 15",
    media_type=models.MediaType.IMAGE,
)
media_object_15 = hari_uploader.HARIMediaObject(
    back_reference="traffic_cone_1",
    reference_data=models.Point2DXY(x=400.0, y=750.0),
)
media_object_15.set_object_category_subset_name(
    "wheel"
)  # Changed from "traffic_cone" to "wheel"
media_15.add_media_object(media_object_15)

media_16 = hari_uploader.HARIMedia(
    file_key="Images/ecp14.png",
    name="A busy street 16",
    back_reference="image 16",
    media_type=models.MediaType.IMAGE,
)
media_object_16 = hari_uploader.HARIMediaObject(
    back_reference="building_1",
    reference_data=models.PolyLine2DFlatCoordinates(
        coordinates=[100, 100, 300, 100, 300, 400, 100, 400, 100, 100],
        closed=True,
    ),
)
media_object_16.set_object_category_subset_name(
    "road_marking"
)  # Changed from "building" to "road_marking"
media_16.add_media_object(media_object_16)

media_17 = hari_uploader.HARIMedia(
    file_key="Images/ecp17.png",
    name="A busy street 17",
    back_reference="image 17",
    media_type=models.MediaType.IMAGE,
)
media_object_17 = hari_uploader.HARIMediaObject(
    back_reference="truck_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=550.0,
        y=450.0,
        width=400.0,
        height=250.0,
    ),
)
attribute_object_17 = hari_uploader.HARIAttribute(
    id=is_parked_id,  # Reuse the same ID for all is_parked attributes
    name="is_parked",
    value=True,
)
media_object_17.add_attribute(attribute_object_17)
media_object_17.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "truck" to "pedestrian"
media_17.add_media_object(media_object_17)

media_18 = hari_uploader.HARIMedia(
    file_key="Images/ecp2.png",
    name="A busy street 18",
    back_reference="image 18",
    media_type=models.MediaType.IMAGE,
)
media_object_18 = hari_uploader.HARIMediaObject(
    back_reference="fire_hydrant_1",
    reference_data=models.Point2DXY(x=200.0, y=650.0),
)
media_object_18.set_object_category_subset_name(
    "wheel"
)  # Changed from "fire_hydrant" to "wheel"
media_18.add_media_object(media_object_18)

media_19 = hari_uploader.HARIMedia(
    file_key="Images/ecp4.png",
    name="A busy street 19",
    back_reference="image 19",
    media_type=models.MediaType.IMAGE,
)
media_object_19 = hari_uploader.HARIMediaObject(
    back_reference="pedestrian_crossing",
    reference_data=models.PolyLine2DFlatCoordinates(
        coordinates=[150, 700, 850, 700],
        closed=False,
    ),
)
media_object_19.set_object_category_subset_name("road_marking")
media_19.add_media_object(media_object_19)

media_20 = hari_uploader.HARIMedia(
    file_key="Images/ecp7.png",
    name="A busy street 20",
    back_reference="image 20",
    media_type=models.MediaType.IMAGE,
)
media_object_20 = hari_uploader.HARIMediaObject(
    back_reference="bus_stop_1",
    reference_data=models.BBox2DCenterPoint(
        type=models.BBox2DType.BBOX2D_CENTER_POINT,
        x=650.0,
        y=350.0,
        width=120.0,
        height=180.0,
    ),
)
media_object_20.set_object_category_subset_name(
    "pedestrian"
)  # Changed from "bus_stop" to "pedestrian"
media_20.add_media_object(media_object_20)

# Videos (without media objects as requested)
video_1 = hari_uploader.HARIMedia(
    file_key="Videos/ThumbnailsMP4_netw_opt.mp4",
    name="Video footage 1",
    back_reference="video 1",
    media_type=models.MediaType.VIDEO,
)

video_2 = hari_uploader.HARIMedia(
    file_key="Videos/ThumbnailsMov_netw_opt.mov",
    name="Video footage 2",
    back_reference="video 2",
    media_type=models.MediaType.VIDEO,
)

# Create a list of all medias to add to your dataset
all_medias = [
    media_1,
    media_2,
    media_3,
    media_4,
    media_5,
    media_6,
    media_7,
    media_8,
    media_9,
    media_10,
    media_11,
    media_12,
    media_13,
    media_14,
    media_15,
    media_16,
    media_17,
    media_18,
    media_19,
    media_20,
    video_1,
    video_2,
]

# 4. Set up the uploader and add the medias to it
uploader = hari_uploader.HARIUploader(
    client=hari,
    dataset_id=dataset_id,
    object_categories={"pedestrian", "wheel", "road_marking"},
)
uploader.add_media(*all_medias)

# 5. Trigger the upload process
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

# 6. Create a subset
print("Creating new subset...")
new_subset_id = hari.create_subset(
    dataset_id=dataset_id,
    subset_type=models.SubsetType.MEDIA_OBJECT,
    subset_name="All media objects",
)
print(f"Created new subset with id {new_subset_id}")

# 7. Trigger metadata updates
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
