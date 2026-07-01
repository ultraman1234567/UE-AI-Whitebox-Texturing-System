# Material Palette Setup

Material Palette is a server-side provider. Do not install or call it from the UE plugin.

Install the real repository only on the Linux GPU server. Local Windows tests use fake output files and do not require Material Palette, CUDA, or model weights.

## Install Material Palette

Example layout:

```bash
cd /opt
git clone https://github.com/astra-vision/MaterialPalette.git
cd MaterialPalette
```

Create the Python or conda environment according to the upstream Material Palette documentation. Match CUDA, PyTorch, and model-weight versions to the target GPU server.

For the tested server setup, including mamba, PyTorch/CUDA pinning, pip 24.0, `pydantic`/`lightning` compatibility fixes, and validation commands, use:

```text
deploy/material_palette_env_setup.md
```

Example shell:

```bash
conda activate matpal
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import lightning, diffusers, peft, cv2, jsonargparse, easydict; print('matpal deps ok')"
```

Do not commit model weights, paid assets, license files, private URLs, or credentials to this repository.

## Configuration

Configure the provider through `.env` or `server_config.yaml`:

```env
MATERIAL_PALETTE_REPO_PATH=/opt/data/private/Tesla/XR/kosmos/MaterialPalette
MATERIAL_PALETTE_CONDA_ENV=matpal
MATERIAL_PALETTE_OUTPUT_DIR=material_palette_input
MATERIAL_PALETTE_TIMEOUT=3600
MATERIAL_PALETTE_COMMAND_TEMPLATE=conda run -n {conda_env} python pipeline.py "{input_dir}"
```

Available command template variables:

- `{repo_path}`
- `{conda_env}`
- `{job_dir}`
- `{input_dir}`
- `{output_dir}`
- `{reference_path}`
- `{masks_dir}`

The provider prepares:

```text
material_palette_input/
  reference.png
  masks/*.png
```

It then scans the configured output directory for files containing:

- BaseColor: `albedo`, `basecolor`, `base_color`, `diffuse`, `color`
- Normal: `normal`, `nrm`
- Roughness: `roughness`, `rough`

Missing Normal, Roughness, AO, and Metallic are filled with the project fallback rules, and ORM is packed as `R=AO`, `G=Roughness`, `B=Metallic`.

## Server Request

Call:

```json
{
  "provider": "material_palette",
  "texture_size": 1024,
  "fallback_to_mock": true
}
```

If Material Palette fails and `fallback_to_mock=true`, the server logs the command, input/output directories, collected files, and fallback reason in:

```text
server_data/jobs/{job_id}/logs/material_palette.log
```

## Local Development

Local Windows tests use fake output files and do not require Material Palette, CUDA, or model weights.
