from __future__ import annotations

import enum
import typing
import uuid

import pydantic


class VideoParameters(str, enum.Enum):
    # Currently empty
    pass


class VisualisationParameters(str, enum.Enum):
    # Currently empty
    pass


ComparisonOperator = typing.Literal["<", "<=", ">", ">=", "==", "!="]
SetOperator = typing.Literal["in", "not in", "all"]
LogicOperator = typing.Literal["and", "or", "not"]
QueryOperator = typing.Union[ComparisonOperator, SetOperator]


class QueryParameter(pydantic.BaseModel):
    attribute: str
    query_operator: QueryOperator
    value: typing.Any = None


class LogicParameter(pydantic.BaseModel):
    operator: LogicOperator
    queries: list[typing.Union[QueryParameter, LogicParameter]]


class PaginationParameter(pydantic.BaseModel):
    limit: typing.Optional[int] = None
    skip: typing.Optional[int] = None


QueryList = list[typing.Union[QueryParameter, LogicParameter]]
SortingDirection = typing.Literal["asc", "desc"]


class SortingParameter(pydantic.BaseModel):
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


class Point3DAggregationMetrics(pydantic.BaseModel):
    dummy_metrics: str = pydantic.Field(title="Dummy Metrics")


class Point2DAggregationMetrics(pydantic.BaseModel):
    dummy_metrics: str = pydantic.Field(title="Dummy Metrics")


class BoundingBox2DAggregationMetrics(pydantic.BaseModel):
    iou_to_aggregated_box: typing.Optional[dict[str, typing.Any]] = pydantic.Field(
        default=None, title="Iou To Aggregated Box"
    )
    distance_to_center_of_aggregated_box: typing.Optional[
        dict[str, typing.Any]
    ] = pydantic.Field(default=None, title="Distance To Center Of Aggregated Box")
    absolute_difference_to_area_of_aggregated_box: typing.Optional[
        dict[str, typing.Any]
    ] = pydantic.Field(
        default=None, title="Absolute Difference To Area Of Aggregated Box"
    )


class Point3DAggregation(pydantic.BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    z: typing.Any = pydantic.Field(title="Z")
    metrics: typing.Optional[Point3DAggregationMetrics] = pydantic.Field(
        default=None, title="Point3DAggregationMetrics"
    )


class Point2DAggregation(pydantic.BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    metrics: typing.Optional[Point2DAggregationMetrics] = pydantic.Field(
        default=None, title="Point2DAggregationMetrics"
    )


class BoundingBox2DAggregation(pydantic.BaseModel):
    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    width: typing.Any = pydantic.Field(title="Width")
    height: typing.Any = pydantic.Field(title="Height")
    metrics: typing.Optional[BoundingBox2DAggregationMetrics] = pydantic.Field(
        default=None, title="BoundingBox2DAggregationMetrics"
    )


class Point3DXYZ(pydantic.BaseModel):
    """x, y, z: point coordinates"""

    type: str = pydantic.Field(title="Type")
    x: typing.Any = pydantic.Field(title="X")
    y: typing.Any = pydantic.Field(title="Y")
    z: typing.Any = pydantic.Field(title="Z")


class CuboidCenterPoint(pydantic.BaseModel):
    """A 3D cuboid defined by its center point position, heading as quaternion and its dimensions along each axis."""

    type: str = pydantic.Field(title="Type")
    position: Point3DTuple = pydantic.Field()
    heading: QuaternionTuple = pydantic.Field()
    dimensions: Point3DTuple = pydantic.Field()


class PolyLine2DFlatCoordinates(pydantic.BaseModel):
    type: str = "polyline_2d_flat_coordinates"
    coordinates: list[float] = pydantic.Field(title="Coordinates")
    closed: bool = pydantic.Field(default=False, title="Closed")


class Point2DXY(pydantic.BaseModel):
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


class BBox2DCenterPoint(pydantic.BaseModel):
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
    """Describes the mediatype of annotatables in a dataset. Only available on datasets, not annotatables."""

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


class Dataset(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    name: str = pydantic.Field(title="Name")
    data_root: str = pydantic.Field(title="Data Root")
    creation_timestamp: str = pydantic.Field(title="Creation Timestamp")
    mediatype: MediaType = pydantic.Field(title="MediaType")
    customer: typing.Optional[str] = pydantic.Field(default=None, title="Customer")
    reference_files: typing.Optional[list] = pydantic.Field(
        default=None, title="Reference Files"
    )
    num_medias: int = pydantic.Field(title="Num Medias")
    num_media_objects: int = pydantic.Field(title="Num Media Objects")
    num_annotations: typing.Optional[int] = pydantic.Field(
        default=None, title="Num Annotations"
    )
    num_attributes: typing.Optional[int] = pydantic.Field(
        default=None, title="Num Attributes"
    )
    num_instances: int = pydantic.Field(title="Num Instances")
    color: typing.Optional[str] = pydantic.Field(default="#FFFFFF", title="Color")
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    is_anonymized: typing.Optional[bool] = pydantic.Field(
        default=False, title="Is Anonymized"
    )
    license: typing.Optional[str] = pydantic.Field(default=None, title="License")
    owner: typing.Optional[str] = pydantic.Field(default=None, title="Owner")
    current_snapshot_id: typing.Optional[int] = pydantic.Field(
        default=None, title="Current Snapshot Id"
    )
    visibility_status: typing.Optional[VisibilityStatus] = pydantic.Field(
        default="visible", title="VisibilityStatus"
    )


class DatasetResponse(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    name: str = pydantic.Field(title="Name")
    parent_dataset: typing.Optional[str] = pydantic.Field(
        default=None, title="Parent Dataset"
    )
    num_medias: int = pydantic.Field(title="Num Medias")
    num_media_objects: int = pydantic.Field(title="Num Media Objects")
    num_instances: int = pydantic.Field(title="Num Instances")
    done_percentage: typing.Optional[typing.Any] = pydantic.Field(
        default=None, title="Done Percentage"
    )
    creation_timestamp: typing.Optional[str] = pydantic.Field(
        default=None, title="Creation Timestamp"
    )
    color: typing.Optional[str] = pydantic.Field(default="#FFFFFF", title="Color")
    subset_type: typing.Optional[SubsetType] = pydantic.Field(
        default=None, title="SubsetType"
    )
    mediatype: MediaType = pydantic.Field(title="MediaType")
    object_category: typing.Optional[bool] = pydantic.Field(
        default=None, title="Object Category"
    )
    is_anonymized: typing.Optional[bool] = pydantic.Field(
        default=None, title="Is Anonymized"
    )
    export_id: typing.Optional[str] = pydantic.Field(default=None, title="Export Id")
    license: typing.Optional[str] = pydantic.Field(default=None, title="License")
    visibility_status: typing.Optional[VisibilityStatus] = pydantic.Field(
        default="visible", title="VisibilityStatus"
    )


class Pose3D(pydantic.BaseModel):
    position: Point3DTuple = pydantic.Field()
    heading: QuaternionTuple = pydantic.Field()


class CameraModelType(str, enum.Enum):
    PINHOLE = "pinhole"
    FISHEYE = "fisheye"


class CameraDistortionCoefficients(pydantic.BaseModel):
    k1: typing.Optional[typing.Any] = pydantic.Field(default=None, title="K1")
    k2: typing.Optional[typing.Any] = pydantic.Field(default=None, title="K2")
    k3: typing.Optional[typing.Any] = pydantic.Field(default=None, title="K3")
    k4: typing.Optional[typing.Any] = pydantic.Field(default=None, title="K4")
    p1: typing.Optional[typing.Any] = pydantic.Field(default=None, title="P1")
    p2: typing.Optional[typing.Any] = pydantic.Field(default=None, title="P2")


class CameraIntrinsics(pydantic.BaseModel):
    camera_model: CameraModelType = pydantic.Field(title="CameraModelType")
    focal_length: Point2DTuple = pydantic.Field()
    principal_point: Point2DTuple = pydantic.Field()
    width_px: typing.Any = pydantic.Field(title="Width Px")
    height_px: typing.Any = pydantic.Field(title="Height Px")
    distortion_coefficients: typing.Optional[
        CameraDistortionCoefficients
    ] = pydantic.Field(default=None, title="CameraDistortionCoefficients")


class PointCloudMetadata(pydantic.BaseModel):
    sensor_id: str = pydantic.Field(title="Sensor Id")
    lidar_sensor_pose: dict[str, typing.Any] = pydantic.Field(title="Lidar Sensor Pose")


class ImageMetadata(pydantic.BaseModel):
    width: typing.Optional[int] = pydantic.Field(default=None, title="Width")
    height: typing.Optional[int] = pydantic.Field(default=None, title="Height")
    camera_intrinsics: typing.Optional[CameraIntrinsics] = pydantic.Field(
        default=None, title="CameraIntrinsics"
    )
    camera_extrinsics: typing.Optional[Pose3D] = pydantic.Field(
        default=None, title="Pose3D"
    )


class TransformationParameters(pydantic.BaseModel):
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

    resize: typing.Optional[list] = pydantic.Field(default=None, title="Resize")
    crop: typing.Optional[list] = pydantic.Field(default=None, title="Crop")
    quality: typing.Optional[int] = pydantic.Field(default=None, title="Quality")
    format: typing.Optional[
        typing.Union[str, str, str, str, str, str, str, str, str]
    ] = pydantic.Field(default=None, title="Format")
    rotate: typing.Optional[int] = pydantic.Field(default=None, title="Rotate")
    upscale: typing.Optional[bool] = pydantic.Field(default=None, title="Upscale")
    proportion: typing.Optional[typing.Any] = pydantic.Field(
        default=None, title="Proportion"
    )
    strip_exif: typing.Optional[bool] = pydantic.Field(default=None, title="Strip Exif")
    strip_icc: typing.Optional[bool] = pydantic.Field(default=None, title="Strip Icc")
    flip: typing.Optional[bool] = pydantic.Field(default=None, title="Flip")
    flop: typing.Optional[bool] = pydantic.Field(default=None, title="Flop")
    original_image_height: typing.Optional[int] = pydantic.Field(
        default=None, title="Original Image Height"
    )
    original_image_width: typing.Optional[int] = pydantic.Field(
        default=None, title="Original Image Width"
    )


class ImageTransformation(pydantic.BaseModel):
    """An image transformation is a visualisation created by transforming an image file."""

    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="ImageTransformation", title="Visualisation Type"
    )
    visualisation_configuration_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Annotatable Id"
    )
    annotatable_type: typing.Optional[DataBaseObjectType] = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: TransformationParameters = pydantic.Field(
        title="TransformationParameters"
    )
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")


class Video(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="Video", title="Visualisation Type"
    )
    visualisation_configuration_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Annotatable Id"
    )
    annotatable_type: typing.Optional[DataBaseObjectType] = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: typing.Optional[VideoParameters] = pydantic.Field(
        default=None, title="VideoParameters"
    )
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")


class Tile(pydantic.BaseModel):
    """A special case of cropping, where the image is cropped into multiple tiles."""

    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(default="Tile", title="Visualisation Type")
    visualisation_configuration_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Annotatable Id"
    )
    annotatable_type: typing.Optional[DataBaseObjectType] = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: TransformationParameters = pydantic.Field(
        title="TransformationParameters"
    )
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")


class RenderedVisualisation(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default="2024-06-30T23:04:12.478027", title="Timestamp"
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    visualisation_type: str = pydantic.Field(
        default="Rendered", title="Visualisation Type"
    )
    visualisation_configuration_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Annotatable Id"
    )
    annotatable_type: typing.Optional[DataBaseObjectType] = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: typing.Optional[VisualisationParameters] = pydantic.Field(
        default=None, title="VisualisationParameters"
    )
    media_url: str = pydantic.Field(title="Media Url")


class Media(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default=None,
        title="Timestamp",
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    back_reference: str = pydantic.Field(title="Back Reference")
    subset_ids: list = pydantic.Field(default=[], title="Subset Ids")
    attributes: list = pydantic.Field(default=[], title="Attributes")
    thumbnails: dict[str, typing.Any] = pydantic.Field(default={}, title="Thumbnails")
    visualisations: typing.Optional[list[VisualisationUnion]] = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: typing.Optional[str] = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str = pydantic.Field(default="Media", title="Type")
    media_url: str = pydantic.Field(title="Media Url")
    pii_media_url: str = pydantic.Field(title="Pii Media Url")
    name: str = pydantic.Field(title="Name")
    metadata: typing.Optional[
        typing.Union[ImageMetadata, PointCloudMetadata]
    ] = pydantic.Field(default=None, title="ImageMetadata")
    frame_idx: typing.Optional[int] = pydantic.Field(default=None, title="Frame Idx")
    media_type: typing.Optional[MediaType] = pydantic.Field(
        default=None, title="MediaType"
    )
    frame_timestamp: typing.Optional[str] = pydantic.Field(
        default=None, title="Frame Timestamp"
    )
    back_reference_json: typing.Optional[str] = pydantic.Field(
        default=None, title="Back Reference Json"
    )


class MediaResponse(pydantic.BaseModel):
    id: typing.Optional[str] = pydantic.Field(default=None, title="Id")
    dataset_id: typing.Optional[str] = pydantic.Field(default=None, title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: typing.Optional[str] = pydantic.Field(default=None, title="Timestamp")
    archived: typing.Optional[bool] = pydantic.Field(default=None, title="Archived")
    back_reference: typing.Optional[str] = pydantic.Field(
        default=None, title="Back Reference"
    )
    subset_ids: typing.Optional[list] = pydantic.Field(default=None, title="Subset Ids")
    attributes: typing.Optional[list] = pydantic.Field(default=None, title="Attributes")
    thumbnails: typing.Optional[dict[str, typing.Any]] = pydantic.Field(
        default=None, title="Thumbnails"
    )
    visualisations: typing.Optional[list[VisualisationUnion]] = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: typing.Optional[str] = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: typing.Optional[str] = pydantic.Field(default=None, title="Type")
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")
    pii_media_url: typing.Optional[str] = pydantic.Field(
        default=None, title="Pii Media Url"
    )
    name: typing.Optional[str] = pydantic.Field(default=None, title="Name")
    metadata: typing.Optional[
        typing.Union[ImageMetadata, PointCloudMetadata]
    ] = pydantic.Field(default=None, title="ImageMetadata")
    frame_idx: typing.Optional[int] = pydantic.Field(default=None, title="Frame Idx")
    media_type: typing.Optional[MediaType] = pydantic.Field(
        default=None, title="MediaType"
    )
    frame_timestamp: typing.Optional[str] = pydantic.Field(
        default=None, title="Frame Timestamp"
    )
    back_reference_json: typing.Optional[str] = pydantic.Field(
        default=None, title="Back Reference Json"
    )


class FilterCount(pydantic.BaseModel):
    false_negative_percentage: typing.Optional[typing.Any] = pydantic.Field(
        default=None, title="False Negative Percentage"
    )
    false_positive_percentage: typing.Optional[typing.Any] = pydantic.Field(
        default=None, title="False Positive Percentage"
    )
    total_count: int = pydantic.Field(title="Total Count")


class RenderedVisualisationConfigParameters(pydantic.BaseModel):
    type: str = pydantic.Field(default="rendered", title="Type")


class TileVisualisationConfigParameters(pydantic.BaseModel):
    type: str = pydantic.Field(default="tile", title="Type")
    columns: int = pydantic.Field(title="Columns")
    rows: int = pydantic.Field(title="Rows")
    overlap_percent: typing.Any = pydantic.Field(title="Overlap Percent")


class LidarVideoStackedVisualisationConfigParameters(pydantic.BaseModel):
    type: str = pydantic.Field(default="lidar_video_stacked", title="Type")


class LidarVideoVisualisationConfigParameters(pydantic.BaseModel):
    type: str = pydantic.Field(default="lidar_video", title="Type")


class CropVisualisationConfigParameters(pydantic.BaseModel):
    type: str = pydantic.Field(default="crop", title="Type")
    padding_percent: int = pydantic.Field(title="Padding Percent")
    padding_minimum: int = pydantic.Field(title="Padding Minimum")
    max_size: typing.Optional[list] = pydantic.Field(default=None, title="Max Size")
    aspect_ratio: typing.Optional[list] = pydantic.Field(
        default=None, title="Aspect Ratio"
    )


class VisualisationConfiguration(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(default=None, title="Timestamp")
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    name: str = pydantic.Field(title="Name")
    parameters: typing.Union[
        CropVisualisationConfigParameters,
        LidarVideoVisualisationConfigParameters,
        LidarVideoStackedVisualisationConfigParameters,
        TileVisualisationConfigParameters,
        RenderedVisualisationConfigParameters,
    ] = pydantic.Field(title="CropVisualisationConfigParameters")
    subset_ids: list = pydantic.Field(title="Subset Ids")


class Visualisation(pydantic.BaseModel):
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
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(
        default=None,
        title="Timestamp",
    )
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    visualisation_type: VisualisationType = pydantic.Field(title="VisualisationType")
    visualisation_configuration_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Visualisation Configuration Id"
    )
    annotatable_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Annotatable Id"
    )
    annotatable_type: typing.Optional[DataBaseObjectType] = pydantic.Field(
        default=None, title="DataBaseObjectType"
    )
    parameters: typing.Optional[VisualisationParameters] = pydantic.Field(
        default=None, title="VisualisationParameters"
    )
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")


class MediaObject(pydantic.BaseModel):
    id: str = pydantic.Field(title="Id")
    dataset_id: str = pydantic.Field(title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: str = pydantic.Field(default=None, title="Timestamp")
    archived: typing.Optional[bool] = pydantic.Field(default=False, title="Archived")
    back_reference: str = pydantic.Field(title="Back Reference")
    subset_ids: list = pydantic.Field(default=[], title="Subset Ids")
    attributes: list = pydantic.Field(default=[], title="Attributes")
    thumbnails: dict[str, typing.Any] = pydantic.Field(default={}, title="Thumbnails")
    visualisations: typing.Optional[list[VisualisationUnion]] = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: typing.Optional[str] = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: str = pydantic.Field(default="MediaObject", title="Type")
    media_id: str = pydantic.Field(title="Media Id")
    media_url: str = pydantic.Field(title="Media Url")
    crop_url: str = pydantic.Field(default=None, title="Crop Url")
    object_category: typing.Optional[str] = pydantic.Field(
        default=None, title="Object Category"
    )
    source: DataSource = pydantic.Field(title="DataSource")
    qm_data: typing.Optional[list[GeometryUnion]] = pydantic.Field(
        default=None, title="QM sourced geometry object"
    )
    reference_data: typing.Optional[GeometryUnion] = pydantic.Field(
        default=None, title="Externally sourced geometry object"
    )
    frame_idx: typing.Optional[int] = pydantic.Field(default=None, title="Frame Idx")
    instance_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Instance Id"
    )
    media_object_type: typing.Optional[MediaObjectType] = pydantic.Field(
        default=None, title="Media Object Type"
    )


class MediaObjectResponse(pydantic.BaseModel):
    id: typing.Optional[str] = pydantic.Field(default=None, title="Id")
    dataset_id: typing.Optional[str] = pydantic.Field(default=None, title="Dataset Id")
    tags: typing.Optional[list] = pydantic.Field(default=None, title="Tags")
    timestamp: typing.Optional[str] = pydantic.Field(default=None, title="Timestamp")
    archived: typing.Optional[bool] = pydantic.Field(default=None, title="Archived")
    back_reference: typing.Optional[str] = pydantic.Field(
        default=None, title="Back Reference"
    )
    subset_ids: typing.Optional[list] = pydantic.Field(default=None, title="Subset Ids")
    attributes: typing.Optional[list] = pydantic.Field(default=None, title="Attributes")
    thumbnails: typing.Optional[dict[str, typing.Any]] = pydantic.Field(
        default=None, title="Thumbnails"
    )
    visualisations: typing.Optional[list[VisualisationUnion]] = pydantic.Field(
        default=None, title="Visualisations"
    )
    scene_id: typing.Optional[str] = pydantic.Field(default=None, title="Scene Id")
    realWorldObject_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Realworldobject Id"
    )
    type: typing.Optional[str] = pydantic.Field(default=None, title="Type")
    media_id: typing.Optional[str] = pydantic.Field(default=None, title="Media Id")
    media_url: typing.Optional[str] = pydantic.Field(default=None, title="Media Url")
    crop_url: typing.Optional[str] = pydantic.Field(default=None, title="Crop Url")
    object_category: typing.Optional[str] = pydantic.Field(
        default=None, title="Object Category"
    )
    source: typing.Optional[DataSource] = pydantic.Field(
        default=None, title="DataSource"
    )
    qm_data: typing.Optional[list[GeometryUnion]] = pydantic.Field(
        default=None, title="QM sourced geometry object"
    )
    reference_data: typing.Optional[GeometryUnion] = pydantic.Field(
        default=None, title="Externally sourced geometry object"
    )
    frame_idx: typing.Optional[int] = pydantic.Field(default=None, title="Frame Idx")
    instance_id: typing.Optional[str] = pydantic.Field(
        default=None, title="Instance Id"
    )
    media_object_type: typing.Optional[MediaObjectType] = pydantic.Field(
        default=None, title="Media Object Type"
    )


class ValidationError(pydantic.BaseModel):
    loc: list = pydantic.Field(title="Location")
    msg: str = pydantic.Field(title="Message")
    type: str = pydantic.Field(title="Error Type")


class AttributeGroup(str, enum.Enum):
    AnnotationAttribute = "annotation_attribute"
    MlAnnotationAttribute = "ml_annotation_attribute"
    AutoAttribute = "auto_attribute"
    InitialAttribute = "initial_attribute"
    InheritedAnnotationAttribute = "inherited_annotation_attribute"


class HistogramType(str, enum.Enum):
    boolean = "BOOLEAN"
    categorical = "CATEGORICAL"
    numerical = "NUMERICAL"
    subset = "SUBSET"


class AttributeHistogramStatistics(pydantic.BaseModel):
    variance: float
    average: float
    quantiles_25: float
    quantiles_50: float
    quantiles_75: float
    interquartile_range: float
    shapiro_p_value: typing.Optional[float] = None


class AttributeHistogram(pydantic.BaseModel):
    attribute_id: str
    attribute_name: str
    filter_name: str
    type: HistogramType
    attribute_group: AttributeGroup
    dataset_id: str
    subset_id: typing.Optional[str] = None
    num_buckets: typing.Optional[int] = None
    lower: typing.Optional[float] = None
    upper: typing.Optional[float] = None
    interval: typing.Optional[float] = None
    buckets: list[tuple[typing.Union[int, float, str], int]]
    cant_solves: int = 0
    corrupt_data: int = 0
    statistics: typing.Optional[AttributeHistogramStatistics] = None


class MediaUploadUrlInfo(pydantic.BaseModel):
    upload_url: str
    media_id: str
    media_url: str


class VisualisationUploadUrlInfo(pydantic.BaseModel):
    upload_url: str
    visualisation_id: str
    visualisation_url: str


VisualisationUnion = typing.Union[
    ImageTransformation, Video, Tile, RenderedVisualisation
]
GeometryUnion = typing.Union[
    BBox2DCenterPoint,
    Point2DXY,
    PolyLine2DFlatCoordinates,
    CuboidCenterPoint,
    Point3DXYZ,
    BoundingBox2DAggregation,
    Point2DAggregation,
    Point3DAggregation,
]


class ProcessingType(str, enum.Enum):
    LOCAL = "local"
    REMOTE = "remote"


class ResponseBaseParameters(pydantic.BaseModel):
    batch: bool = pydantic.Field(default=False, title="Batch")
    override_processing_type: typing.Optional[ProcessingType] = pydantic.Field(
        default=None, title="Override Processing Type"
    )
    task_token: typing.Optional[str] = pydantic.Field(default=None, title="Task Token")
    job_id: typing.Optional[uuid.UUID] = pydantic.Field(default=None, title="Job ID")
    trace_id: typing.Optional[uuid.UUID] = pydantic.Field(
        default=None, title="Trace ID"
    )
    user_id: typing.Optional[uuid.UUID] = pydantic.Field(default=None, title="User ID")
    user_group: typing.Optional[str] = pydantic.Field(default=None, title="User Group")


class CreateThumbnailsParameters(pydantic.BaseModel):
    dataset_id: str = pydantic.Field(title="Dataset ID")
    query: typing.Optional[QueryList] = pydantic.Field(default=None, title="Query")
    pagination: typing.Optional[PaginationParameter] = pydantic.Field(
        default=None, title="Pagination"
    )
    upload_folder_name: str = pydantic.Field(
        default="thumbnails", title="Upload Folder Name"
    )
    s3_bucket: typing.Optional[str] = pydantic.Field(default=None, title="S3 Bucket")
    s3_folder: typing.Optional[str] = pydantic.Field(default=None, title="S3 Folder")
    max_size: typing.Optional[tuple[int, int]] = pydantic.Field(
        default=None, title="Max Size"
    )
    aspect_ratio: tuple[int, int] = pydantic.Field(title="Aspect Ratio")
    calc_and_write_image_info: bool = pydantic.Field(
        default=True, title="Calculate and Write Image Info"
    )


class CreateThumbnailsResponse(ResponseBaseParameters):
    method_name: typing.Literal["create_thumbnails"] = pydantic.Field(
        default="create_thumbnails", title="Method Name"
    )
    parameters: CreateThumbnailsParameters = pydantic.Field(title="Parameters")


class UpdateHistogramsParameters(pydantic.BaseModel):
    dataset_id: str = pydantic.Field(title="Dataset ID")
    subset_ids: typing.Optional[list[str]] = pydantic.Field(
        default=None, title="Subset IDs"
    )
    attribute_ids: typing.Optional[list[str]] = pydantic.Field(
        default=None, title="Attribute IDs"
    )
    num_buckets: int = pydantic.Field(default=360, title="Number of Buckets")
    ignore_complete_dataset_histogram: bool = pydantic.Field(
        default=False, title="Ignore Complete Dataset Histogram"
    )
    compute_for_all_subsets: bool = pydantic.Field(
        default=False, title="Compute for All Subsets"
    )


class UpdateHistogramsResponse(ResponseBaseParameters):
    method_name: typing.Literal["update_histograms"] = pydantic.Field(
        default="update_histograms", title="Method Name"
    )
    parameters: UpdateHistogramsParameters = pydantic.Field(title="Parameters")


class CreateCropsParameters(pydantic.BaseModel):
    dataset_id: str = pydantic.Field(title="Dataset ID")
    query: typing.Optional[QueryList] = pydantic.Field(default=None, title="Query")
    pagination: typing.Optional[PaginationParameter] = pydantic.Field(
        default=None, title="Pagination"
    )
    upload_folder_name: str = pydantic.Field(
        default="cropped_image", title="Upload Folder Name"
    )
    s3_bucket: typing.Optional[str] = pydantic.Field(default=None, title="S3 Bucket")
    s3_folder: typing.Optional[str] = pydantic.Field(default=None, title="S3 Folder")
    aspect_ratio: tuple[int, int] = pydantic.Field(title="Aspect Ratio")
    padding_percent: int = pydantic.Field(title="Padding Percent")
    padding_minimum: int = pydantic.Field(title="Padding Minimum")
    max_size: typing.Optional[tuple[int, int]] = pydantic.Field(
        default=None, title="Max Size"
    )


class CreateCropsResponse(ResponseBaseParameters):
    method_name: typing.Literal["create_crops"] = pydantic.Field(
        default="create_crops", title="Method Name"
    )
    parameters: CreateCropsParameters = pydantic.Field(title="Parameters")
