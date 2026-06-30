# API

Current implemented endpoints:

- `GET /health`: returns server status and version.
- `POST /api/jobs`: creates a local job under `server_data/jobs/{job_id}/`.
- `GET /api/jobs/{job_id}`: returns local job metadata.
- `POST /api/jobs/{job_id}/reference/upload`: uploads `reference.png`, `.jpg`, or `.jpeg`.
- `POST /api/jobs/{job_id}/reference/generate`: generates or resolves a reference image through a server-side reference provider.
- `POST /api/jobs/{job_id}/masks/upload/{material_name}`: uploads a material mask as PNG after `material_name` sanitization.
- `POST /api/jobs/{job_id}/masks/auto-sam`: generates candidate masks through a server-side mask provider.
- `GET /api/jobs/{job_id}/masks/candidates/{mask_id}/preview`: returns a candidate mask preview PNG.
- `POST /api/jobs/{job_id}/masks/confirm`: converts selected candidate masks into a confirmed material mask.
- `POST /api/jobs/{job_id}/assignment`: saves UE material assignment data.
- `POST /api/jobs/{job_id}/pbr/generate`: generates mock PBR maps and `manifest.json`.
- `GET /api/jobs/{job_id}/download`: downloads the generated zip package.

PBR generation supports `provider: "mock_pbr"` for local testing and `provider: "material_palette"` for server-side Material Palette integration. If Material Palette fails and `fallback_to_mock=true`, the server returns mock PBR output.

Reference generation providers are server-side only. The local default is `mock`; external providers such as `custom_http`, `doubao`, and `comfyui` require server configuration and `ENABLE_EXTERNAL_PROVIDERS=true`. Reference requests can set `fallback_to_mock=true` to continue with `MockReferenceProvider` if the selected provider fails.

Mask auto-generation returns candidates only. A candidate mask does not enter PBR generation until `/masks/confirm` saves it as `masks/{material_name}.png`. SAM requests can set `fallback_to_mock=true` to return deterministic mock candidates when the SAM provider fails or is disabled.
