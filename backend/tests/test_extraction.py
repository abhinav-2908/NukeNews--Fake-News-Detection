import pytest
from app.extraction.url import _check_url

def test_blocks_loopback():
    with pytest.raises(ValueError): _check_url('http://127.0.0.1/admin')

def test_blocks_non_http():
    with pytest.raises(ValueError): _check_url('file:///etc/passwd')
