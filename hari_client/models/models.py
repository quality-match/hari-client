from __future__ import annotations

import datetime
import enum
import typing
import uuid

import pydantic
from pydantic import model_validator

from hari_client.client import errors

typeT = typing.TypeVar("typeT", bound=typing.Any)


class BaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="allow",
        json_encoders={
            pydantic.BaseModel: lambda v: v.model_dump(),  # Serialize all nested Pydantic models using .model_dump()
            uuid.UUID: lambda v: str(v),
        },
    )


class VideoParameters(str, enum.Enum):
    # Currently empty
    pass


class VisualisationParameters(str, enum.Enum):
    # Currently empty
    pass


any_response_type = str | int | float | list | dict | None

ComparisonOperator = typing.Literal["<", "<=", ">", ">=", "==", "!="]
SetOperator = typing.Literal["in", "not in", "all"]
LogicOperator = typing.Literal["and", "or", "not"]
QueryOperator = ComparisonOperator | SetOperator


class QueryParameter(BaseModel):
    attribute: str
    query_operator: QueryOperator
    value: typing.Any = None


class LogicParameter(BaseModel):
    operator: LogicOperator
    queries: list[QueryParameter | LogicParameter]


class PaginationParameter(BaseModel):
    limit: int | None = None
    skip: int | None = None


QueryList = list[QueryParameter | LogicParameter]
SortingDirection = typing.Literal["asc", "desc"]


class SortingParameter(BaseModel):
    field: str
    order: SortingDirection


class QuaternionTuple(typing.NamedTuple):
    w: float
    x: float
    y: float
    z: float


class Point2DTuple(typing.NamedTuple):
    x: float
    y: float


class Point3DTuple(typing.NamedTuple):
    x: float
    y: float
    z: float


class Point3DAggregationMetrics(BaseModel):
    dummy_metrics: str = pydantic.Field(title="Dummy Metrics")


class Point2DAggregationMetrics(BaseModel):
    dummy_metrics: str = pydantic.Field(title="Dummy Metrics")


class BoundingBox2DAggregationMetrics(BaseModel):
    iou_to_aggregated_box: dict[str, typing.Any] | None = pydantic.Field(
        default=None, title="Iou To Aggregated Box"
    )
    distance_to_center_of_aggregated_box: dict[str, typing.Any] | None = pydantic.Field(
        default=None, title="Distance To Center Of Aggregated Box"
    )
    absolute_difference_to_area_of_aggregated_box: dict[
        str, typing.Any
    ] | None = pydantic.Field(
        default=None, title="Absolute Difference To Area Of Aggregated Box"
    )


class Point3DAggregation(BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    z: typing.Any = pydantic.Field(title="Z")
    metrics: Point3DAggregationMetrics | None = pydantic.Field(
        default=None, title="Point3DAggregationMetrics"
    )


class Point2DAggregation(BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    metrics: Point2DAggregationMetrics | None = pydantic.Field(
        default=None, title="Point2DAggregationMetrics"
    )


class BoundingBox2DAggregation(BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    width: typing.Any = pydantic.Field(title="Width")
    height: typing.Any = pydantic.Field(title="Height")
    metrics: BoundingBox2DAggregationMetrics | None = pydantic.Field(
        default=None, title="BoundingBox2DAggregationMetrics"
    )


class Point3DXYZ(BaseModel):
    """x, y, z: point coordinates"""

    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    z: typing.Any = pydantic.Field(title="Z")


class CuboidCenterPoint(BaseModel):
    """A 3D cuboid defined by its center point position, heading as quaternion and its
    dimensions along each axis."""

    type: str = pydantic.Field(title="Type")
    position: Point3DTuple = pydantic.Field()
    heading: QuaternionTuple = pydantic.Field()
    dimensions: Point3DTuple = pydantic.Field()


class PolyLine2DFlatCoordinates(BaseModel):
    type: str = "polyline_2d_flat_coordinates"
    coordinates: list[float] = pydantic.Field(title="Coordinates")
    closed: bool = pydantic.Field(default=False, title="Closed")


class Point2DXY(BaseModel):
    """x, y: point coordinates with x along the horizontal axis and y
    along the vertical axis."""

    type: str = "point2d_xy"
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")


class BBox2DType(str, enum.Enum):
    BBOX2D_CENTER_POINT = "bbox2d_center_point"
    BBOX2D_TOP_LEFT_POINT = "bbox2d_top_left_point"
    BBOX2D_CENTER_POINT_LENGTH = "bbox2d_center_point_length"
    BBOX2D_TWO_POINTS = "bbox2d_two_points"


class BBox2DCenterPoint(BaseModel):
    """2D center point Bounding Box representation.

    x, y: center point of the box, width, height: total width/height of the box.
    x and width are parallel to the horizontal axis, y and height are parallel
    to the vertical axis."""

    type: BBox2DType = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    width: typing.Any = pydantic.Field(title="Width")
    height: typing.Any = pydantic.Field(title="Height")


class DataSource(str, enum.Enum):
    QM = "QM"
    REFERENCE = "REFERENCE"


class MediaType(str, enum.Enum):
    """Describes the mediatype of annotatables in a dataset. Only available on datasets,
    not annotatables."""

    IMAGE = "image"
    VIDEO = "video"
    POINT_CLOUD = "point_cloud"


class MediaObjectType(str, enum.Enum):
    POINT2D_XY = "point2d_xy"
    POINT3D_XYZ = "point3d_xyz"
    BBOX_2D_CENTER_POINT_AGGREGATION = "bbox2d_center_point_aggregation"
    POINT_2D_XY_AGGREGATION = "point2d_xy_aggregation"
    POINT_3D_XYZ_AGGREGATION = "point3d_xyz_aggregation"
    BBOX2D_CENTER_POINT = "bbox2d_center_point"
    CUBOID_CENTER_POINT = "cuboid_center_point"
    POLYLINE2D_FLAT_COORDINATES = "polyline_2d_flat_coordinates"


class VisibilityStatus(str, enum.Enum):
    IMPORTING = "importing"
    SPLIT_AI_SUBSET = "split_ai_subset"
    VISIBLE = "visible"


class SubsetType(str, enum.Enum):
    MEDIA = "media"
    MEDIA_OBJECT = "media_object"
    INSTANCE = "instance"
    ATTRIBUTE = "attribute"


class DataBaseObjectType(str, enum.Enum):
    MEDIA = "Media"
    SUBIMAGE = "SubImage"
    MEDIAOBJECT = "MediaObject"
    ATTRIBUTE = "Attribute"
    ANNOTATION = "Annotation"
    VISUALISATION = "Visualisation"
    INSTANCE = "Instance"
    SNAPSHOT = "Snapshot"


class VisualisationType(str, enum.Enum):
    DEFAULT = "Default"
    CROP = "Crop"
    TILE = "Tile"
    IMAGETRANSFORMATION = "ImageTransformation"
    VIDEO = "Video"
    RENDERED = "Rendered"


class Dataset(BaseModel):
    id: uuid.UUID = pydantic.Field(title="Id")
    name: str = pydantic.Field(title="Name")
    data_root: str = pydantic.Field(title="Data Root")
    creation_timestamp: str = pydantic.Field(title="Creation Timestamp")
    mediatype: MediaType = pydantic.Field(title="MediaType")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    reference_files: list | None = pydantic.Field(default=None, title="Reference Files")
    num_medias: int = pydantic.Field(title="Num Medias")
    num_media_objects: int = pydantic.Field(title="Num Media Objects")
    num_annotations: int | None = pydantic.Field(default=None, title="Num Annotations")
    num_attributes: int | None = pydantic.Field(default=None, title="Num Attributes")
    num_instances: int = pydantic.Field(title="Num Instances")
    color: str | None = pydantic.Field(default="#FFFFFF", title="Color")
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    is_anonymized: bool | None = pydantic.Field(default=False, title="Is Anonymized")
    license: str | None = pydantic.Field(default=None, title="License")
    owner: str | None = pydantic.Field(default=None, title="Owner")
    current_snapshot_id: int | None = pydantic.Field(
        default=None, title="Current Snapshot Id"
    )
    visibility_status: VisibilityStatus | None = pydantic.Field(
        default="visible", title="VisibilityStatus"
    )


class DatasetResponse(BaseModel):
    id: uuid.UUID = pydantic.Field(title="Id")
    name: str = pydantic.Field(title="Name")
    parent_dataset: str | None = pydantic.Field(default=None, title="Parent Dataset")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    num_medias: int = pydantic.Field(title="Num Medias")
    num_media_objects: int = pydantic.Field(title="Num Media Objects")
    num_instances: int = pydantic.Field(title="Num Instances")
    done_percentage: typing.Any | None = pydantic.Field(
        default=None, title="Done Percentage"
    )
    creation_timestamp: str | None = pydantic.Field(
        default=None, title="Creation Timestamp"
    )
    color: str | None = pydantic.Field(default="#FFFFFF", title="Color")
    subset_type: SubsetType | None = pydantic.Field(default=None, title="SubsetType")
    mediatype: MediaType = pydantic.Field(title="MediaType")
    object_category: bool | None = pydantic.Field(default=None, title="Object Category")
    is_anonymized: bool | None = pydantic.Field(default=None, title="Is Anonymized")
    export_id: str | None = pydantic.Field(default=None, title="Export Id")
    license: str | None = pydantic.Field(default=None, title="License")
    visibility_status: VisibilityStatus | None = pydantic.Field(
        default=VisibilityStatus.VISIBLE, title="VisibilityStatus"
    )


class Pose3D(BaseModel):
    position: Point3DTuple = pydantic.Field()
    heading: QuaternionTuple = pydantic.Field()


class CameraModelType(str, enum.Enum):
    PINHOLE = "pinhole"
    FISHEYE = "fisheye"


class CameraDistortionCoefficients(BaseModel):
    k1: typing.Any | None = pydantic.Field(default=None, title="K1")
    k2: typing.Any | None = pydantic.Field(default=None, title="K2")
    k3: typing.Any | None = pydantic.Field(default=None, title="K3")
    k4: typing.Any | None = pydantic.Field(default=None, title="K4")
    p1: typing.Any | None = pydantic.Field(default=None, title="P1")
    p2: typing.Any | None = pydantic.Field(default=None, title="P2")


class CameraIntrinsics(BaseModel):
    camera_model: CameraModelType = pydantic.Field(title="CameraModelType")
    focal_length: Point2DTuple = pydantic.Field()
    principal_point: Point2DTuple = pydantic.Field()
    width_px: typing.Any = pydantic.Field(title="Width Px")
    height_px: typing.Any = pydantic.Field(title="Height Px")
    distortion_coefficients: CameraDistortionCoefficients | None = pydantic.Field(
        default=None, title="CameraDistortionCoefficients"
    )


class PointCloudMetadata(BaseModel):
    sensor_id: str = pydantic.Field(title="Sensor Id")
    lidar_sensor_pose: dict[str, typing.Any] = pydantic.Field(title="Lidar Sensor Pose")


class ImageMetadata(BaseModel):
    width: int | None = pydantic.Field(default=None, title="Width")
    height: int | None = pydantic.Field(default=None, title="Height")
    camera_intrinsics: CameraIntrinsics | None = pydantic.Field(
        default=None, title="CameraIntrinsics"
    )
    camera_extrinsics: Pose3D | None = pydantic.Field(default=None, title="Pose3D")


class TransformationParameters(BaseModel):
    """Parameters for image transformations.

    Attributes:
        resize: (width, height) of the resized image
        crop: ((x1, y1), (x2, y2)) top left and bottom right point of the cropped image
        quality: quality of the image after transformation in [0,100]
        format: format of the image after transformation (e.g. .jpeg, .png, .webp)
        rotate: rotation of the image in degrees in [0,359]
        upscale: whether to upscale the image if the new size is larger than the original
        proportion: proportion to apply when cropping in [0,1]
        strip_exif: whether to strip exif data from the image
        strip_icc: whether to strip icc data from the image
        flip: whether to flip the image horizontally
        flop: whether to flop the image vertically
    """

    resize: list | None = pydantic.Field(default=None, title="Resize")
    crop: list | None = pydantic.Field(default=None, title="Crop")
    quality: int | None = pydantic.Field(default=None, title="Quality")
    format: str | None = pydantic.Field(default=None, title="Format")
    rotate: int | None = pydantic.Field(default=None, title="Rotate")
    upscale: bool | None = pydantic.Field(default=None, title="Upscale")
    proportion: typing.Any | None = pydantic.Field(default=None, title="Proportion")
    strip_exif: bool | None = pydantic.Field(default=None, title="Strip Exif")
    strip_icc: bool | None = pydantic.Field(default=None, title="Strip Icc")
    flip: bool | None = pydantic.Field(default=None, title="Flip")
    flop: bool | None = pydantic.Field(default=None, title="Flop")
    original_image_height: int | None = pydantic.Field(
        default=None, title="Original Image Height"
    )
    original_image_width: int | None = pydantic.Field(
        default=None, title="Original Image Width"
    )


class ImageTransformation(BaseModel):
    """An image transformation is a visualisation created by transforming an image file."""

    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="ImageTransformation", title="Visualisation Type"
    )
    visualisation_configuration_id: str | None = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: TransformationParameters = pydantic.Field(
        title="TransformationParameters"
    )
    media_url: str | None = pydantic.Field(default=None, title="Media Url")


class Video(BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="Video", title="Visualisation Type"
    )
    visualisation_configuration_id: str | None = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: VideoParameters | None = pydantic.Field(
        default=None, title="VideoParameters"
    )
    media_url: str | None = pydantic.Field(default=None, title="Media Url")


class Tile(BaseModel):
    """A special case of cropping, where the image is cropped into multiple tiles."""

    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(default="Tile", title="Visualisation Type")
    visualisation_configuration_id: str | None = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: TransformationParameters = pydantic.Field(
        title="TransformationParameters"
    )
    media_url: str | None = pydantic.Field(default=None, title="Media Url")


class RenderedVisualisation(BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="Rendered", title="Visualisation Type"
    )
    visualisation_configuration_id: str | None = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: VisualisationParameters | None = pydantic.Field(
        default=None, title="VisualisationParameters"
    )
    media_url: str = pydantic.Field(title="Media Url")


class Media(BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default=None,
        title="Timestamp",
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    back_reference: str = pydantic.Field(title="Back Reference")
    subset_ids: list = pydantic.Field(default=[], title="Subset Ids")
    attributes: list = pydantic.Field(default=[], title="Attributes")
    thumbnails: dict[str, typing.Any] = pydantic.Field(default={}, title="Thumbnails")
    visualisations: list[VisualisationUnion] | None = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: str | None = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: str | None = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str = pydantic.Field(default="Media", title="Type")
    media_url: str = pydantic.Field(title="Media Url")
    pii_media_url: str = pydantic.Field(title="Pii Media Url")
    name: str = pydantic.Field(title="Name")
    metadata: ImageMetadata | PointCloudMetadata | None = pydantic.Field(
        default=None, title="ImageMetadata"
    )
    frame_idx: int | None = pydantic.Field(default=None, title="Frame Idx")
    media_type: MediaType | None = pydantic.Field(default=None, title="MediaType")
    frame_timestamp: str | None = pydantic.Field(default=None, title="Frame Timestamp")
    back_reference_json: str | None = pydantic.Field(
        default=None, title="Back Reference Json"
    )


class MediaResponse(BaseModel):
    id: str | None = pydantic.Field(default=None, title="Id")
    dataset_id: uuid.UUID | None = pydantic.Field(default=None, title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str | None = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=None, title="Archived")
    back_reference: str | None = pydantic.Field(default=None, title="Back Reference")
    subset_ids: list | None = pydantic.Field(default=None, title="Subset Ids")
    attributes: list[AttributeValueResponse] | None = pydantic.Field(
        default=None, title="Attributes"
    )
    thumbnails: dict[str, typing.Any] | None = pydantic.Field(
        default=None, title="Thumbnails"
    )
    visualisations: list[VisualisationUnion] | None = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: str | None = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: str | None = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str | None = pydantic.Field(default=None, title="Type")
    media_url: str | None = pydantic.Field(default=None, title="Media Url")
    pii_media_url: str | None = pydantic.Field(default=None, title="Pii Media Url")
    name: str | None = pydantic.Field(default=None, title="Name")
    metadata: ImageMetadata | PointCloudMetadata | None = pydantic.Field(
        default=None, title="ImageMetadata"
    )
    frame_idx: int | None = pydantic.Field(default=None, title="Frame Idx")
    media_type: MediaType | None = pydantic.Field(default=None, title="MediaType")
    frame_timestamp: str | None = pydantic.Field(default=None, title="Frame Timestamp")
    back_reference_json: str | None = pydantic.Field(
        default=None, title="Back Reference Json"
    )


class FilterCount(BaseModel):
    false_negative_percentage: typing.Any | None = pydantic.Field(
        default=None, title="False Negative Percentage"
    )
    false_positive_percentage: typing.Any | None = pydantic.Field(
        default=None, title="False Positive Percentage"
    )
    total_count: int = pydantic.Field(title="Total Count")


class RenderedVisualisationConfigParameters(BaseModel):
    type: str = pydantic.Field(default="rendered", title="Type")


class TileVisualisationConfigParameters(BaseModel):
    type: str = pydantic.Field(default="tile", title="Type")
    columns: int = pydantic.Field(title="Columns")
    rows: int = pydantic.Field(title="Rows")
    overlap_percent: typing.Any = pydantic.Field(title="Overlap Percent")


class LidarVideoStackedVisualisationConfigParameters(BaseModel):
    type: str = pydantic.Field(default="lidar_video_stacked", title="Type")


class LidarVideoVisualisationConfigParameters(BaseModel):
    type: str = pydantic.Field(default="lidar_video", title="Type")


class CropVisualisationConfigParameters(BaseModel):
    type: str = pydantic.Field(default="crop", title="Type")
    padding_percent: int = pydantic.Field(title="Padding Percent")
    padding_minimum: int = pydantic.Field(title="Padding Minimum")
    max_size: list | None = pydantic.Field(default=None, title="Max Size")
    aspect_ratio: list | None = pydantic.Field(default=None, title="Aspect Ratio")


class VisualisationConfiguration(BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    name: str = pydantic.Field(title="Name")
    parameters: (
        CropVisualisationConfigParameters
        | LidarVideoVisualisationConfigParameters
        | LidarVideoStackedVisualisationConfigParameters
        | TileVisualisationConfigParameters
        | RenderedVisualisationConfigParameters
    ) = pydantic.Field(title="CropVisualisationConfigParameters")
    subset_ids: list = pydantic.Field(title="Subset Ids")


class Visualisation(BaseModel):
    """A visualisation is a visual representation of an annotatable.

    Attributes:
        visualisation_type: type of visualisation
        visualisation_configuration_id: id of the visualisation configuration used to
        create the visualisation
        annotatable_id: id of the annotatable that is visualised
        annotatable_type: type of the annotatable that is visualised
        parameters: parameters used to create the visualisation
        media_url: url of the visualisation
    """

    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default=None,
        title="Timestamp",
    )
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    visualisation_type: VisualisationType = pydantic.Field(title="VisualisationType")
    visualisation_configuration_id: str | None = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: VisualisationParameters | None = pydantic.Field(
        default=None, title="VisualisationParameters"
    )
    media_url: str | None = pydantic.Field(default=None, title="Media Url")


class MediaObject(BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: uuid.UUID = pydantic.Field(title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=False, title="Archived")
    back_reference: str = pydantic.Field(title="Back Reference")
    subset_ids: list = pydantic.Field(default=[], title="Subset Ids")
    attributes: list[AttributeValueResponse] = pydantic.Field(
        default=[], title="Attributes"
    )
    thumbnails: dict[str, typing.Any] = pydantic.Field(default={}, title="Thumbnails")
    visualisations: list[VisualisationUnion] | None = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: str | None = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: str | None = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str = pydantic.Field(default="MediaObject", title="Type")
    media_id: str = pydantic.Field(title="Media Id")
    media_url: str = pydantic.Field(title="Media Url")
    crop_url: str = pydantic.Field(default=None, title="Crop Url")
    object_category: str | None = pydantic.Field(default=None, title="Object Category")
    source: DataSource = pydantic.Field(title="DataSource")
    qm_data: list[GeometryUnion] | None = pydantic.Field(
        default=None, title="QM sourced geometry object"
    )
    reference_data: GeometryUnion | None = pydantic.Field(
        default=None, title="Externally sourced geometry object"
    )
    frame_idx: int | None = pydantic.Field(default=None, title="Frame Idx")
    instance_id: str | None = pydantic.Field(default=None, title="Instance Id")
    media_object_type: MediaObjectType | None = pydantic.Field(
        default=None, title="Media Object Type"
    )


class MediaObjectResponse(BaseModel):
    id: str | None = pydantic.Field(default=None, title="Id")
    dataset_id: uuid.UUID | None = pydantic.Field(default=None, title="Dataset Id")
    tags: list | None = pydantic.Field(default=None, title="Tags")
    timestamp: str | None = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=None, title="Archived")
    back_reference: str | None = pydantic.Field(default=None, title="Back Reference")
    subset_ids: list | None = pydantic.Field(default=None, title="Subset Ids")
    attributes: list[AttributeValueResponse] | None = pydantic.Field(
        default=None, title="Attributes"
    )
    thumbnails: dict[str, typing.Any] | None = pydantic.Field(
        default=None, title="Thumbnails"
    )
    visualisations: list[VisualisationUnion] | None = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: str | None = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: str | None = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str | None = pydantic.Field(default=None, title="Type")
    media_id: str | None = pydantic.Field(default=None, title="Media Id")
    media_url: str | None = pydantic.Field(default=None, title="Media Url")
    crop_url: str | None = pydantic.Field(default=None, title="Crop Url")
    object_category: str | None = pydantic.Field(default=None, title="Object Category")
    source: DataSource | None = pydantic.Field(default=None, title="DataSource")
    qm_data: list[GeometryUnion] | None = pydantic.Field(
        default=None, title="QM sourced geometry object"
    )
    reference_data: GeometryUnion | None = pydantic.Field(
        default=None, title="Externally sourced geometry object"
    )
    frame_idx: int | None = pydantic.Field(default=None, title="Frame Idx")
    instance_id: str | None = pydantic.Field(default=None, title="Instance Id")
    media_object_type: MediaObjectType | None = pydantic.Field(
        default=None, title="Media Object Type"
    )


class TrainingAttribute(BaseModel):
    dataset_id: str = pydantic.Field(default=None, title="Dataset Id")
    attribute_id: str = pydantic.Field(default=None, title="Attribute Id")
    query: QueryList | None = pydantic.Field(default_factory=list, title="Query")


class DevelopmentSetResponse(BaseModel):
    id: str | None = pydantic.Field(default=None, title="Id")
    name: str | None = pydantic.Field(default=None, title="Name")
    created_at: str | None = pydantic.Field(default=None, title="Created At")
    updated_at: str | None = pydantic.Field(default=None, title="Updated At")
    archived_at: str | None = pydantic.Field(default=None, title="Archived At")
    owner: str | None = pydantic.Field(default=None, title="Owner")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    training_attributes: list[TrainingAttribute] = pydantic.Field(
        default_factory=list, title="Training Attributes"
    )
    question: str | None = pydantic.Field(default=None, title="Question")
    possible_answers: list[str | int | bool] = pydantic.Field(
        default_factory=list, title="Possible Answers"
    )
    repeats: int | None = pydantic.Field(default=None, title="Repeats")
    subset_id: str | None = pydantic.Field(default=None, title="Subset Id")


MLAnnotationModelStatus = typing.Literal[
    "created", "training", "training_failed", "training_done"
]


class MlAnnotationModel(BaseModel):
    created_at: str | None = pydantic.Field(default=None, title="Created At")
    updated_at: str | None = pydantic.Field(default=None, title="Updated At")
    archived_at: str | None = pydantic.Field(default=None, title="Archived At")
    owner: str | None = pydantic.Field(default=None, title="Owner")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    status: MLAnnotationModelStatus = pydantic.Field(default=None, title="Status")
    dataset_id: str = pydantic.Field(default=None, title="Dataset Id")
    reference_set_annotation_run_id: str | None = pydantic.Field(
        default=None, title="Reference Set Annotation Run Id"
    )
    name: str | None = pydantic.Field(default=None, title="Name")
    training_subset_id: str | None = pydantic.Field(
        default=None, title="Training Subset Id"
    )
    validation_subset_id: str | None = pydantic.Field(
        default=None, title="Validation Subset Id"
    )
    test_subset_id: str | None = pydantic.Field(default=None, title="Test Subset Id")
    automation_correctness_curve: dict | None = pydantic.Field(
        default_factory=dict, title="Automation Correctness Curve"
    )
    model_weight_location: str | None = pydantic.Field(
        default=None, title="Model Weight Location"
    )
    training_set_id: str | None = pydantic.Field(default=None, title="Training Set Id")
    id: str = pydantic.Field(default=None, title="Id")


AiAnnotationRunStatus = typing.Literal[
    "created", "annotating", "creation_failed", "ai_annotation_failed", "done"
]


class AiAnnotationRun(BaseModel):
    created_at: str | None = pydantic.Field(default=None, title="Created At")
    updated_at: str | None = pydantic.Field(default=None, title="Updated At")
    archived_at: str | None = pydantic.Field(default=None, title="Archived At")
    owner: str | None = pydantic.Field(default=None, title="Owner")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    name: str = pydantic.Field(default=None, title="Name")
    status: AiAnnotationRunStatus = pydantic.Field(default=None, title="Status")
    dataset_id: str = pydantic.Field(default=None, title="Dataset Id")
    subset_id: str = pydantic.Field(default=None, title="Subset Id")
    ml_annotation_model_id: str | None = pydantic.Field(
        default=None, title="ML Annotation Model Id"
    )
    attribute_metadata_id: str | None = pydantic.Field(
        default=None, title="Attribute Metadata Id"
    )
    id: str = pydantic.Field(default=None, title="Id")
    completed_at: str | None = pydantic.Field(default=None, title="Completed At")


class ValidationError(BaseModel):
    loc: list = pydantic.Field(title="Location")
    msg: str = pydantic.Field(title="Message")
    type: str = pydantic.Field(title="Error Type")


class AttributeGroup(str, enum.Enum):
    AnnotationAttribute = "annotation_attribute"
    MlAnnotationAttribute = "ml_annotation_attribute"
    AutoAttribute = "auto_attribute"
    InitialAttribute = "initial_attribute"
    InheritedAnnotationAttribute = "inherited_annotation_attribute"


class AttributeType(str, enum.Enum):
    Binary = "BINARY"
    Categorical = "CATEGORICAL"
    Slider = "SLIDER"
    BBox2D = "BBOX2D"
    Point2D = "POINT2D"
    Point3D = "POINT3D"


class HistogramType(str, enum.Enum):
    boolean = "BOOLEAN"
    categorical = "CATEGORICAL"
    numerical = "NUMERICAL"
    subset = "SUBSET"


class AttributeHistogramStatistics(BaseModel):
    variance: float
    average: float
    quantiles_25: float
    quantiles_50: float
    quantiles_75: float
    interquartile_range: float
    shapiro_p_value: float | None = None


class AttributeHistogram(BaseModel):
    attribute_id: str
    attribute_name: str
    filter_name: str
    type: HistogramType
    attribute_group: AttributeGroup
    dataset_id: uuid.UUID
    subset_id: str | None = None
    num_buckets: int | None = None
    lower: float | None = None
    upper: float | None = None
    interval: float | None = None
    buckets: list[tuple[int | float | str, int]]
    cant_solves: int = 0
    corrupt_data: int = 0
    statistics: AttributeHistogramStatistics | None = None


class MediaUploadUrlInfo(BaseModel):
    upload_url: str
    media_id: str
    media_url: str


class VisualisationUploadUrlInfo(BaseModel):
    upload_url: str
    visualisation_id: str
    visualisation_url: str


VisualisationUnion = ImageTransformation | Video | Tile | RenderedVisualisation
GeometryUnion = (
    BBox2DCenterPoint
    | Point2DXY
    | PolyLine2DFlatCoordinates
    | CuboidCenterPoint
    | Point3DXYZ
    | BoundingBox2DAggregation
    | Point2DAggregation
    | Point3DAggregation
)


class BulkOperationStatusEnum(str, enum.Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    PROCESSING = "processing"


class BulkUploadSuccessSummary(BaseModel):
    """Quantifies how many items were successfully uploaded and how many failed in a bulk request.

    Attributes:
        total: The total number of items.
        successful: The number of successful uploads.
        failed: The number of failed uploads.
    """

    total: int = 0
    successful: int = 0
    failed: int = 0


class ResponseStatesEnum(str, enum.Enum):
    SUCCESS = "success"
    MISSING_DATA = "missing_data"
    SERVER_ERROR = "server_error"
    BAD_DATA = "bad_data"
    CONFLICT = "conflict"


class BaseBulkItemResponse(BaseModel, arbitrary_types_allowed=True):
    item_id: str | None = None
    status: ResponseStatesEnum
    errors: list[str] | None = None


class AnnotatableCreateResponse(BaseBulkItemResponse):
    bulk_operation_annotatable_id: str


class AttributeCreateResponse(BaseBulkItemResponse):
    annotatable_id: str


class BulkResponse(BaseModel):
    status: BulkOperationStatusEnum = BulkOperationStatusEnum.PROCESSING
    summary: BulkUploadSuccessSummary = pydantic.Field(
        default_factory=BulkUploadSuccessSummary
    )
    results: list[
        AnnotatableCreateResponse | AttributeCreateResponse | BaseBulkItemResponse
    ] = pydantic.Field(default_factory=list)


class MediaCreate(BaseModel):
    # file_path is not part of the HARI API, but is used to define where to read the
    # media file from
    file_path: str | None = pydantic.Field(default=None, exclude=True)

    name: str
    media_type: MediaType
    back_reference: str
    media_url: str | None = None

    id: str | None = pydantic.Field(
        default=None, title="Id"
    )  # used to identify already uploaded medias

    archived: bool = False
    scene_id: str | None = None
    realWorldObject_id: str | None = None
    visualisations: list[VisualisationUnion] | None = None
    subset_ids: set[str] | list[str] | None = None

    metadata: ImageMetadata | PointCloudMetadata | None = None
    frame_idx: int | None = None
    frame_timestamp: datetime.datetime | None = None
    back_reference_json: str | None = None


class BulkMediaCreate(MediaCreate):
    """
    bulk_operation_annotatable_id is used to link the media in the bulk creation to the returned response entry with created media.
    Its value should be unique for each media within the bulk.
    """

    bulk_operation_annotatable_id: str

    @model_validator(mode="before")
    @classmethod
    def check_bulk_operation_annotatable_id_omitted(
        cls, data: typing.Any
    ) -> typing.Any:
        if isinstance(data, dict) and "bulk_operation_annotatable_id" not in data:
            raise errors.BulkOperationAnnotatableIdMissing()
        return data


class MediaObjectCreate(BaseModel):
    media_id: str
    source: DataSource = DataSource.REFERENCE
    back_reference: str

    id: str | None = pydantic.Field(
        default=None, title="Id"
    )  # used to identify already uploaded medias

    archived: bool = False
    scene_id: str | None = None
    realWorldObject_id: str | None = None
    visualisations: list[VisualisationUnion] | None = None
    subset_ids: set[str] | list[str] | None = None

    instance_id: str | None = None
    object_category: uuid.UUID | None = None
    # source represents if the media object is either a geometry that was constructed by
    # QM, e.g., by annotating media data; or a geometry that was already provided by a
    # customer, and hence, would be a REFERENCE.
    qm_data: list[GeometryUnion] | None = None
    reference_data: GeometryUnion | None = None
    frame_idx: int | None = None
    media_object_type: GeometryUnion | None = None


class BulkMediaObjectCreate(MediaObjectCreate):
    """
    bulk_operation_annotatable_id is used to link the media object in the bulk creation to the returned response entry with created media object.
    Its value should be unique for each media object within the bulk.
    """

    bulk_operation_annotatable_id: str

    @model_validator(mode="before")
    @classmethod
    def check_bulk_operation_annotatable_id_omitted(
        cls, data: typing.Any
    ) -> typing.Any:
        if isinstance(data, dict) and "bulk_operation_annotatable_id" not in data:
            raise errors.BulkOperationAnnotatableIdMissing()
        return data


class AttributeCreate(BaseModel):
    # This value is mandatory during upload but needs to be synced with existing values in HARI and this is set programmatically in the Uploader
    id: uuid.UUID | str | None = (
        None  # value should be UUID but legacy attributes can be str
    )
    name: str
    annotatable_id: str
    annotatable_type: typing.Literal[
        DataBaseObjectType.MEDIA,
        DataBaseObjectType.MEDIAOBJECT,
        DataBaseObjectType.INSTANCE,
    ]
    attribute_type: AttributeType | None = None
    attribute_group: AttributeGroup = AttributeGroup.InitialAttribute
    value: typeT
    min: typeT | None = None
    max: typeT | None = None
    sum: typeT | None = None
    cant_solves: int | None = None
    solvability: float | None = None
    aggregate: typeT | None = None
    modal: typeT | None = None
    credibility: float | None = None
    convergence: float | None = None
    ambiguity: float | None = None
    median: typeT | None = None
    variance: float | None = None
    standard_deviation: float | None = None
    range: typing.Any | None = None
    average_absolute_deviation: float | None = None
    cumulated_frequency: typing.Any | None = None
    frequency: dict[str, int] | None = None
    question: str | None = None
    repeats: int | None = None
    possible_values: list[str | int | float | bool] | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def populate_derived_field(cls, values):
        derived_fields = {
            "question": values.get("question", values.get("name")),
        }
        values.update(derived_fields)

        return values


class Attribute(BaseModel):
    # AttributeValue + AttributeMetadata = Attribute
    id: str = pydantic.Field(title="ID")
    name: str
    question: str
    annotatable_id: str
    annotatable_type: DataBaseObjectType
    subset_ids: set[str] = set()
    attribute_type: AttributeType | None = None
    attribute_group: AttributeGroup
    value: typeT
    min: typeT | None = None
    max: typeT | None = None
    sum: typeT | None = None
    cant_solves: int | None = None
    solvability: float | None = None
    aggregate: typeT | None = None
    modal: typeT | None = None
    credibility: float | None = None
    convergence: float | None = None
    confidence: float | None = None
    ambiguity: float | None = None
    median: typeT | None = None
    variance: float | None = None
    standard_deviation: float | None = None
    range: typing.Any | None = None
    average_absolute_deviation: float | None = None
    cumulated_frequency: typing.Any | None = None
    frequency: dict[str, int] | None = None
    question: str | None = None
    ml_predictions: dict[str, float] | None = None
    ml_probability_distributions: dict[str, float] | None = None
    cant_solve_ratio: float | None = None
    repeats: int | None = None
    possible_values: list[str | int | float | bool] | None = None


class AttributeResponse(BaseModel):
    # AttributeValue + AttributeMetadata = Attribute
    id: str | None = pydantic.Field(default=None, title="Id")
    dataset_id: str | None = pydantic.Field(default=None, title="Dataset Id")
    timestamp: str | None = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=None, title="Archived")
    subset_ids: set[str] = pydantic.Field(default=set(), title="Subset Ids")
    metadata_id: str | None = pydantic.Field(default=None, title="Metadata Id")
    name: str | None = pydantic.Field(default=None, title="Name")
    question: str | None = pydantic.Field(default=None, title="Question")
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable ID")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="Annotatable Type"
    )
    attribute_type: AttributeType | None = pydantic.Field(
        default=None, title="Attribute Type"
    )
    attribute_group: AttributeGroup | None = pydantic.Field(
        default=None, title="Attribute Group"
    )
    value: typeT | None = pydantic.Field(default=None, title="Value")
    min: typeT | None = pydantic.Field(default=None, title="Min")
    max: typeT | None = pydantic.Field(default=None, title="Max")
    sum: typeT | None = pydantic.Field(default=None, title="Sum")
    cant_solves: int | None = pydantic.Field(default=None, title="Cant Solves")
    solvability: float | None = pydantic.Field(default=None, title="Solvability")
    confidence: float | None = pydantic.Field(default=None, title="Confidence")
    aggregate: typeT | None = pydantic.Field(default=None, title="Aggregate")
    modal: typeT | None = pydantic.Field(default=None, title="Modal")
    credibility: float | None = pydantic.Field(default=None, title="Credibility")
    convergence: float | None = pydantic.Field(default=None, title="Convergence")
    ambiguity: float | None = pydantic.Field(default=None, title="Ambiguity")
    median: typeT | None = pydantic.Field(default=None, title="Median")
    variance: float | None = pydantic.Field(default=None, title="Variance")
    standard_deviation: float | None = pydantic.Field(
        default=None, title="Standard Deviation"
    )
    range: typing.Any | None = pydantic.Field(default=None, title="Range")
    average_absolute_deviation: float | None = pydantic.Field(
        default=None, title="Average Absolute Deviation"
    )
    cumulated_frequency: typing.Any | None = pydantic.Field(
        default=None, title="Cumulated Frequency"
    )
    frequency: dict[str, int] | None = pydantic.Field(default=None, title="Frequency")
    ml_predictions: dict[str, float] | None = pydantic.Field(
        default=None,
        title="ML Predictions",
        description="These are the parameters of the posterior Dirichlet distribution",
    )
    ml_probability_distributions: dict[str, float] | None = pydantic.Field(
        default=None,
        title="ML Probability Distributions",
        description="A point estimate for the probability associated with each category"
        ", obtained from the full Dirichlet distribution predicted by the"
        " model.",
    )
    cant_solve_ratio: float | None = pydantic.Field(
        default=None,
        title="Can't Solve Ratio",
    )
    repeats: int | None = pydantic.Field(
        default=None,
        title="Repeats",
        description="Number of repeats for this attribute",
    )
    possible_values: list[str | int | float | bool] | None = pydantic.Field(
        default=None,
        title="Possible Values",
        description="Possible values for this attribute",
    )


class AttributeValueResponse(BaseModel):
    # AttributeValue + AttributeMetadata = Attribute
    id: str | None = pydantic.Field(default=None, title="Id")
    dataset_id: str | None = pydantic.Field(default=None, title="Dataset Id")
    timestamp: str | None = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=None, title="Archived")
    annotatable_id: str | None = pydantic.Field(default=None, title="Annotatable ID")
    metadata_id: str | None = pydantic.Field(default=None, title="Metadata Id")
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="Annotatable Type"
    )
    value: typeT | None = pydantic.Field(default=None, title="Value")
    min: typeT | None = pydantic.Field(default=None, title="Min")
    max: typeT | None = pydantic.Field(default=None, title="Max")
    sum: typeT | None = pydantic.Field(default=None, title="Sum")
    cant_solves: int | None = pydantic.Field(default=None, title="Cant Solves")
    cant_solve_ratio: float | None = pydantic.Field(
        default=None, title="Can't Solve Ratio"
    )
    solvability: float | None = pydantic.Field(default=None, title="Solvability")
    aggregate: typeT | None = pydantic.Field(default=None, title="Aggregate")
    modal: typeT | None = pydantic.Field(default=None, title="Modal")
    credibility: float | None = pydantic.Field(default=None, title="Credibility")
    convergence: float | None = pydantic.Field(default=None, title="Convergence")
    confidence: float | None = pydantic.Field(default=None, title="Confidence")
    ambiguity: float | None = pydantic.Field(default=None, title="Ambiguity")
    median: typeT | None = pydantic.Field(default=None, title="Median")
    variance: float | None = pydantic.Field(default=None, title="Variance")
    standard_deviation: float | None = pydantic.Field(
        default=None, title="Standard Deviation"
    )
    range: typing.Any | None = pydantic.Field(default=None, title="Range")
    average_absolute_deviation: float | None = pydantic.Field(
        default=None, title="Average Absolute Deviation"
    )
    cumulated_frequency: typing.Any | None = pydantic.Field(
        default=None, title="Cumulated Frequency"
    )
    frequency: dict[str, int] | None = pydantic.Field(default=None, title="Frequency")
    ml_predictions: dict[str, float] | None = pydantic.Field(
        default=None,
        title="ML Predictions",
        description="These are the parameters of the posterior Dirichlet distribution",
    )
    ml_probability_distributions: dict[str, float] | None = pydantic.Field(
        default=None,
        title="ML Probability Distributions",
        description="A point estimate for the probability associated with each category,"
        " obtained from the full Dirichlet distribution predicted by the model.",
    )


class AttributeMetadataResponse(BaseModel):
    # AttributeValue + AttributeMetadata = Attribute
    id: str | None = pydantic.Field(default=None, title="Id")
    dataset_id: str | None = pydantic.Field(default=None, title="Dataset Id")
    tags: set[str] | None = pydantic.Field(default=None, title="Tags")
    timestamp: str | None = pydantic.Field(default=None, title="Timestamp")
    archived: bool | None = pydantic.Field(default=None, title="Archived")
    name: str | None = pydantic.Field(default=None, title="Name")
    question: str | None = pydantic.Field(default=None, title="Question")
    subset_ids: set[str] | None = pydantic.Field(default=None, title="Subset Ids")
    attribute_type: AttributeType | None = pydantic.Field(
        default=None, title="Attribute Type"
    )
    attribute_group: AttributeGroup | None = pydantic.Field(
        default=None, title="Attribute Group"
    )
    annotatable_type: DataBaseObjectType | None = pydantic.Field(
        default=None, title="Annotatable Type"
    )
    annotation_run_node_id: str | None = pydantic.Field(
        default=None, title="Annotation Run Node ID"
    )
    annotation_run_id: str | None = pydantic.Field(
        default=None, title="Annotation Run ID"
    )
    pipeline_project: dict | None = pydantic.Field(
        default=None, title="Pipeline Project"
    )
    possible_values: list[str | int | float | bool] | None = pydantic.Field(
        default=None,
        title="Possible Values",
        description="Possible values for this attribute",
    )


class BulkAttributeCreate(AttributeCreate):
    pass


class ProcessingType(str, enum.Enum):
    LOCAL = "local"
    REMOTE = "remote"


class ProcessingJobMethods(str, enum.Enum):
    THUMBNAILS_CREATION = "create_thumbnails"
    HISTOGRAMS_UPDATE = "update_histograms"
    CROPS_CREATION = "create_crops"
    METADATA_REBUILD = "metadata_rebuild"


class ProcessingJobStatus(str, enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessingJob(BaseModel):
    id: uuid.UUID = pydantic.Field(title="ID")
    status: ProcessingJobStatus = pydantic.Field(title="Status")
    owner: uuid.UUID | None = pydantic.Field(default=None, title="Owner")
    user_group: str | None = pydantic.Field(default=None, title="User Group")
    created_at: datetime.datetime | None = pydantic.Field(
        title="Created At", default=None
    )
    updated_at: datetime.datetime | None = pydantic.Field(
        title="Updated At", default=None
    )
    archived_at: datetime.datetime | None = pydantic.Field(
        title="Archived At", default=None
    )
    process_name: str = pydantic.Field(title="Process Name")
    details: str = pydantic.Field(title="Details")
    trace_id: uuid.UUID | None = pydantic.Field(default=None, title="Trace ID")


class BaseProcessingJobParameters(BaseModel):
    # this is intentionally left empty to allow for arbitrary parameters
    pass


class BaseProcessingJobMethod(BaseModel):
    method_name: str
    batch: bool = False
    override_processing_type: ProcessingType | None = None
    task_token: str | None = None
    job_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    user_group: str | None = None
    parameters: BaseProcessingJobParameters
