from urllib.parse import urlparse, urljoin
from flask import request


def is_safe_url(target: str) -> bool:
    """Ensure a redirect target URL is safe and points to the same host."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
