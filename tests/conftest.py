import pytest

from hari_client import Config
from hari_client import HARIClient
from tests.upload.fixtures import *  # noqa


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


@pytest.fixture()
def test_client_mocked(test_client: HARIClient, mocker):
    """Returns hari-client for testing that has the internal _request method mocked.
    All endpoint methods to hari will return an empty dict.
    Note that this doesn't cover media file upload related methods.
    """
    mocker.patch.object(test_client, "_request", return_value={})
    yield test_client
