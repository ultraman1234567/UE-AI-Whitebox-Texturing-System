# UE Plugin Usage

The first UE-side UI milestone is a lightweight Editor plugin panel. The panel stores only local workflow settings and never stores external provider API keys.

## Requirements

- Unreal Editor with Python Editor Script Plugin enabled.
- A UE project with C++ support, because this plugin adds an Editor module.
- The result package must be a local zip file or an extracted directory containing `manifest.json`.
- The master material path in `manifest.unreal.master_material` must exist in the UE project.

## Install The Plugin

Copy or symlink this plugin directory into your UE project:

```text
YourProject/
  Plugins/
    AITexturing/
      AITexturing.uplugin
      Source/
      Scripts/
      Content/
```

Then reopen the `.uproject`, enable `AI Texturing` and `Python Editor Script Plugin` in `Edit > Plugins`, and let Unreal rebuild the project modules when prompted.

## Open The Panel

After the plugin is enabled, open:

```text
Window > AI Texturing
```

The panel fields are:

- `Server URL`: local mock server, for example `http://127.0.0.1:8000`.
- `Job ID`: server job id returned by `Create Job`.
- `Local Package Path`: a local result zip, extracted package directory, or source job directory.

Settings are saved to:

```text
YourProject/Saved/Config/AITexturingEditor.json
```

## Configure Server URL

For local mock development, start the FastAPI server from this repository:

```powershell
uvicorn server.app.main:app --reload --port 8000
```

In the UE panel, set:

```text
Server URL = http://127.0.0.1:8000
```

Then click `Save Settings`.

## Import A Mock Package

Set `Local Package Path` to a downloaded `job_xxx_textures.zip` or an extracted package directory. Click:

- `Import Local Package` to import textures and create material instances without assigning actors.
- `Assign To Selected Actors` to import and assign matching materials to selected actors.
- `Assign To All Level Actors` to import and assign matching materials to all level actors.

The importer reads `manifest.json`, imports BaseColor/Normal/ORM, creates material instances under `manifest.unreal.instance_root`, and assigns materials using `assign_patterns`.

## Server Buttons

The panel also contains first-pass server workflow buttons:

- `Create Job`
- `Upload Reference`
- `Generate Reference`
- `Upload Mask`
- `Auto SAM Candidates`
- `Confirm SAM Masks`
- `Submit Assignment`
- `Start Mock/Real PBR Generation`
- `Poll Status`
- `Download Package`

These call `Scripts/ai_texturing_ui_actions.py` through Unreal Python. For upload actions, `Local Package Path` should point to a directory or zip containing `reference.png`, `masks/*.png`, and either `assignment.json` or `manifest.json`.

For generated reference, SAM candidates, SAM confirm, and PBR, the script reads optional request files from `Local Package Path`:

- `reference_request.json`
- `sam_request.json`
- `mask_confirm_requests.json`, `mask_confirm.json`, `sam_confirm_requests.json`, or `sam_confirm.json`
- `pbr_request.json`

`Auto SAM Candidates` saves the server response beside the package path as `job_xxx_sam_candidates.json`. Inspect that file, choose candidate IDs, then edit `mask_confirm_requests.json` before clicking `Confirm SAM Masks`.

`Start Mock/Real PBR Generation` defaults to:

```json
{"provider": "material_palette", "texture_size": 1024, "fallback_to_mock": true}
```

If Material Palette is not configured or fails, the server falls back to `mock_pbr` when `fallback_to_mock=true`.

## Run From UE Python Console

```python
import sys
sys.path.append(r"E:\横向\XR\半自动化白模贴图\ue_plugin\AITexturing\Scripts")

import import_ai_materials
import_ai_materials.run(
    r"C:\path\to\job_xxx_textures.zip",
    assign_mode="selected",  # or "all"
)
```

## Assignment Matching

The importer matches each material's `assign_patterns` against:

- actor label and actor object name
- static mesh component name
- static mesh asset name and asset path
- actor tags

The first matching material in `manifest.materials` is assigned to all material slots on the matching static mesh component.

## Full Pipeline

See `docs/final_pipeline.md` for the complete operation sequence and `docs/troubleshooting.md` for diagnostics.
