import pytest

from hari_client.utils import cloud


@pytest.mark.parametrize(
    "url, expected",
    [
        # S3 virtual-hosted style URLs
        ("https://my-bucket.s3.amazonaws.com/folder/image.png", "folder/image.png"),
        ("https://another-bucket.s3.us-east-1.amazonaws.com/image.png", "image.png"),
        # S3 path-style URLs
        ("https://s3.amazonaws.com/my-bucket/folder/image.png", "folder/image.png"),
        (
            "https://s3.us-west-2.amazonaws.com/bucket-name/dir/image.png",
            "dir/image.png",
        ),
        # Azure Blob Storage URLs
        (
            "https://mystorageaccount.blob.core.windows.net/mycontainer/path/to/image.png",
            "path/to/image.png",
        ),
        (
            "https://storage.blob.core.windows.net/container-name/some/deeply/nested/file.png",
            "some/deeply/nested/file.png",
        ),
        # Edge cases
        ("https://s3.amazonaws.com/bucket/", ""),  # Root of bucket
        ("https://my-bucket.s3.amazonaws.com/", ""),  # Empty key
        ("https://account.blob.core.windows.net/container/", ""),  # Empty Azure key
    ],
)
def test_parse_file_key(url, expected):
    assert cloud.parse_file_key(url) == expected
