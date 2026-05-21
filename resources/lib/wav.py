"""Pure-function WAV header builder for the silent-stream HTTP proxy."""
import struct


def build_wav_header(duration):
    """Build a PCM WAV header for `duration` seconds of stereo 44.1 kHz 16-bit audio.

    Adds 2 seconds of padding to avoid Kodi crossfade truncation. Returns
    (header_bytes, total_file_size_bytes).
    """
    duration += 2
    channels = 2
    samplerate = 44100
    bitspersample = 16
    numsamples = samplerate * duration
    bytes_per_sample = bitspersample // 8
    datasize = numsamples * channels * bytes_per_sample

    fmt_chunk = struct.pack(
        "<4sLHHLLHH",
        b"fmt ",
        16,
        1,
        channels,
        samplerate,
        samplerate * channels * bytes_per_sample,
        channels * bytes_per_sample,
        bitspersample,
    )
    data_chunk = struct.pack("<4sL", b"data", int(datasize))

    riff_size = 4 + len(fmt_chunk) + len(data_chunk) + datasize
    main_header = struct.pack("<4sL4s", b"RIFF", riff_size, b"WAVE")

    header = main_header + fmt_chunk + data_chunk
    total_size = riff_size + 8  # +8 for "RIFF" + size field
    return header, total_size


def silent_stream_chunks(header, payload_size, max_buffer=8192):
    """Yield the WAV header followed by `payload_size` zero bytes in chunks of
    at most `max_buffer` bytes."""
    yield header
    written = 0
    zeros = b"\x00" * max_buffer
    while written < payload_size:
        remaining = payload_size - written
        if remaining >= max_buffer:
            yield zeros
            written += max_buffer
        else:
            yield b"\x00" * remaining
            written = payload_size
