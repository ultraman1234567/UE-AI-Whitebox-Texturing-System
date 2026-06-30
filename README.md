# UE AI Whitebox Texturing System

This project is a semi-automated texturing pipeline for Unreal Engine whitebox scenes. The long-term flow is: UE client uploads reference material, material masks, and assignments; the server generates PBR texture maps; UE downloads a package described by `manifest.json` and imports the result.

## Current Development Mode

Development can run locally on Windows with mock providers, while real providers are configured only on the remote server. Local tests must still avoid GPU, CUDA, Material Palette, SAM, ComfyUI, Doubao, paid APIs, and external model calls.

The immediate target is a lightweight FastAPI mock server plus clear package contracts:

```text
reference.png
masks/*.png
assignment.json
textures/*/*.png
manifest.json
```

## Mock-First Principle

All AI-facing features must be replaceable providers. During local development, routes and tests should use mock providers only. Real providers such as Material Palette, SAM, Doubao, ComfyUI, or custom HTTP adapters will be added later behind configuration and must never leak API keys to the UE client.

## Repository Layout

- `server/`: FastAPI server skeleton, API routes, schemas, storage, provider slots, processing utilities, workers, and tests.
- `ue_plugin/AITexturing/`: Unreal Editor plugin panel, server action helpers, and local package importer.
- `examples/job_001/`: sample job layout for reference images, masks, and assignment data.
- `docs/`: architecture, API, provider, and manifest documentation.
- `deploy/`: future deployment notes and server setup files.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
python -m pytest server\tests
uvicorn server.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check the mock server:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","version":"0.1.0"}
```

## Mock Job Flow

The current mock flow supports job creation, reference upload, material mask upload, assignment submission, mock PBR generation, manifest creation, and zip download.

Implemented PBR outputs per material:

- `T_{material}_BaseColor.png`
- `T_{material}_Normal.png`
- `T_{material}_Roughness.png`
- `T_{material}_AO.png`
- `T_{material}_Metallic.png`
- `T_{material}_ORM.png`

Mock fallback values:

- Normal: RGB `(128, 128, 255)`
- AO: white
- Roughness: `0.7`
- Metallic: `assignment.json` material value, default `0`
- ORM: `R=AO`, `G=Roughness`, `B=Metallic`

## Real Flow Docs

Use the final workflow guide when connecting UE to a remote server:

- `docs/final_pipeline.md`
- `docs/troubleshooting.md`
- `deploy/server_setup.md`
- `deploy/material_palette_setup.md`
- `deploy/sam_setup.md`

Real provider failures can fall back to mock when request JSON sets `fallback_to_mock: true`, keeping UE import and material assignment debuggable even when GPU providers are unavailable.
