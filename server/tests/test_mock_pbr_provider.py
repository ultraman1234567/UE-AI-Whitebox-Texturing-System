from pathlib import Path

from server.app.providers.pbr.base import PBRGenerationRequest, PBRMaterialRequest
from server.app.providers.pbr.mock_pbr_provider import MockPBRProvider


def test_mock_pbr_provider_interface(tmp_path: Path) -> None:
    provider = MockPBRProvider()
    result = provider.generate(
        PBRGenerationRequest(
            texture_size=2,
            materials=[
                PBRMaterialRequest(name="wall_concrete", metallic=0.0),
                PBRMaterialRequest(name="floor_tiles", metallic=0.25),
            ],
        ),
        tmp_path,
    )

    assert provider.name == "mock_pbr"
    assert result.provider == "mock_pbr"
    assert result.status == "done"
    assert result.materials == ["wall_concrete", "floor_tiles"]
    assert result.textures["wall_concrete"]["orm"] == "textures/wall_concrete/T_wall_concrete_ORM.png"
