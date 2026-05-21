from wav import silent_stream_chunks


def test_yields_header_first():
    chunks = list(silent_stream_chunks(b"HEADER", payload_size=10, max_buffer=4))
    assert chunks[0] == b"HEADER"


def test_payload_is_zero_bytes_summing_to_size():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=10, max_buffer=4))
    payload = b"".join(chunks[1:])
    assert len(payload) == 10
    assert payload == b"\x00" * 10


def test_chunks_respect_max_buffer():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=10, max_buffer=4))
    # header + ceil(10/4) = 1 + 3 = 4
    assert len(chunks) == 4
    assert all(len(c) <= 4 for c in chunks[1:])


def test_zero_payload():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=0, max_buffer=4))
    assert chunks == [b"HDR"]
