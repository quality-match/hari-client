import pytest

from hari_client import Config
from hari_client import HARIClient

pytest_plugins = [
    "tests.upload.fixtures",
]


@pytest.fixture()
def test_client():
    test_config = Config(
        hari_username="username",
        hari_password="password",
        hari_api_base_url="api_base_url",
        hari_client_id="client_id",
        hari_auth_url="auth_url",
    )
    yield HARIClient(config=test_config)
