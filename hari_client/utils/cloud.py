import re
from urllib.parse import urlparse


def parse_file_key(storage_url: str) -> str:
    """
    Extracts the file key (path) from an S3 or Azure Blob Storage URL.

    Supports:
    - S3 virtual-hosted-style URLs (e.g., https://bucket.s3.amazonaws.com/path/to/image.png)
    - S3 path-style URLs (e.g., https://s3.amazonaws.com/bucket/path/to/image.png)
    - Azure Blob Storage URLs (e.g., https://account.blob.core.windows.net/container/path/to/image.png)

    Args:
        storage_url: The storage URL to parse

    Returns:
        str: Extracted file key (path within the bucket/container)
    """
    parsed_url = urlparse(storage_url)

    if "s3" in parsed_url.netloc:
        # Handle S3 virtual-hosted-style URLs (bucket.s3.amazonaws.com)
        match = re.match(r"^(.*?)\.s3.*\.amazonaws\.com$", parsed_url.hostname or "")
        if match:
            return parsed_url.path.lstrip("/")

        # Handle S3 path-style URLs (s3.amazonaws.com/bucket/key)
        path_parts = parsed_url.path.lstrip("/").split("/", 1)
        if len(path_parts) > 1:
            return path_parts[1]

    elif "blob.core.windows.net" in parsed_url.netloc:
        # Azure Blob Storage format: https://account.blob.core.windows.net/container/path/to/image.png
        path_parts = parsed_url.path.lstrip("/").split("/", 1)
        if len(path_parts) > 1:
            return path_parts[1]

    # Default return for unhandled cases
    return parsed_url.path.lstrip("/")
