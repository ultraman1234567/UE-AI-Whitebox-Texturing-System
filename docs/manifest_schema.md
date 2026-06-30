# Manifest Schema

Result packages must include `manifest.json`. Paths inside the manifest must be relative to the package root and must not contain Windows or Linux absolute paths.

The schema must retain `schema_version` for future compatibility.

Current generated fields:

- `schema_version`
- `job_id`
- `reference_image`
- `unreal`
- `materials[].mask`
- `materials[].textures.basecolor`
- `materials[].textures.normal`
- `materials[].textures.roughness`
- `materials[].textures.ao`
- `materials[].textures.metallic`
- `materials[].textures.orm`

All package paths use POSIX-style relative paths such as `textures/wall_concrete/T_wall_concrete_ORM.png`.
