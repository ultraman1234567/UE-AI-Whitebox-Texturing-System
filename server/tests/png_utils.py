import struct
import zlib


def read_png_first_pixel(data: bytes) -> tuple[int, int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = 0
    idat = b""
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, _height, bit_depth, color_type, *_ = struct.unpack(">IIBBBBB", chunk_data)
            assert bit_depth == 8
            assert color_type == 2
        elif chunk_type == b"IDAT":
            idat += chunk_data
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(idat)
    assert raw[0] == 0
    assert width > 0
    return tuple(raw[1:4])
