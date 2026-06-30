# Provider Configuration

Provider selection must be configuration-driven. The local phase uses:

- `DEFAULT_REFERENCE_PROVIDER=mock`
- `DEFAULT_MASK_PROVIDER=mock`
- `DEFAULT_PBR_PROVIDER=mock_pbr`

External providers remain disabled until server-side configuration, security, and tests are in place.

Real provider requests can opt into mock fallback for debugging:

```json
{
  "provider": "doubao",
  "prompt": "test reference",
  "fallback_to_mock": true
}
```

For PBR, use `provider: "material_palette"` with `fallback_to_mock: true` to continue with mock maps when Material Palette fails.

## Reference Providers

Reference providers are configured on the server through `.env` variables or `server_config.yaml`. The UE client only calls this server and never stores external image API keys.

Example YAML:

```yaml
reference_providers:
  custom_http:
    endpoint: "https://example.local/generate"
    model: "image-model"
    headers:
      Authorization: "Bearer ${CUSTOM_IMAGE_API_KEY}"
    request_template:
      model: "{model}"
      prompt: "{prompt}"
      negative_prompt: "{negative_prompt}"
      seed: "{seed}"
      width: "{width}"
      height: "{height}"
    response_mapping:
      image_base64: "data.0.b64_json"

  doubao:
    endpoint: "${DOUBAO_ENDPOINT}"
    model: "${DOUBAO_MODEL}"
    headers:
      Authorization: "Bearer ${DOUBAO_API_KEY}"
    request_template: {}
    response_mapping:
      image_base64: "data.0.b64_json"

  comfyui:
    endpoint: "http://127.0.0.1:8188/prompt"
    workflow_path: "workflows/reference.json"
    field_mappings:
      prompt: "6.inputs.text"
      negative_prompt: "7.inputs.text"
      seed: "3.inputs.seed"
    response_mapping:
      image_base64: "image_base64"
```

Enable external providers explicitly:

```env
ENABLE_EXTERNAL_PROVIDERS=true
PROVIDER_CONFIG_PATH=server_config.yaml
```

## Mask Providers

The local default is `DEFAULT_MASK_PROVIDER=mock`. `MockMaskProvider` generates deterministic candidate masks for Windows tests.

`SAMMaskProvider` is a configurable server-side extension point. It does not import SAM, CUDA, or model weights in local development. Future deployment can wire it to a server command or service with:

```env
MASK_SAM_ENDPOINT=
MASK_SAM_MODEL_PATH=
MASK_SAM_COMMAND_TEMPLATE=
MASK_SAM_TIMEOUT=120
```

SAM candidates must be confirmed before PBR generation. Supported confirm operations:

- `replace`
- `union`
- `subtract`
- `intersect`

## PBR Providers

The local default is `DEFAULT_PBR_PROVIDER=mock_pbr`.

`MaterialPaletteProvider` is configured on the server. It prepares a temporary input directory with `reference.png` and `masks/*.png`, runs the configured command, then scans the output directory for:

- BaseColor: `albedo`, `basecolor`, `base_color`, `diffuse`, `color`
- Normal: `normal`, `nrm`
- Roughness: `roughness`, `rough`

Example `.env`:

```env
MATERIAL_PALETTE_REPO_PATH=/opt/MaterialPalette
MATERIAL_PALETTE_CONDA_ENV=material_palette
MATERIAL_PALETTE_COMMAND_TEMPLATE=conda run -n {conda_env} python run.py --input "{input_dir}" --output "{output_dir}"
MATERIAL_PALETTE_TIMEOUT=900
MATERIAL_PALETTE_OUTPUT_DIR=material_palette_output
```

Available template variables:

- `{repo_path}`
- `{conda_env}`
- `{job_dir}`
- `{input_dir}`
- `{output_dir}`
- `{reference_path}`
- `{masks_dir}`

If execution fails and the request uses `fallback_to_mock=true`, the server logs the fallback reason and returns `MockPBRProvider` output.
