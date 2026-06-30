# Server Setup

This guide deploys the FastAPI server on a Linux host. Keep all provider API keys on the server. The Windows UE client should only know the server URL.

## Clone The Project

```bash
sudo mkdir -p /opt/ue-ai-texturing
sudo chown "$USER":"$USER" /opt/ue-ai-texturing
cd /opt/ue-ai-texturing
git clone <YOUR_REPO_URL> .
```

## Install Python Environment

Use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r server/requirements.txt
```

Create local config:

```bash
cp .env.example .env
mkdir -p server_data/jobs
```

Recommended mock-only values:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_DATA_DIR=/opt/ue-ai-texturing/server_data/jobs
DEFAULT_REFERENCE_PROVIDER=mock
DEFAULT_MASK_PROVIDER=mock
DEFAULT_PBR_PROVIDER=mock_pbr
ENABLE_EXTERNAL_PROVIDERS=false
```

## Start Mock Server

```bash
source .venv/bin/activate
uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

Smoke test:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok","version":"0.1.0"}
```

## systemd Service

Copy and edit the service user/path if needed:

```bash
sudo cp deploy/ai-texturing.service /etc/systemd/system/ai-texturing.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-texturing
sudo systemctl status ai-texturing
```

Logs:

```bash
journalctl -u ai-texturing -f
```

## Windows UE Client Connection

In the UE plugin panel:

```text
Server URL = http://<SERVER_LAN_IP>:8000
```

Do not configure Doubao, ComfyUI, Material Palette, or SAM keys in the UE plugin. Those stay in `.env` or `server_config.yaml` on the Linux server.

## Firewall And Port Troubleshooting

Check the server is listening:

```bash
ss -ltnp | grep 8000
```

Open the port if using UFW:

```bash
sudo ufw allow 8000/tcp
sudo ufw status
```

From Windows PowerShell:

```powershell
Test-NetConnection <SERVER_LAN_IP> -Port 8000
Invoke-RestMethod http://<SERVER_LAN_IP>:8000/health
```

If this fails, check:

- `SERVER_HOST=0.0.0.0`, not `127.0.0.1`, for LAN access.
- Cloud/security-group inbound rules allow TCP `8000`.
- Linux firewall allows TCP `8000`.
- Windows and server are on routable networks.
- Reverse proxies forward `/api/*` and `/health` unchanged if used.
