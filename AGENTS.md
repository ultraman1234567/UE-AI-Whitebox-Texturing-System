# AGENTS.md — UE AI Whitebox Texturing System

## 0. 项目定位

本项目是一个面向 Unreal Engine 白模场景的 AI 半自动贴图系统。

用户已经在 Unreal Engine 中搭好了白模场景。UE 运行在 Windows 客户端；AI 模型、PBR 材质生成模型、SAM 分割模型和外部图生图 API 调用统一部署在远程 Linux GPU 服务器上。

系统目标不是单纯生成一张参考图，而是完成一条完整的 UE 资产贴图管线：

```text
UE 白模场景
  ↓
参考图：用户上传，或调用图生图/文生图 API 生成
  ↓
材质 mask：用户绘制上传，或服务器端 SAM 自动分割后用户选择/编辑
  ↓
Material Palette（https://github.com/astra-vision/MaterialPalette） 生成 PBR 材质 maps
  ↓
服务器打包 BaseColor / Normal / Roughness / AO / Metallic / ORM
  ↓
Windows 客户端 / UE 插件下载结果包
  ↓
UE 自动导入贴图、创建材质实例、批量赋给白模资产
```

---

## 1. 当前开发环境约束

当前 Codex 运行在用户自己的 Windows 电脑上，不在远程 GPU 服务器上。

因此，在第一阶段开发时：

* 不要假设可以访问远程服务器。
* 不要假设本机有 CUDA。
* 不要假设本机安装了 Material Palette。
* 不要假设本机安装了 SAM。
* 不要假设有豆包或其他图像 API Key。
* 不要让测试依赖 GPU、外部模型或第三方付费 API。

第一版必须先做到：

```text
本机 Windows
  ↓
FastAPI mock server
  ↓
Mock reference image / Mock mask / Mock PBR maps
  ↓
manifest.json + zip package
  ↓
UE Python importer / UE plugin 导入
```

真实服务器、Material Palette、SAM、豆包 API、ComfyUI 等，后续作为 provider 接入。

---

## 2. 总体架构

项目采用 client-server 架构。

```text
Windows Client / UE Editor Plugin
        ↓ HTTP / WebSocket / REST
Remote AI Texturing Server
        ↓
Reference Image Providers
        ├── user_upload
        ├── doubao
        ├── comfyui
        ├── custom_http
        └── mock

Mask Providers
        ├── user_upload
        ├── user_drawn
        ├── sam_auto
        └── mock

PBR Providers
        ├── material_palette
        └── mock
```

其中：

* UE 插件/客户端只负责交互、上传、下载、导入和赋材质。
* API Key 只保存在服务器端。
* UE 端不得保存豆包、ComfyUI、Material Palette 或其他 AI 服务密钥。
* AI 模型只在服务器端运行。
* UE 和服务器之间只通过 HTTP 通信，不共享文件系统路径。
* 所有结果必须通过 manifest.json 明确描述。

---

## 3. 核心业务原则

### 3.1 以“材质”为中心，不以“物体”为中心

mask 应该表示一种材质区域，而不是一个物体区域。

推荐：

```text
wall_concrete.png
floor_tiles.png
ceiling_plaster.png
rusty_metal.png
painted_wood.png
glass_window.png
```

不推荐：

```text
chair.png
table.png
wall_01.png
wall_02.png
```

原因：UE 场景里大面积白模通常应该复用可平铺 PBR 材质，而不是给每个物体生成一张不可复用的大贴图。

### 3.2 参考图不是最终贴图

AI 参考图里通常含有透视、光照、阴影、反射、遮挡。不能直接把参考图裁剪后当 BaseColor 贴回 UE。

正确方式：

```text
参考图 + 材质 mask
  ↓
Material Palette 提取/生成材质概念
  ↓
分解为 albedo/basecolor、normal、roughness
  ↓
补齐 AO、Metallic、ORM
  ↓
导入 UE
```

### 3.3 Material Palette 是第一版真实 PBR 模型核心

第一版真实服务器上主要接入 Material Palette。

Material PaletteProvider 的职责：

* 接收 reference image。
* 接收多个 material masks。
* 为每个材质区域调用 Material Palette。
* 收集 albedo/basecolor、normal、roughness 输出。
* 如果缺少 AO，生成白色 AO。
* 如果缺少 metallic，根据 assignment.json 指定值生成 Metallic。
* 打包 ORM：

  * R = AO
  * G = Roughness
  * B = Metallic
* 输出 UE 可导入的标准命名贴图。

### 3.4 SAM 只负责生成候选 mask，不直接决定最终材质

SAM 自动分割用于加速 mask 制作。

SAMProvider 的职责：

* 输入 reference image。
* 输出若干候选 masks。
* 每个 mask 需要包含 id、bbox、area、score、preview。
* 用户或 UE 插件需要选择、合并、重命名这些 mask。
* 最终送入 Material Palette 的 mask 必须是用户确认过的 material mask。

不要把 SAM 自动生成的全部 object mask 直接当材质 mask 使用。

---

## 4. 推荐仓库结构

```text
ue-ai-texturing/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── ue_plugin_usage.md
│   ├── provider_config.md
│   ├── material_palette_setup.md
│   ├── sam_setup.md
│   └── manifest_schema.md
├── server/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── storage.py
│   │   ├── job_manager.py
│   │   ├── api/
│   │   │   ├── routes_health.py
│   │   │   ├── routes_jobs.py
│   │   │   ├── routes_reference.py
│   │   │   ├── routes_masks.py
│   │   │   ├── routes_pbr.py
│   │   │   └── routes_downloads.py
│   │   ├── providers/
│   │   │   ├── reference/
│   │   │   │   ├── base.py
│   │   │   │   ├── user_upload_provider.py
│   │   │   │   ├── doubao_provider.py
│   │   │   │   ├── comfyui_provider.py
│   │   │   │   ├── custom_http_provider.py
│   │   │   │   └── mock_reference_provider.py
│   │   │   ├── mask/
│   │   │   │   ├── base.py
│   │   │   │   ├── user_mask_provider.py
│   │   │   │   ├── sam_provider.py
│   │   │   │   └── mock_mask_provider.py
│   │   │   └── pbr/
│   │   │       ├── base.py
│   │   │       ├── material_palette_provider.py
│   │   │       └── mock_pbr_provider.py
│   │   ├── processing/
│   │   │   ├── image_utils.py
│   │   │   ├── mask_utils.py
│   │   │   ├── pbr_pack.py
│   │   │   ├── manifest.py
│   │   │   └── validation.py
│   │   └── workers/
│   │       ├── queue.py
│   │       └── tasks.py
│   └── tests/
│       ├── test_jobs.py
│       ├── test_reference_mock.py
│       ├── test_mask_mock.py
│       ├── test_pbr_pack.py
│       ├── test_mock_pbr_provider.py
│       ├── test_manifest.py
│       └── test_api_end_to_end.py
├── ue_plugin/
│   └── AITexturing/
│       ├── AITexturing.uplugin
│       ├── Content/
│       │   └── Materials/
│       │       └── M_AI_PBR_Master.uasset
│       ├── Source/
│       │   ├── AITexturing/
│       │   └── AITexturingEditor/
│       └── Scripts/
│           ├── import_ai_materials.py
│           ├── download_job_package.py
│           ├── assign_materials.py
│           └── create_master_material.py
├── examples/
│   └── job_001/
│       ├── reference.png
│       ├── masks/
│       │   ├── wall_concrete.png
│       │   └── floor_tiles.png
│       └── assignment.json
└── deploy/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── server_setup.md
    ├── material_palette_setup.md
    ├── sam_setup.md
    └── ai-texturing.service
```

---

## 5. Server API 需求

服务器使用 FastAPI。

### 5.1 Health

```http
GET /health
```

返回：

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### 5.2 创建 job

```http
POST /api/jobs
```

请求：

```json
{
  "job_name": "corridor_test_001",
  "description": "industrial corridor whitebox texturing",
  "ue_project_name": "MyUEProject"
}
```

返回：

```json
{
  "job_id": "job_xxx",
  "status": "created"
}
```

---

### 5.3 上传用户提供的参考图

```http
POST /api/jobs/{job_id}/reference/upload
```

multipart file:

```text
reference.png
```

---

### 5.4 调用 AI 生成参考图

```http
POST /api/jobs/{job_id}/reference/generate
```

请求：

```json
{
  "provider": "doubao",
  "prompt": "realistic abandoned industrial corridor, concrete walls, worn metal panels, game environment",
  "negative_prompt": "distorted geometry, extra doors, extra windows, text, watermark",
  "seed": 42,
  "width": 1024,
  "height": 1024,
  "strength": 0.65,
  "input_images": {
    "whitebox": "file_id_or_path",
    "depth": "optional_file_id_or_path",
    "normal": "optional_file_id_or_path",
    "canny": "optional_file_id_or_path"
  },
  "extra": {}
}
```

provider 必须是可配置的，不得写死豆包。

必须支持：

```text
mock
doubao
comfyui
custom_http
```

---

### 5.5 上传用户绘制的 mask

```http
POST /api/jobs/{job_id}/masks/upload/{material_name}
```

multipart file:

```text
mask.png
```

要求：

* mask 必须和 reference image 尺寸一致，或能被安全 resize。
* 白色表示材质区域。
* 黑色表示其他区域。
* material_name 必须清洗为安全名称：

  * lowercase
  * 字母、数字、下划线
  * 不允许路径分隔符
  * 不允许空格

---

### 5.6 使用 SAM 自动分割生成候选 masks

```http
POST /api/jobs/{job_id}/masks/auto-sam
```

请求：

```json
{
  "provider": "sam",
  "mode": "automatic",
  "params": {
    "points_per_side": 32,
    "pred_iou_thresh": 0.88,
    "stability_score_thresh": 0.95,
    "min_mask_region_area": 256
  }
}
```

返回：

```json
{
  "job_id": "job_xxx",
  "status": "done",
  "candidates": [
    {
      "mask_id": "mask_001",
      "preview_url": "/api/jobs/job_xxx/masks/candidates/mask_001/preview",
      "bbox": [10, 20, 300, 220],
      "area": 58210,
      "score": 0.94
    }
  ]
}
```

---

### 5.7 将 SAM candidate 保存为材质 mask

```http
POST /api/jobs/{job_id}/masks/confirm
```

请求：

```json
{
  "material_name": "wall_concrete",
  "candidate_mask_ids": ["mask_001", "mask_007"],
  "operation": "union"
}
```

operation 支持：

```text
replace
union
subtract
intersect
```

---

### 5.8 提交材质分配规则

```http
POST /api/jobs/{job_id}/assignment
```

请求：

```json
{
  "unreal": {
    "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
    "texture_root": "/Game/AI_Texturing/Generated/Textures",
    "instance_root": "/Game/AI_Texturing/Generated/Instances"
  },
  "materials": [
    {
      "name": "wall_concrete",
      "display_name": "Wall Concrete",
      "assign_patterns": ["SM_Wall_*", "Wall_*", "*wall*"],
      "tiling": 3.0,
      "normal_strength": 1.0,
      "roughness_mult": 1.0,
      "metallic": 0.0
    },
    {
      "name": "floor_tiles",
      "display_name": "Floor Tiles",
      "assign_patterns": ["SM_Floor_*", "Floor_*", "*floor*"],
      "tiling": 4.0,
      "normal_strength": 1.2,
      "roughness_mult": 1.0,
      "metallic": 0.0
    }
  ]
}
```

---

### 5.9 生成 PBR 材质

```http
POST /api/jobs/{job_id}/pbr/generate
```

请求：

```json
{
  "provider": "material_palette",
  "texture_size": 1024,
  "fallback_to_mock": true
}
```

开发初期必须支持：

```json
{
  "provider": "mock_pbr"
}
```

---

### 5.10 查询 job 状态

```http
GET /api/jobs/{job_id}
```

返回：

```json
{
  "job_id": "job_xxx",
  "status": "running",
  "stage": "pbr_generation",
  "progress": 0.5,
  "message": "Generating roughness maps"
}
```

---

### 5.11 下载结果包

```http
GET /api/jobs/{job_id}/download
```

返回 zip：

```text
manifest.json
reference.png
masks/
  wall_concrete.png
  floor_tiles.png
textures/
  wall_concrete/
    T_wall_concrete_BaseColor.png
    T_wall_concrete_Normal.png
    T_wall_concrete_Roughness.png
    T_wall_concrete_AO.png
    T_wall_concrete_Metallic.png
    T_wall_concrete_ORM.png
  floor_tiles/
    T_floor_tiles_BaseColor.png
    T_floor_tiles_Normal.png
    T_floor_tiles_Roughness.png
    T_floor_tiles_AO.png
    T_floor_tiles_Metallic.png
    T_floor_tiles_ORM.png
logs/
  job.log
```

---

## 6. Provider 设计

### 6.1 ReferenceImageProvider

接口：

```python
class ReferenceImageProvider(Protocol):
    name: str

    def generate(self, request: ReferenceGenerationRequest, job_dir: Path) -> ReferenceGenerationResult:
        ...
```

必须实现：

```text
MockReferenceProvider
UserUploadReferenceProvider
DoubaoReferenceProvider
ComfyUIReferenceProvider
CustomHTTPReferenceProvider
```

要求：

* Doubao provider 不要硬编码 endpoint、model、API key。
* 读取 `.env` 或 `server_config.yaml`。
* CustomHTTPProvider 要支持通用 URL、headers、body_template、response_mapping。
* ComfyUIProvider 要从外部 workflow JSON 读取工作流，不要硬编码复杂节点。
* MockReferenceProvider 用于本机无 API 测试。

---

### 6.2 MaskProvider

接口：

```python
class MaskProvider(Protocol):
    name: str

    def generate(self, request: MaskGenerationRequest, job_dir: Path) -> MaskGenerationResult:
        ...
```

必须实现：

```text
UserMaskProvider
SAMMaskProvider
MockMaskProvider
```

要求：

* UserMaskProvider 接收用户上传或 UE 端绘制的 mask。
* SAMMaskProvider 在服务器上运行 SAM，输出候选 masks。
* MockMaskProvider 在本机测试时生成简单几何 mask。
* SAM 输出不直接进入 PBR，必须经过 confirm step 转成 material mask。

---

### 6.3 PBRProvider

接口：

```python
class PBRProvider(Protocol):
    name: str

    def generate(self, request: PBRGenerationRequest, job_dir: Path) -> PBRGenerationResult:
        ...
```

必须实现：

```text
MockPBRProvider
MaterialPaletteProvider
```

MockPBRProvider 用于：

* 本机 Windows 开发。
* 单元测试。
* UE 导入流程测试。
* 无 GPU 端到端验证。

MaterialPaletteProvider 用于：

* 真实 Linux GPU 服务器。
* 从 reference image + material masks 生成真实 PBR maps。
* 通过 subprocess 或独立服务调用外部 Material Palette 环境。

---

## 7. PBR 输出规范

每个材质必须输出：

```text
T_{material}_BaseColor.png
T_{material}_Normal.png
T_{material}_Roughness.png
T_{material}_AO.png
T_{material}_Metallic.png
T_{material}_ORM.png
```

生成规则：

* BaseColor:

  * RGB。
  * 对应 albedo/basecolor。
* Normal:

  * RGB normal map。
  * 如果缺失，生成 flat normal：`128, 128, 255`。
* Roughness:

  * grayscale。
  * 如果缺失，默认 `0.7`。
* AO:

  * grayscale。
  * 如果缺失，默认白色 `1.0`。
* Metallic:

  * grayscale。
  * 从 assignment.json 中读取。
  * 非金属默认 `0.0`。
* ORM:

  * R = AO
  * G = Roughness
  * B = Metallic

---

## 8. manifest.json 规范

结果包中必须包含 manifest.json。

示例：

```json
{
  "schema_version": "0.1.0",
  "job_id": "job_xxx",
  "reference_image": "reference.png",
  "unreal": {
    "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
    "texture_root": "/Game/AI_Texturing/Generated/Textures",
    "instance_root": "/Game/AI_Texturing/Generated/Instances"
  },
  "materials": [
    {
      "name": "wall_concrete",
      "display_name": "Wall Concrete",
      "mask": "masks/wall_concrete.png",
      "textures": {
        "basecolor": "textures/wall_concrete/T_wall_concrete_BaseColor.png",
        "normal": "textures/wall_concrete/T_wall_concrete_Normal.png",
        "roughness": "textures/wall_concrete/T_wall_concrete_Roughness.png",
        "ao": "textures/wall_concrete/T_wall_concrete_AO.png",
        "metallic": "textures/wall_concrete/T_wall_concrete_Metallic.png",
        "orm": "textures/wall_concrete/T_wall_concrete_ORM.png"
      },
      "assign_patterns": ["SM_Wall_*", "Wall_*", "*wall*"],
      "parameters": {
        "tiling": 3.0,
        "normal_strength": 1.0,
        "roughness_mult": 1.0,
        "metallic": 0.0
      }
    }
  ]
}
```

要求：

* 所有路径必须是 zip 内相对路径。
* 不允许服务器绝对路径。
* 不允许 Windows 绝对路径。
* 不允许 Linux 绝对路径。
* schema_version 必须保留，方便后续兼容升级。

---

## 9. UE 插件 / 客户端需求

UE 运行在 Windows 客户端。

第一版可以先实现 UE Python 脚本，然后再封装成 Editor 插件 UI。

UE 端必须支持：

1. 配置服务器：

   * server_url
   * optional token
   * local cache directory
2. job 操作：

   * create job
   * upload reference image
   * request AI reference generation
   * upload material masks
   * request SAM auto masks
   * confirm SAM masks as material masks
   * submit assignment
   * start PBR generation
   * poll status
   * download zip package
3. 导入结果：

   * unzip package
   * read manifest.json
   * import textures
   * configure texture settings
   * create Material Instances
   * assign material instances
4. 赋材质范围：

   * selected actors
   * all level actors
5. 匹配方式：

   * actor name
   * component name
   * static mesh asset name
   * actor tags
   * wildcard patterns

---

## 10. UE Master Material 参数要求

默认父材质路径：

```text
/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master
```

必须暴露以下参数：

Texture parameters:

```text
T_BaseColor
T_Normal
T_ORM
```

Scalar parameters:

```text
UV_Tiling
Normal_Strength
Roughness_Mult
```

可选参数：

```text
BaseColor_Tint
Metallic_Override
Use_Metallic_Override
```

ORM 连接规则：

```text
ORM.R → Ambient Occlusion
ORM.G → Roughness
ORM.B → Metallic
```

UE 贴图导入设置：

```text
BaseColor:
  sRGB = true
  Compression = default

Normal:
  sRGB = false
  Compression = normal map

ORM:
  sRGB = false
  Compression = masks
```

---

## 11. 安全与配置

必须遵守：

* 不要把 API key 提交到 Git。
* `.env.example` 可以提交，`.env` 不可提交。
* 外部 API key 只保存在服务器端。
* UE 插件不保存豆包或其他生图 API key。
* 上传文件必须校验大小、扩展名和 MIME。
* job_id、material_name、filename 必须防止路径穿越。
* zip 解压必须防止 zip slip。
* material_name 必须 sanitize。
* 服务器端日志不要打印完整 API key。

---

## 12. 测试要求

第一阶段测试不得依赖：

```text
GPU
CUDA
Material Palette
SAM
ComfyUI
豆包 API
外部网络
```

必须有 pytest 测试：

```text
test_jobs.py
test_reference_mock.py
test_mask_mock.py
test_pbr_pack.py
test_mock_pbr_provider.py
test_manifest.py
test_api_end_to_end.py
```

测试内容：

1. 创建 job。
2. 上传 reference。
3. 上传 mask。
4. 提交 assignment。
5. 使用 MockPBRProvider 生成 PBR maps。
6. 生成 manifest.json。
7. 生成 zip。
8. 校验 zip 内路径都是相对路径。
9. 校验 ORM 通道：

   * R = AO
   * G = Roughness
   * B = Metallic
10. 校验缺失 normal 时生成 flat normal。
11. 校验缺失 AO 时生成 white AO。
12. 校验 material_name sanitize。

---

## 13. 开发里程碑

### Milestone 1 — 本机 FastAPI Mock Server

目标：本机 Windows 上无 GPU 跑通 server skeleton。

实现：

* FastAPI app。
* health endpoint。
* job 创建。
* 本地 job storage。
* reference 上传。
* mask 上传。
* assignment 上传。
* MockReferenceProvider。
* MockMaskProvider。
* MockPBRProvider。
* pytest。

不要实现：

* UE 插件。
* Material Palette。
* SAM。
* 豆包 API。
* ComfyUI。

---

### Milestone 2 — PBR Packaging + Manifest

目标：生成 UE 可用结果包。

实现：

* BaseColor / Normal / Roughness / AO / Metallic / ORM 生成。
* 缺失 map fallback。
* ORM packing。
* manifest.json。
* zip package。
* API 下载 endpoint。
* 端到端 mock 测试。

---

### Milestone 3 — UE Python Importer

目标：UE 中可以导入服务器结果包。

实现：

* UE Python 脚本读取本地 zip 或解压目录。
* 读取 manifest.json。
* 导入 BaseColor / Normal / ORM。
* 设置 texture compression 和 sRGB。
* 创建 Material Instance。
* 设置材质参数。
* 支持 selected actors / all level actors 批量赋材质。
* 支持 wildcard pattern 匹配。

---

### Milestone 4 — UE Editor Plugin UI

目标：给用户可操作界面。

实现：

* AITexturing Editor 插件。
* server_url 配置。
* create job。
* upload reference。
* upload masks。
* start PBR generation。
* poll status。
* download package。
* import package。
* assign selected actors。
* assign all level actors。

第一版 UI 可以调用 Python 脚本完成导入逻辑。

---

### Milestone 5 — Reference Image Providers

目标：参考图来源可配置。

实现：

* ReferenceImageProvider 接口。
* MockReferenceProvider。
* UserUploadReferenceProvider。
* CustomHTTPReferenceProvider。
* ComfyUIReferenceProvider。
* DoubaoReferenceProvider 配置式 adapter。

要求：

* 不硬编码豆包 API 细节。
* endpoint、model、headers、request_template、response_mapping 都从配置读取。
* 支持后续官方购买模型接入。
* UE 端不接触 provider API key。

---

### Milestone 6 — Mask Providers + SAM

目标：mask 支持用户绘制和 SAM 自动分割。

实现：

* UserMaskProvider。
* MockMaskProvider。
* SAMMaskProvider。
* `/masks/auto-sam` endpoint。
* candidate masks 存储。
* candidate preview。
* confirm masks as material masks。
* mask union/subtract/intersect/replace 操作。

要求：

* SAM 输出只是候选 mask。
* 用户确认后的 material mask 才能进入 PBR 阶段。

---

### Milestone 7 — Material Palette Provider

目标：真实服务器上接入 Material Palette。

实现：

* MaterialPaletteProvider。
* 通过 subprocess 或独立服务调用 Material Palette。
* material_palette_repo_path 可配置。
* conda_env 可配置。
* command_template 可配置。
* 输入 job_dir/reference.png 和 job_dir/masks/*.png。
* 输出收集器要稳健搜索：

  * albedo
  * basecolor
  * base_color
  * diffuse
  * color
  * normal
  * nrm
  * roughness
  * rough
* 统一重命名为 UE PBR 输出规范。
* 补齐 AO / Metallic / ORM。
* 如果失败且 fallback_to_mock=true，则回退 MockPBRProvider。

---

### Milestone 8 — Linux GPU Server Deployment

目标：部署到真实服务器。

实现：

* Dockerfile 或 conda 部署文档。
* docker-compose.yml。
* `.env.example`。
* deploy/server_setup.md。
* deploy/material_palette_setup.md。
* deploy/sam_setup.md。
* systemd service。
* 服务器端 smoke test。
* Windows UE 客户端连接服务器测试。

---

### Milestone 9 — End-to-End Real Pipeline

目标：真实流程跑通。

流程：

```text
UE 截图或用户 reference
  ↓
用户上传 reference 或服务器生成 reference
  ↓
用户上传 mask 或 SAM 生成候选后确认
  ↓
Material Palette 生成 PBR
  ↓
UE 下载结果包
  ↓
UE 自动导入
  ↓
UE 批量赋材质
```

---

## 14. 编码风格

* Python 使用 type hints。
* FastAPI schema 使用 Pydantic。
* 文件路径使用 pathlib。
* provider 逻辑不要写在 route 中。
* route 只做请求解析和调用服务。
* 文件读写集中在 storage.py。
* manifest 生成集中在 processing/manifest.py。
* PBR 打包集中在 processing/pbr_pack.py。
* 尽量保持函数短小、可测。
* 所有 tests 必须能在本机 Windows 无 GPU 环境运行。
* 所有真实 AI provider 都必须可关闭或替换为 mock。

---

## 15. Definition of Done for First MVP

第一版 MVP 完成标准：

1. 本机 Windows 能启动 FastAPI server。
2. pytest 全部通过。
3. 可以创建 job。
4. 可以上传 reference。
5. 可以上传至少两个 material masks。
6. 可以提交 assignment。
7. MockPBRProvider 生成完整 PBR maps。
8. manifest.json 正确。
9. zip 包正确。
10. UE Python 脚本可以导入 zip。
11. UE 可以创建 Material Instances。
12. UE 可以按 wildcard patterns 给 selected actors 或 all level actors 赋材质。
13. 不需要 GPU。
14. 不需要 Material Palette。
15. 不需要 SAM。
16. 不需要豆包 API key。
17. 文档说明后续如何接入真实服务器、Material Palette、SAM、图生图 provider。

---

## 16. 最重要的实现原则

不要把参考图生成、mask 生成、PBR 生成、UE 导入写成强耦合流程。

它们必须通过清晰的数据文件和 manifest 串联：

```text
reference.png
masks/*.png
assignment.json
textures/*/*.png
manifest.json
```

这样后续才能替换豆包、ComfyUI、SAM、Material Palette 或其他模型，而不影响 UE 导入端。
