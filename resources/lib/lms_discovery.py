"""LMS UDP discovery — parse the server reply payload.

LMS broadcast protocol: client sends b"eJSON\x00" to port 3483.
Server replies starting with b"E" followed by tag/length/value triples.
The JSON tag value is the JSON-RPC port (ASCII).
"""

LMS_QUERY = b"eJSON\x00"
LMS_PORT = 3483


def parse_lms_response(data):
    """Return the JSON-RPC port from an LMS discovery reply, or None."""
    if not data or not data.startswith(b"E"):
        return None
    idx = data.find(b"JSON")
    if idx < 0 or idx + 5 > len(data):
        return None
    length = data[idx + 4]
    start = idx + 5
    end = start + length
    if end > len(data):
        return None
    try:
        return int(data[start:end])
    except ValueError:
        return None
