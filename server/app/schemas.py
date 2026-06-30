from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class JobCreateRequest(BaseModel):
    job_name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    ue_project_name: str = ""


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: float = 0.0
    message: str = ""
    job_name: str | None = None
    description: str | None = None
    ue_project_name: str | None = None
    reference_image: str | None = None
    reference_provider: str | None = None
    masks: dict[str, str] = Field(default_factory=dict)
    assignment: str | None = None
    manifest: str | None = None


class FileUploadResponse(BaseModel):
    job_id: str
    status: str
    path: str
    filename: str
    bytes_written: int
    material_name: str | None = None


class ReferenceGenerateRequest(BaseModel):
    provider: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    seed: int | None = None
    width: int = Field(1024, ge=1, le=4096)
    height: int = Field(1024, ge=1, le=4096)
    strength: float = Field(0.65, ge=0.0, le=1.0)
    input_images: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)
    fallback_to_mock: bool = False


class ReferenceGenerateResponse(BaseModel):
    job_id: str
    status: str
    provider: str
    path: str
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnrealAssignment(BaseModel):
    master_material: str
    texture_root: str
    instance_root: str


class MaterialAssignment(BaseModel):
    name: str
    display_name: str = ""
    assign_patterns: list[str] = Field(default_factory=list)
    tiling: float = 1.0
    normal_strength: float = 1.0
    roughness_mult: float = 1.0
    metallic: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)


class AssignmentRequest(BaseModel):
    unreal: UnrealAssignment
    materials: list[MaterialAssignment]


class AssignmentResponse(BaseModel):
    job_id: str
    status: str
    path: str
    material_count: int
    materials: list[str]


class MaskAutoRequest(BaseModel):
    provider: str = "mock"
    mode: str = "automatic"
    params: dict[str, Any] = Field(default_factory=dict)
    fallback_to_mock: bool = False


class MaskCandidateResponse(BaseModel):
    mask_id: str
    bbox: list[int]
    area: int
    score: float
    preview_url: str


class MaskAutoResponse(BaseModel):
    job_id: str
    status: str
    provider: str
    candidates: list[MaskCandidateResponse]


class MaskConfirmRequest(BaseModel):
    material_name: str
    candidate_mask_ids: list[str] = Field(..., min_length=1)
    operation: str = Field("replace", pattern="^(replace|union|subtract|intersect)$")


class MaskConfirmResponse(BaseModel):
    job_id: str
    status: str
    material_name: str
    path: str
    operation: str
    candidate_mask_ids: list[str]


class PBRGenerateRequest(BaseModel):
    provider: str = "mock_pbr"
    texture_size: int = Field(1024, ge=1, le=4096)
    fallback_to_mock: bool = True


class PBRGenerateResponse(BaseModel):
    job_id: str
    status: str
    provider: str
    material_count: int
    materials: list[str]
    manifest_path: str
    textures: dict[str, dict[str, str]]
