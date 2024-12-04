import pytest

from hari_client import Config
from hari_client import HARIClient
from hari_client import HARIUploaderConfig
from tests.upload.fixtures import *  # noqa


@pytest.fixture()
def test_client():
    test_config = Config(
        hari_username="username",
        hari_password="password",
        hari_api_base_url="api_base_url",
        hari_client_id="client_id",
        hari_auth_url="auth_url",
        # tests related to batching were written before batch size
        # was configurable, so use the old default 500 for all tests
        # using the test_client fixture
        hari_uploader=HARIUploaderConfig(
            media_upload_batch_size=500,
            media_object_upload_batch_size=500,
            attribute_upload_batch_size=500,
        ),
    )
    yield HARIClient(config=test_config)
