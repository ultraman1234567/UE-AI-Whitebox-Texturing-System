"""Mock PBR map generation and ORM packing.

The local milestone intentionally uses deterministic generated PNGs instead of
GPU models. Real providers can later feed source maps into the same naming and
packing contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import struct
import zlib

from .validation import sanitize_material_name


@dataclass(frozen=True)
class MaterialTextureSpec:
    name: str
    metallic: float = 0.0


TEXTURE_KEYS = ("basecolor", "normal", "roughness", "ao", "metallic", "orm")
TEXTURE_SUFFIXES = {
    "basecolor": "BaseColor",
    "normal": "Normal",
    "roughness": "Roughness",
    "ao": "AO",
    "metallic": "Metallic",
    "orm": "ORM",
}


def generate_mock_texture_sets(
    job_dir: Path,
    materials: list[MaterialTextureSpec],
    texture_size: int,
) -> dict[str, dict[str, str]]:
    if texture_size < 1:
        raise ValueError("texture_size must be at least 1")

    outputs: dict[str, dict[str, str]] = {}
    textures_root = job_dir / "textures"
    textures_root.mkdir(parents=True, exist_ok=True)

    for material in materials:
        material_name = sanitize_material_name(material.name)
        material_dir = textures_root / material_name
        material_dir.mkdir(parents=True, exist_ok=True)
        metallic = _float_to_byte(material.metallic)

        colors = {
            "basecolor": _basecolor_for_name(material_name),
            "normal": (128, 128, 255),
            "roughness": _gray(_float_to_byte(0.7)),
            "ao": _gray(255),
            "metallic": _gray(metallic),
            "orm": (255, _float_to_byte(0.7), metallic),
        }

        outputs[material_name] = {}
        for key in TEXTURE_KEYS:
            suffix = TEXTURE_SUFFIXES[key]
            filename = f"T_{material_name}_{suffix}.png"
            output_path = material_dir / filename
            write_solid_rgb_png(output_path, texture_size, texture_size, colors[key])
            outputs[material_name][key] = f"textures/{material_name}/{filename}"

    return outputs


def generate_texture_set_from_sources(
    job_dir: Path,
    material: MaterialTextureSpec,
    sources: dict[str, Path],
    texture_size: int,
) -> dict[str, str]:
    material_name = sanitize_material_name(material.name)
    material_dir = job_dir / "textures" / material_name
    material_dir.mkdir(parents=True, exist_ok=True)

    width, height = _source_size(sources, texture_size)
    metallic = _float_to_byte(material.metallic)
    output_paths: dict[str, str] = {}

    fallback_colors = {
        "basecolor": _basecolor_for_name(material_name),
        "normal": (128, 128, 255),
        "roughness": _gray(_float_to_byte(0.7)),
        "ao": _gray(255),
        "metallic": _gray(metallic),
    }

    for key in ("basecolor", "normal", "roughness", "ao", "metallic"):
        suffix = TEXTURE_SUFFIXES[key]
        filename = f"T_{material_name}_{suffix}.png"
        output_path = material_dir / filename
        source = sources.get(key)
        if source and source.is_file() and source.suffix.lower() == ".png" and _is_readable_png(source):
            shutil.copyfile(source, output_path)
        else:
            write_solid_rgb_png(output_path, width, height, fallback_colors[key])
        output_paths[key] = f"textures/{material_name}/{filename}"

    orm_filename = f"T_{material_name}_ORM.png"
    orm_path = material_dir / orm_filename
    pack_orm_png(
        job_dir / output_paths["ao"],
        job_dir / output_paths["roughness"],
        job_dir / output_paths["metallic"],
        orm_path,
    )
    output_paths["orm"] = f"textures/{material_name}/{orm_filename}"
    return output_paths


def pack_orm_png(ao_path: Path, roughness_path: Path, metallic_path: Path, output_path: Path) -> None:
    width, height, ao = read_rgb_png(ao_path)
    rough_width, rough_height, roughness = read_rgb_png(roughness_path)
    metal_width, metal_height, metallic = read_rgb_png(metallic_path)
    if (rough_width, rough_height) != (width, height) or (metal_width, metal_height) != (width, height):
        raise ValueError("ORM source dimensions do not match")

    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            idx = y * width + x
            row.extend([ao[idx][0], roughness[idx][0], metallic[idx][0]])
        rows.append(bytes(row))

    raw = b"".join(rows)
    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw)),
            _png_chunk(b"IEND", b""),
        ]
    )
    output_path.write_bytes(png)


def read_rgb_png(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"not a PNG file: {path}")

    offset = 8
    width = 0
    height = 0
    color_type = -1
    idat = b""
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk_data)
            if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("unsupported PNG format")
        elif chunk_type == b"IDAT":
            idat += chunk_data
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(idat)
    pixels: list[tuple[int, int, int]] = []
    if color_type == 2:
        stride = width * 3
        for y in range(height):
            start = y * (stride + 1)
            if raw[start] != 0:
                raise ValueError("unsupported PNG filter")
            row = raw[start + 1 : start + 1 + stride]
            for x in range(width):
                i = x * 3
                pixels.append((row[i], row[i + 1], row[i + 2]))
    elif color_type == 0:
        stride = width
        for y in range(height):
            start = y * (stride + 1)
            if raw[start] != 0:
                raise ValueError("unsupported PNG filter")
            row = raw[start + 1 : start + 1 + stride]
            for value in row:
                pixels.append((value, value, value))
    else:
        raise ValueError("unsupported PNG color type")
    return width, height, pixels


def write_solid_rgb_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = bytes([0]) + bytes(color) * width
    raw = row * height
    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(png)


def _source_size(sources: dict[str, Path], fallback_size: int) -> tuple[int, int]:
    for key in ("basecolor", "normal", "roughness", "ao", "metallic"):
        source = sources.get(key)
        if source and source.is_file() and source.suffix.lower() == ".png":
            try:
                width, height, _pixels = read_rgb_png(source)
                return width, height
            except ValueError:
                continue
    return fallback_size, fallback_size


def _is_readable_png(path: Path) -> bool:
    try:
        read_rgb_png(path)
        return True
    except ValueError:
        return False


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _basecolor_for_name(material_name: str) -> tuple[int, int, int]:
    digest = hashlib.sha1(material_name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _float_to_byte(value: float) -> int:
    clamped = max(0.0, min(1.0, float(value)))
    return int(clamped * 255 + 0.5)


def _gray(value: int) -> tuple[int, int, int]:
    return (value, value, value)
