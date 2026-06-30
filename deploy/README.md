# Deployment

Local development remains mock-first. Real GPU deployment notes live in focused setup docs:

- `server_setup.md`
- `material_palette_setup.md`
- `sam_setup.md`

Container examples:

- `Dockerfile`
- `docker-compose.yml`

Service example:

- `ai-texturing.service`

Start with `server_setup.md` for a plain Python deployment. Add Material Palette or SAM only after the mock server is reachable from the Windows UE client.
