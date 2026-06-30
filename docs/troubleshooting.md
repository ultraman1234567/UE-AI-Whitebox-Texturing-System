# Troubleshooting

Use this checklist from the outside in: Windows UE client, server HTTP, provider configuration, package output, then UE import.

## UE Cannot Reach Server

Symptoms: `Create Job` fails, `Invoke-RestMethod` cannot connect, or `Test-NetConnection` fails.

Check:

```powershell
Test-NetConnection <SERVER_IP> -Port 8000
Invoke-RestMethod http://<SERVER_IP>:8000/health
```

On Linux:

```bash
ss -ltnp | grep 8000
sudo ufw status
```

Fixes:

- Use `SERVER_HOST=0.0.0.0` for LAN access.
- Open TCP port `8000` on Linux firewall and cloud security groups.
- Use the server LAN IP in UE, not `127.0.0.1`.

## Reference Generation Fails

Check server config:

- `ENABLE_EXTERNAL_PROVIDERS=true`
- `PROVIDER_CONFIG_PATH` points to the intended YAML or JSON file.
- Provider config includes `endpoint`, `model`, `headers`, `request_template`, and `response_mapping` where needed.
- API keys are present only in server `.env`, never in UE.

Debug with fallback:

```json
{
  "provider": "doubao",
  "prompt": "test reference",
  "fallback_to_mock": true
}
```

If the response provider is `mock`, the external provider failed or was disabled, but the pipeline can continue.

## SAM Candidates Fail

Check:

- `ENABLE_EXTERNAL_PROVIDERS=true`
- `MASK_SAM_MODEL_PATH` or `SAM_MODEL_PATH` points to server-side weights.
- The configured SAM command or service is installed on the server.

Debug request:

```json
{
  "provider": "sam",
  "params": {"width": 1024, "height": 1024},
  "fallback_to_mock": true
}
```

The UE action saves candidate JSON beside the local package path as `job_xxx_sam_candidates.json`.

## Mask Confirm Fails

Common causes:

- `mask_confirm_requests.json` is missing.
- Candidate IDs do not match the latest `job_xxx_sam_candidates.json`.
- The operation is not one of `replace`, `union`, `subtract`, or `intersect`.
- Candidate masks have different dimensions.

Generate candidates again, update candidate IDs, then re-run `Confirm SAM Masks`.

## Material Palette Fails

Check:

- `MATERIAL_PALETTE_REPO_PATH` exists.
- `MATERIAL_PALETTE_CONDA_ENV` exists.
- `MATERIAL_PALETTE_COMMAND_TEMPLATE` works when run manually.
- The command writes output files containing supported keywords: `albedo`, `basecolor`, `base_color`, `diffuse`, `color`, `normal`, `nrm`, `roughness`, or `rough`.

Open:

```text
server_data/jobs/{job_id}/logs/material_palette.log
```

The log records the command, input directory, output directory, collected files, and fallback reason.

## Download Fails

`GET /download` returns `409` until `manifest.json` exists. Run `Start Mock/Real PBR Generation` first and poll job status.

If download returns `500`, a file referenced by `manifest.json` is missing. Re-run PBR generation and inspect the job directory.

## UE Import Fails

Check:

- `Python Editor Script Plugin` is enabled.
- `Local Package Path` points to a zip or extracted directory containing `manifest.json`.
- `manifest.unreal.master_material` exists in the UE project.
- `texture_root` and `instance_root` start with `/Game/`.
- The package contains BaseColor, Normal, and ORM textures for each material.

Run import without assignment first:

```text
Import Local Package
```

Then test:

```text
Assign To Selected Actors
```

## Materials Are Not Assigned

Assignment matching checks:

- actor label
- actor object name
- static mesh component name
- static mesh asset name and path
- actor tags

Update `assignment.json` patterns, for example:

```json
"assign_patterns": ["SM_Wall_*", "Wall_*", "*wall*"]
```

Select a known actor and use `Assign To Selected Actors` before assigning the full level.

## Known Good Mock Smoke Test

Use local mock providers to isolate UE import from real models:

```powershell
uvicorn server.app.main:app --reload --port 8000
pytest server\tests
```

In UE:

```text
Server URL = http://127.0.0.1:8000
```

Use `examples/job_001` and `pbr_request.json` with `provider: "mock_pbr"` or `provider: "material_palette", fallback_to_mock: true`.

