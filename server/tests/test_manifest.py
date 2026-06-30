import pytest

from server.app.processing.manifest import ManifestError, build_manifest


def test_build_manifest_uses_relative_paths() -> None:
    manifest = build_manifest(
        job_id="job_abc123def456",
        assignment={
            "unreal": {
                "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
                "texture_root": "/Game/AI_Texturing/Generated/Textures",
                "instance_root": "/Game/AI_Texturing/Generated/Instances",
            },
            "materials": [{"name": "wall_concrete", "metallic": 0.0}],
        },
        reference_image="reference.png",
        masks={"wall_concrete": "masks/wall_concrete.png"},
        texture_outputs={
            "wall_concrete": {
                "basecolor": "textures/wall_concrete/T_wall_concrete_BaseColor.png",
                "normal": "textures/wall_concrete/T_wall_concrete_Normal.png",
                "roughness": "textures/wall_concrete/T_wall_concrete_Roughness.png",
                "ao": "textures/wall_concrete/T_wall_concrete_AO.png",
                "metallic": "textures/wall_concrete/T_wall_concrete_Metallic.png",
                "orm": "textures/wall_concrete/T_wall_concrete_ORM.png",
            }
        },
    )

    assert manifest["schema_version"] == "0.1.0"
    assert manifest["materials"][0]["mask"] == "masks/wall_concrete.png"


def test_build_manifest_rejects_absolute_paths() -> None:
    with pytest.raises(ManifestError):
        build_manifest(
            job_id="job_abc123def456",
            assignment={"unreal": {}, "materials": [{"name": "wall_concrete"}]},
            reference_image="C:/bad/reference.png",
            masks={"wall_concrete": "masks/wall_concrete.png"},
            texture_outputs={
                "wall_concrete": {
                    "basecolor": "textures/wall_concrete/T_wall_concrete_BaseColor.png",
                    "normal": "textures/wall_concrete/T_wall_concrete_Normal.png",
                    "roughness": "textures/wall_concrete/T_wall_concrete_Roughness.png",
                    "ao": "textures/wall_concrete/T_wall_concrete_AO.png",
                    "metallic": "textures/wall_concrete/T_wall_concrete_Metallic.png",
                    "orm": "textures/wall_concrete/T_wall_concrete_ORM.png",
                }
            },
        )
