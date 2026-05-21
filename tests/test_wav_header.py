import struct

from wav import build_wav_header


def test_header_starts_with_riff():
    header, total_size = build_wav_header(duration=10)
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"


def test_header_format_chunk_is_pcm_stereo_44100_16bit():
    header, _ = build_wav_header(duration=10)
    fmt_chunk = header[12:36]
    assert fmt_chunk[:4] == b"fmt "
    (chunk_size, audio_format, channels, samplerate, byterate,
     blockalign, bitspersample) = struct.unpack("<LHHLLHH", fmt_chunk[4:])
    assert chunk_size == 16
    assert audio_format == 1  # PCM
    assert channels == 2
    assert samplerate == 44100
    assert bitspersample == 16
    assert byterate == 44100 * 2 * 2
    assert blockalign == 2 * 2


def test_total_size_matches_data_chunk():
    duration = 5
    header, total_size = build_wav_header(duration=duration)
    # 2 extra seconds added for crossfade
    expected_samples = 44100 * (duration + 2)
    expected_datasize = expected_samples * 2 * 2
    # total_size = 44 byte header + data
    assert total_size == 44 + expected_datasize


def test_header_returns_bytes_not_str():
    header, _ = build_wav_header(duration=1)
    assert isinstance(header, bytes)
