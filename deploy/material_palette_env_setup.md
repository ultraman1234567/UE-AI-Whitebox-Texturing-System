# Material Palette Environment Setup

This guide records the tested server-side setup path for Material Palette. Use it when the upstream `deps.yml` solve is slow or when pip upgrades old dependencies into incompatible versions.

The example paths below match the current server layout:

```text
/opt/data/private/Tesla/XR/kosmos/MaterialPalette
/opt/data/private/Tesla/XR/kosmos/UE-AI-Whitebox-Texturing-System
```

## Clone Material Palette

```bash
cd /opt/data/private/Tesla/XR/kosmos
git clone --depth 1 https://github.com/astra-vision/MaterialPalette.git
cd MaterialPalette
```

If GitHub is unstable, download the zip from:

```text
https://github.com/astra-vision/MaterialPalette/archive/refs/heads/main.zip
```

Then upload and unpack it as `MaterialPalette`.

## Avoid Classic Conda Solving

The upstream `deps.yml` can stall at:

```text
Solving environment: working...
```

Use `mamba` instead:

```bash
conda install -n base -c conda-forge mamba -y
```

If a broken `matpal` environment already exists, remove it:

```bash
conda deactivate
conda env remove -n matpal -y
```

## Create A Stable Environment

Create the core environment with conda packages first. Keep PyTorch on a CUDA version supported by the server driver.

```bash
mamba create -n matpal python=3.10 \
  pytorch=1.13.1 torchvision=0.14.1 pytorch-cuda=11.7 \
  numpy=1.24 pillow scipy tqdm requests pyyaml protobuf \
  -c pytorch -c nvidia -c conda-forge -y

conda activate matpal
python -m pip install pip==24.0 setuptools==80.9.0
```

Do not upgrade pip past `24.0` for this environment. Old `lightning==1.8.3` has metadata that newer pip rejects.

## Install Python Packages

Install pinned compatibility packages first:

```bash
python -m pip install \
  "pydantic==1.10.26" \
  "fastapi==0.88.0" \
  "starlette==0.22.0" \
  "anyio<4" \
  "tokenizers>=0.11.1,<0.14" \
  "transformers==4.33.3" \
  "huggingface-hub<0.17" \
  "accelerate==0.23.0" \
  "lightning-utilities==0.3.*" \
  "torchmetrics==0.11.4" \
  tensorboardX
```

Install Material Palette packages without dependency resolution, so pip does not replace `torch` or `pydantic`:

```bash
python -m pip install --no-deps \
  lightning==1.8.3 \
  diffusers==0.19.3 \
  peft==0.5.0 \
  opencv_python \
  jsonargparse \
  easydict
```

Install the remaining Lightning app dependencies. Use `--no-deps` if pip tries to upgrade `torch`, `pydantic`, `fastapi`, or `tokenizers`.

```bash
python -m pip install --no-deps \
  psutil \
  importlib-metadata \
  arrow \
  beautifulsoup4 \
  click \
  croniter \
  deepdiff \
  inquirer \
  lightning-api-access \
  lightning-cloud \
  starsessions \
  traitlets \
  websockets \
  pyparsing
```

## Verify The Environment

Run:

```bash
conda activate matpal

python -c "import pydantic; print('pydantic', pydantic.__version__)"
python -c "import fastapi; print('fastapi', fastapi.__version__)"
python -c "import lightning; print('lightning ok')"
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import diffusers, peft, cv2, jsonargparse, easydict; print('matpal deps ok')"
python -c "import transformers, tokenizers; print(transformers.__version__, tokenizers.__version__)"
```

Expected:

```text
pydantic 1.10.26
fastapi 0.88.0
lightning ok
torch 1.13.x <cuda-version> True
matpal deps ok
transformers 4.33.3 tokenizers 0.13.x
```

If `torch.cuda.is_available()` is `False`, check:

```bash
nvidia-smi
conda list | grep -E "torch|cuda|pydantic|fastapi|lightning|tokenizers"
```

Do not install `torch` with pip in this environment.

## Download Material Palette Weights

In the Material Palette repo:

```bash
cd /opt/data/private/Tesla/XR/kosmos/MaterialPalette
wget https://github.com/astra-vision/MaterialPalette/releases/download/weights/model.tar.gz
tar -xzf model.tar.gz
find . -maxdepth 2 -type f | grep -E "ckpt|pth|pt|safetensors"
```

If `wget` is unstable, download on Windows and upload the archive to the server.

## Configure The FastAPI Server

Edit:

```bash
cd /opt/data/private/Tesla/XR/kosmos/UE-AI-Whitebox-Texturing-System
nano .env
```

Use:

```env
ENABLE_EXTERNAL_PROVIDERS=true
DEFAULT_PBR_PROVIDER=material_palette

MATERIAL_PALETTE_REPO_PATH=/opt/data/private/Tesla/XR/kosmos/MaterialPalette
MATERIAL_PALETTE_CONDA_ENV=matpal
MATERIAL_PALETTE_OUTPUT_DIR=material_palette_input
MATERIAL_PALETTE_TIMEOUT=3600
MATERIAL_PALETTE_COMMAND_TEMPLATE=conda run -n {conda_env} python pipeline.py "{input_dir}"
```

`pipeline.py` receives one input folder. The server prepares that folder as:

```text
material_palette_input/
  reference.png
  masks/*.png
```

The provider scans the configured output directory for filenames containing:

```text
albedo, basecolor, base_color, diffuse, color, normal, nrm, roughness, rough
```

Missing AO, Metallic, Normal, or Roughness maps are filled by fallback rules before ORM packing.

## Restart Server

```bash
cd /opt/data/private/Tesla/XR/kosmos/UE-AI-Whitebox-Texturing-System
conda activate ai-texturing-server
export PYTHONPATH=$PWD
uvicorn server.app.main:app --host 0.0.0.0 --port 8001
```

Run PBR generation with:

```json
{
  "provider": "material_palette",
  "texture_size": 1024,
  "fallback_to_mock": true
}
```

If Material Palette fails, the server returns mock PBR output when `fallback_to_mock=true`. Inspect:

```text
server_data/jobs/{job_id}/logs/material_palette.log
```

## Common Failure Modes

- `Solving environment: working...` for a long time: use `mamba`, not classic conda.
- `lightning==1.8.3 invalid metadata`: downgrade pip to `24.0`.
- `pydantic.main ModelMetaclass` or `IncEx` import error: force `pydantic==1.10.26`, `fastapi==0.88.0`, `starlette==0.22.0`.
- `tokenizers incompatible`: force `tokenizers>=0.11.1,<0.14`.
- `torch` becomes `2.x` or CUDA 13: rebuild or reinstall conda PyTorch; do not let pip manage torch.
- `ModuleNotFoundError` for `websockets` or `pyparsing`: install that package with `python -m pip install --no-deps <package>`.
