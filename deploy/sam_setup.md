# SAM Setup

SAM is a server-side mask candidate provider. It must never run inside the UE client and is not required for local mock tests.

## Install SAM

Install SAM only on the Linux GPU server. Follow the upstream SAM or SAM2 instructions that match your model version, CUDA version, and PyTorch version.

Example environment layout:

```bash
conda create -n sam python=3.10
conda activate sam
# Install PyTorch/CUDA and SAM dependencies according to the upstream docs.
mkdir -p /opt/models/sam
```

Place model weights outside Git:

```text
/opt/models/sam/sam_vit_h.pth
```

## Configure Server

Use `.env` or `server_config.yaml`:

```env
ENABLE_EXTERNAL_PROVIDERS=true
MASK_SAM_ENDPOINT=
MASK_SAM_MODEL_PATH=/opt/models/sam/sam_vit_h.pth
SAM_MODEL_PATH=/opt/models/sam/sam_vit_h.pth
MASK_SAM_COMMAND_TEMPLATE=
MASK_SAM_TIMEOUT=120
```

Current code provides a configurable `SAMMaskProvider` skeleton. The local default remains:

```env
DEFAULT_MASK_PROVIDER=mock
ENABLE_EXTERNAL_PROVIDERS=false
```

## API Flow

SAM should generate candidate masks only:

```http
POST /api/jobs/{job_id}/masks/auto-sam
```

Candidates must be confirmed before entering PBR generation:

```http
POST /api/jobs/{job_id}/masks/confirm
```

This ensures final Material Palette input uses user-confirmed material masks, not raw object masks.
