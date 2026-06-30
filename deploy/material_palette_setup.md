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

Example shell:

```bash
conda create -n material_palette python=3.10
conda activate material_palette
# Install Material Palette requirements following its upstream README.
```

Do not commit model weights, paid assets, license files, private URLs, or credentials to this repository.

## Configuration

Configure the provider through `.env` or `server_config.yaml`:

```env
MATERIAL_PALETTE_REPO_PATH=/opt/MaterialPalette
MATERIAL_PALETTE_CONDA_ENV=material_palette
MATERIAL_PALETTE_OUTPUT_DIR=material_palette_output
MATERIAL_PALETTE_TIMEOUT=900
MATERIAL_PALETTE_COMMAND_TEMPLATE=conda run -n {conda_env} python run.py --input "{input_dir}" --output "{output_dir}"
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
