from pathlib import Path

from server.app.processing.pbr_pack import MaterialTextureSpec, generate_mock_texture_sets
from server.tests.png_utils import read_png_first_pixel


def test_mock_texture_set_fallbacks_and_orm(tmp_path: Path) -> None:
    textures = generate_mock_texture_sets(
        tmp_path,
        [MaterialTextureSpec(name="wall_concrete", metallic=0.25)],
        texture_size=2,
    )

    material_textures = textures["wall_concrete"]
    assert set(material_textures) == {"basecolor", "normal", "roughness", "ao", "metallic", "orm"}

    assert read_png_first_pixel((tmp_path / material_textures["normal"]).read_bytes()) == (128, 128, 255)
    assert read_png_first_pixel((tmp_path / material_textures["ao"]).read_bytes()) == (255, 255, 255)
    assert read_png_first_pixel((tmp_path / material_textures["roughness"]).read_bytes()) == (179, 179, 179)
    assert read_png_first_pixel((tmp_path / material_textures["metallic"]).read_bytes()) == (64, 64, 64)
    assert read_png_first_pixel((tmp_path / material_textures["orm"]).read_bytes()) == (255, 179, 64)
