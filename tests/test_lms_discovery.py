import pytest

from lms_discovery import parse_lms_response, LMS_QUERY


def test_query_is_bytes():
    assert LMS_QUERY == b"eJSON\x00"


def test_parse_extracts_port_from_json_field():
    # LMS responds with "E" followed by tag-length-value triples;
    # JSON tag is "JSON", value is the port as ASCII.
    payload = b"E" + b"JSON" + b"\x049000"
    assert parse_lms_response(payload) == 9000


def test_parse_returns_none_for_non_E_payload():
    assert parse_lms_response(b"XJSON\x049000") is None


def test_parse_returns_none_when_no_json_tag():
    assert parse_lms_response(b"E") is None


def test_parse_handles_extra_tags():
    # Real LMS responses may carry additional tags before/after JSON
    payload = b"E" + b"NAME\x06Server" + b"JSON\x049000"
    assert parse_lms_response(payload) == 9000
