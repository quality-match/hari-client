import pydantic
import pydantic_settings

MEDIA_BULK_UPLOAD_LIMIT = 500
MEDIA_OBJECT_BULK_UPLOAD_LIMIT = 5000
ATTRIBUTE_BULK_UPLOAD_LIMIT = 750
PRESIGNED_URL_MAX_BATCH_SIZE = MEDIA_BULK_UPLOAD_LIMIT


class HARIUploaderConfig(pydantic.BaseModel):
    media_upload_batch_size: int = pydantic.Field(
        default=500, ge=1, le=MEDIA_BULK_UPLOAD_LIMIT
    )
    media_object_upload_batch_size: int = pydantic.Field(
        default=5000, ge=1, le=MEDIA_OBJECT_BULK_UPLOAD_LIMIT
    )
    attribute_upload_batch_size: int = pydantic.Field(
        default=750, ge=1, le=ATTRIBUTE_BULK_UPLOAD_LIMIT
    )


class Config(pydantic_settings.BaseSettings):
    """
     This class contains configuration for usage of the HARIApiClient.

     You have 3 options to work with this class:

    1. Pass the settings directly when instantiating the Config object

       `config = Config(hari_username="MY_USERNAME", hari_password="MY_PASSWORD")`

    2. Specify a `.env` file in the working directory of your script,
       then the Config object will automatically try to read its settings from there.

       `config = Config()`

    3. Specify the `.env` file path explicitly when instantiating the Config object.
       This way you can specify a specific .env file just for this config and
       can keep it in any location.

    `config = Config(_env_file='prod.env')`

    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__"
    )

    hari_api_base_url: str = "https://api.hari.quality-match.com"
    hari_client_id: str = "baked_beans_frontend"
    hari_auth_url: str = "https://auth.quality-match.com/auth"
    hari_username: str
    hari_password: str
    hari_uploader: HARIUploaderConfig = HARIUploaderConfig()
