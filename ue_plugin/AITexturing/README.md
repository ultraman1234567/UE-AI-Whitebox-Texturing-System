# AITexturing Unreal Plugin

This directory contains the minimal Unreal Editor plugin UI for the AI texturing workflow.

Current scope:

- Keep the plugin disabled by default.
- Provide a dockable Editor panel from the Window menu.
- Save panel settings to the project's `Saved/Config/AITexturingEditor.json`.
- Use `Scripts/import_ai_materials.py` for local package import and material assignment.
- Use `Scripts/ai_texturing_ui_actions.py` for server workflow actions, including reference generation, mask upload, SAM candidates, SAM confirm, PBR generation, package download, and mock fallback.
- Do not store external provider API keys in the UE client.

The importer only processes a local downloaded result package, either as a zip file or as an extracted directory containing `manifest.json`.

Optional request files read by the panel are documented in `docs/final_pipeline.md`.
