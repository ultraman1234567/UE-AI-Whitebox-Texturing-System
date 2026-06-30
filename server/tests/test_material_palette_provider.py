from pathlib import Path

from server.app.processing.pbr_pack import write_solid_rgb_png
from server.app.providers.pbr.base import PBRGenerationRequest, PBRMaterialRequest
from server.app.providers.pbr.material_palette_provider import (
    MaterialPaletteConfig,
    MaterialPaletteProvider,
    collect_material_outputs,
)
from server.tests.png_utils import read_png_first_pixel


def test_collect_material_outputs_keyword_search(tmp_path: Path) -> None:
    output_dir = tmp_path / "mp_out"
    output_dir.mkdir()
    albedo = output_dir / "wall_concrete_base_color.png"
    normal = output_dir / "wall_concrete_nrm.png"
    rough = output_dir / "wall_concrete_rough.png"
    other = output_dir / "floor_tiles_albedo.png"
    for path in [albedo, normal, rough, other]:
        write_solid_rgb_png(path, 2, 2, (10, 10, 10))

    sources = collect_material_outputs(output_dir, "wall_concrete")

    assert sources["basecolor"] == albedo
    assert sources["normal"] == normal
    assert sources["roughness"] == rough


def test_material_palette_provider_fake_output_and_fallback_maps(tmp_path: Path) -> None:
    job_dir = _make_job_dir(tmp_path)
    output_dir = job_dir / "fake_mp_output"
    material_dir = output_dir / "wall_concrete"
    material_dir.mkdir(parents=True)
    write_solid_rgb_png(material_dir / "wall_concrete_albedo.png", 2, 2, (11, 22, 33))
    write_solid_rgb_png(material_dir / "wall_concrete_normal.png", 2, 2, (128, 128, 255))
    write_solid_rgb_png(material_dir / "wall_concrete_roughness.png", 2, 2, (51, 51, 51))

    provider = MaterialPaletteProvider(
        MaterialPaletteConfig(
            command_template='python -c "print(\'fake material palette\')"',
            output_dir=str(output_dir),
            timeout=30,
        )
    )
    result = provider.generate(
        PBRGenerationRequest(
            texture_size=2,
            materials=[PBRMaterialRequest(name="wall_concrete", metallic=0.25)],
            fallback_to_mock=False,
        ),
        job_dir,
    )

    textures = result.textures["wall_concrete"]
    assert result.provider == "material_palette"
    assert read_png_first_pixel((job_dir / textures["basecolor"]).read_bytes()) == (11, 22, 33)
    assert read_png_first_pixel((job_dir / textures["normal"]).read_bytes()) == (128, 128, 255)
    assert read_png_first_pixel((job_dir / textures["roughness"]).read_bytes()) == (51, 51, 51)
    assert read_png_first_pixel((job_dir / textures["ao"]).read_bytes()) == (255, 255, 255)
    assert read_png_first_pixel((job_dir / textures["metallic"]).read_bytes()) == (64, 64, 64)
    assert read_png_first_pixel((job_dir / textures["orm"]).read_bytes()) == (255, 51, 64)

    log_text = (job_dir / "logs" / "material_palette.log").read_text(encoding="utf-8")
    assert "calling command:" in log_text
    assert "input dir:" in log_text
    assert "output dir:" in log_text
    assert "collected files for wall_concrete:" in log_text


def test_material_palette_provider_fallback_to_mock_on_failure(tmp_path: Path) -> None:
    job_dir = _make_job_dir(tmp_path)
    provider = MaterialPaletteProvider(
        MaterialPaletteConfig(
            command_template='python -c "import sys; sys.exit(7)"',
            output_dir=str(job_dir / "missing_output"),
            timeout=30,
        )
    )

    result = provider.generate(
        PBRGenerationRequest(
            texture_size=2,
            materials=[PBRMaterialRequest(name="floor_tiles", metallic=0.0)],
            fallback_to_mock=True,
        ),
        job_dir,
    )

    assert result.provider == "mock_pbr"
    assert result.metadata["fallback_from"] == "material_palette"
    assert "fallback reason:" in (job_dir / "logs" / "material_palette.log").read_text(encoding="utf-8")
    assert (job_dir / result.textures["floor_tiles"]["orm"]).is_file()


def _make_job_dir(tmp_path: Path) -> Path:
    job_dir = tmp_path / "job_xxx"
    (job_dir / "masks").mkdir(parents=True)
    (job_dir / "logs").mkdir()
    write_solid_rgb_png(job_dir / "reference.png", 2, 2, (40, 40, 40))
    write_solid_rgb_png(job_dir / "masks" / "wall_concrete.png", 2, 2, (255, 255, 255))
    write_solid_rgb_png(job_dir / "masks" / "floor_tiles.png", 2, 2, (255, 255, 255))
    return job_dir
