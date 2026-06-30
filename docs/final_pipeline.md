# Final End-to-End Pipeline

This document describes the real UE-to-server texturing flow while preserving the mock-first debug path.

## Boundaries

- UE only talks to the FastAPI server by HTTP.
- UE never stores Doubao, ComfyUI, SAM, or Material Palette credentials.
- Server providers are selected by request JSON and server-side `.env` or `server_config.yaml`.
- Mock providers remain available for local debugging and provider fallback.

## Server Checklist

On the remote server, configure `.env`:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_DATA_DIR=/opt/ue-ai-texturing/server_data/jobs
ENABLE_EXTERNAL_PROVIDERS=true
PROVIDER_CONFIG_PATH=/opt/ue-ai-texturing/server_config.yaml
```

Configure only the providers you need:

- Reference: `custom_http`, `doubao`, or `comfyui`
- Masks: `sam`
- PBR: `material_palette`

Start the server:

```bash
source .venv/bin/activate
uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

Verify from Windows:

```powershell
Invoke-RestMethod http://<SERVER_IP>:8000/health
```

## UE Workflow Package

Use a local working directory for request files and optional uploads:

```text
my_job/
  reference.png                  # optional when uploading reference
  reference_request.json          # optional when generating reference
  masks/
    wall_concrete.png             # optional when uploading masks
    floor_tiles.png
  sam_request.json                # optional when using SAM candidates
  mask_confirm_requests.json      # required to confirm SAM candidates
  assignment.json
  pbr_request.json
```

`pbr_request.json` for real generation with debug fallback:

```json
{
  "provider": "material_palette",
  "texture_size": 1024,
  "fallback_to_mock": true
}
```

If Material Palette fails, the server generates mock PBR maps and records the fallback reason in `server_data/jobs/{job_id}/logs/material_palette.log`.

## UE Panel Flow

Install and enable the `AITexturing` plugin, then open:

```text
Window > AI Texturing
```

Set:

```text
Server URL = http://<SERVER_IP>:8000
Local Package Path = C:\path\to\my_job
```

Run the flow:

1. Click `Create Job`, copy the returned Job ID into `Job ID`, then `Save Settings`.
2. Reference image: click `Upload Reference`, or click `Generate Reference` using `reference_request.json`.
3. Masks: click `Upload Mask`, or click `Auto SAM Candidates`.
4. For SAM, inspect the saved `job_xxx_sam_candidates.json`, choose candidate IDs, edit `mask_confirm_requests.json`, then click `Confirm SAM Masks`.
5. Click `Submit Assignment`.
6. Click `Start Mock/Real PBR Generation`.
7. Click `Download Package`. If `Local Package Path` is a directory, the zip is saved there.
8. Set `Local Package Path` to the downloaded zip or extracted package.
9. Click `Import Local Package`, `Assign To Selected Actors`, or `Assign To All Level Actors`.

## Request File Examples

`reference_request.json`:

```json
{
  "provider": "doubao",
  "prompt": "realistic industrial corridor concrete walls and worn metal panels",
  "negative_prompt": "text, watermark, distorted geometry",
  "width": 1024,
  "height": 1024,
  "fallback_to_mock": true
}
```

`sam_request.json`:

```json
{
  "provider": "sam",
  "mode": "automatic",
  "params": {
    "points_per_side": 32,
    "pred_iou_thresh": 0.88
  },
  "fallback_to_mock": true
}
```

`mask_confirm_requests.json`:

```json
{
  "requests": [
    {
      "material_name": "wall_concrete",
      "candidate_mask_ids": ["mask_001"],
      "operation": "replace"
    }
  ]
}
```

## HTTP Equivalent

```bash
curl -X POST http://SERVER:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_name":"corridor_real_001","ue_project_name":"MyUEProject"}'

curl -X POST http://SERVER:8000/api/jobs/JOB_ID/reference/generate \
  -H "Content-Type: application/json" \
  -d @reference_request.json

curl -X POST http://SERVER:8000/api/jobs/JOB_ID/masks/auto-sam \
  -H "Content-Type: application/json" \
  -d @sam_request.json

curl -X POST http://SERVER:8000/api/jobs/JOB_ID/masks/confirm \
  -H "Content-Type: application/json" \
  -d '{"material_name":"wall_concrete","candidate_mask_ids":["mask_001"],"operation":"replace"}'

curl -X POST http://SERVER:8000/api/jobs/JOB_ID/assignment \
  -H "Content-Type: application/json" \
  -d @assignment.json

curl -X POST http://SERVER:8000/api/jobs/JOB_ID/pbr/generate \
  -H "Content-Type: application/json" \
  -d @pbr_request.json

curl -L http://SERVER:8000/api/jobs/JOB_ID/download -o JOB_ID_textures.zip
```

## Mock Debug Path

Use these request values to isolate UE import and assignment without GPU or external APIs:

```json
{"provider": "mock", "fallback_to_mock": true}
```

For PBR:

```json
{"provider": "mock_pbr", "texture_size": 1024, "fallback_to_mock": true}
```

