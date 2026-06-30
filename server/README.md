# Server

FastAPI mock server skeleton for local Windows development.

Current scope:

- Start a lightweight API app.
- Expose `GET /health`.
- Keep AI, GPU, external provider, and UE integration code out of the first skeleton.

Run from the repository root:

```powershell
python -m pip install -r server\requirements.txt
python -m pytest server\tests
uvicorn server.app.main:app --reload --host 127.0.0.1 --port 8000
```
