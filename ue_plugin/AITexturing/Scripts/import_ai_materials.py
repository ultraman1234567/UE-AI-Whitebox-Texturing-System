"""Import an AI texturing result package into Unreal Editor.

Run this script inside Unreal Editor's Python environment. It accepts either a
downloaded zip package or an already extracted package directory containing
manifest.json. It does not contact the server.
"""

from __future__ import annotations

from contextlib import contextmanager
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys
import tempfile
from typing import Any, Iterator, Optional
from zipfile import ZipFile

try:
    import unreal  # type: ignore
except ImportError:  # Allows local syntax checks outside Unreal Editor.
    unreal = None  # type: ignore


PACKAGE_PATH = ""
ASSIGN_MODE = "selected"  # none, selected, or all

LOG_PREFIX = "[AITexturing]"
TEXTURE_IMPORTS = {
    "basecolor": {
        "label": "BaseColor",
        "parameter": "T_BaseColor",
        "srgb": True,
        "compression": "TC_DEFAULT",
    },
    "normal": {
        "label": "Normal",
        "parameter": "T_Normal",
        "srgb": False,
        "compression": "TC_NORMALMAP",
    },
    "orm": {
        "label": "ORM",
        "parameter": "T_ORM",
        "srgb": False,
        "compression": "TC_MASKS",
    },
}


def run(package_path: str, assign_mode: str = "selected") -> dict[str, Any]:
    """Import a local result package and assign generated material instances."""
    _require_unreal()
    assign_mode = assign_mode.lower().strip()
    if assign_mode not in {"none", "selected", "all"}:
        raise ValueError("assign_mode must be 'none', 'selected', or 'all'")

    with _prepared_package(Path(package_path)) as package_root:
        manifest = _load_manifest(package_root)
        importer = AITexturingImporter(package_root, manifest, assign_mode)
        return importer.run()


class AITexturingImporter:
    def __init__(self, package_root: Path, manifest: dict[str, Any], assign_mode: str) -> None:
        self.package_root = package_root
        self.manifest = manifest
        self.assign_mode = assign_mode
        unreal_config = manifest.get("unreal", {})
        self.texture_root = _normalize_ue_folder(unreal_config.get("texture_root", "/Game/AI_Texturing/Generated/Textures"))
        self.instance_root = _normalize_ue_folder(unreal_config.get("instance_root", "/Game/AI_Texturing/Generated/Instances"))
        self.master_material_path = unreal_config.get("master_material", "")
        self.asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    def run(self) -> dict[str, Any]:
        _log(f"Importing package: {self.package_root}")
        _log(f"Texture root: {self.texture_root}")
        _log(f"Instance root: {self.instance_root}")

        parent_material = _load_asset_required(self.master_material_path, "master material")
        imported_materials: dict[str, Any] = {}
        imported_textures: dict[str, dict[str, Any]] = {}

        for material in self.manifest.get("materials", []):
            material_name = material["name"]
            _log(f"Processing material: {material_name}")
            textures = self._import_material_textures(material)
            imported_textures[material_name] = textures
            imported_materials[material_name] = self._create_material_instance(material, parent_material, textures)

        assigned_components = 0
        if self.assign_mode != "none":
            assigned_components = self._assign_materials(imported_materials)
        else:
            _log("Assign mode 'none': imported assets without assigning actors")
        _save_directory(self.texture_root)
        _save_directory(self.instance_root)
        _log(f"Import complete. Materials: {len(imported_materials)}, assigned components: {assigned_components}")
        return {
            "materials": list(imported_materials.keys()),
            "assigned_components": assigned_components,
            "assign_mode": self.assign_mode,
        }

    def _import_material_textures(self, material: dict[str, Any]) -> dict[str, Any]:
        material_name = material["name"]
        destination = _join_ue_path(self.texture_root, material_name)
        textures: dict[str, Any] = {}

        for texture_key, settings in TEXTURE_IMPORTS.items():
            relative_path = material.get("textures", {}).get(texture_key)
            if not relative_path:
                _warn(f"{material_name}: manifest has no {texture_key} texture; skipping")
                continue
            source_file = _resolve_package_file(self.package_root, relative_path)
            asset_name = _safe_asset_name(Path(relative_path).stem)
            _log(f"{material_name}: importing {settings['label']} from {relative_path}")
            texture = self._import_texture(source_file, destination, asset_name)
            _configure_texture(texture, settings["srgb"], settings["compression"])
            textures[texture_key] = texture

        missing = [key for key in TEXTURE_IMPORTS if key not in textures]
        if missing:
            raise RuntimeError(f"{material_name}: missing required imported textures: {missing}")
        return textures

    def _import_texture(self, source_file: Path, destination_path: str, destination_name: str) -> Any:
        if not source_file.is_file():
            raise FileNotFoundError(f"Texture file does not exist: {source_file}")

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source_file))
        task.set_editor_property("destination_path", destination_path)
        task.set_editor_property("destination_name", destination_name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        self.asset_tools.import_asset_tasks([task])

        imported_paths = list(task.get_editor_property("imported_object_paths") or [])
        candidates = imported_paths + [f"{destination_path}/{destination_name}"]
        for asset_path in candidates:
            asset = unreal.EditorAssetLibrary.load_asset(str(asset_path))
            if asset:
                return asset
        raise RuntimeError(f"Failed to load imported texture: {destination_path}/{destination_name}")

    def _create_material_instance(self, material: dict[str, Any], parent_material: Any, textures: dict[str, Any]) -> Any:
        material_name = material["name"]
        asset_name = _safe_asset_name(f"MI_{material_name}")
        asset_path = f"{self.instance_root}/{asset_name}"
        instance = unreal.EditorAssetLibrary.load_asset(asset_path)

        if instance:
            _log(f"{material_name}: updating material instance {asset_path}")
        else:
            _log(f"{material_name}: creating material instance {asset_path}")
            factory = unreal.MaterialInstanceConstantFactoryNew()
            instance = self.asset_tools.create_asset(
                asset_name,
                self.instance_root,
                unreal.MaterialInstanceConstant,
                factory,
            )
            if not instance:
                raise RuntimeError(f"Failed to create material instance: {asset_path}")

        instance.set_editor_property("parent", parent_material)
        material_lib = unreal.MaterialEditingLibrary
        material_lib.set_material_instance_texture_parameter_value(instance, _ue_name("T_BaseColor"), textures["basecolor"])
        material_lib.set_material_instance_texture_parameter_value(instance, _ue_name("T_Normal"), textures["normal"])
        material_lib.set_material_instance_texture_parameter_value(instance, _ue_name("T_ORM"), textures["orm"])

        params = material.get("parameters", {})
        material_lib.set_material_instance_scalar_parameter_value(instance, _ue_name("UV_Tiling"), float(params.get("tiling", 1.0)))
        material_lib.set_material_instance_scalar_parameter_value(
            instance,
            _ue_name("Normal_Strength"),
            float(params.get("normal_strength", 1.0)),
        )
        material_lib.set_material_instance_scalar_parameter_value(
            instance,
            _ue_name("Roughness_Mult"),
            float(params.get("roughness_mult", 1.0)),
        )

        unreal.EditorAssetLibrary.save_loaded_asset(instance)
        return instance

    def _assign_materials(self, imported_materials: dict[str, Any]) -> int:
        actors = _get_target_actors(self.assign_mode)
        if not actors:
            _warn(f"No actors found for assign mode: {self.assign_mode}")
            return 0

        _log(f"Assign mode '{self.assign_mode}' found {len(actors)} actors")
        material_specs = self.manifest.get("materials", [])
        assigned_components = 0

        for actor in actors:
            for component in _get_static_mesh_components(actor):
                material_spec = _match_material_for_component(actor, component, material_specs)
                if not material_spec:
                    continue
                material_name = material_spec["name"]
                material_instance = imported_materials.get(material_name)
                if not material_instance:
                    _warn(f"Matched {material_name}, but no material instance was created")
                    continue
                slot_count = _get_material_slot_count(component)
                for slot_index in range(slot_count):
                    component.set_material(slot_index, material_instance)
                assigned_components += 1
                _log(f"Assigned {material_name} to {_actor_label(actor)} / {component.get_name()} ({slot_count} slots)")

        if assigned_components == 0:
            _warn("No components matched assignment patterns")
        return assigned_components


@contextmanager
def _prepared_package(package_path: Path) -> Iterator[Path]:
    path = package_path.expanduser()
    if path.is_dir():
        manifest = path / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"manifest.json not found in package directory: {path}")
        yield path.resolve()
        return

    if not path.is_file() or path.suffix.lower() != ".zip":
        raise FileNotFoundError(f"Expected a zip package or extracted package directory: {path}")

    temp_dir = Path(tempfile.mkdtemp(prefix="ai_texturing_package_"))
    try:
        _safe_extract_zip(path, temp_dir)
        manifest = temp_dir / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"manifest.json not found in zip package: {path}")
        yield temp_dir.resolve()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _safe_extract_zip(zip_path: Path, destination: Path) -> None:
    root = destination.resolve()
    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            output = _resolve_package_member(root, member.filename)
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output.open("wb") as target:
                shutil.copyfileobj(source, target)


def _load_manifest(package_root: Path) -> dict[str, Any]:
    manifest_path = package_root / "manifest.json"
    _log(f"Reading manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if "materials" not in manifest or "unreal" not in manifest:
        raise ValueError("manifest.json must contain 'unreal' and 'materials'")
    return manifest


def _resolve_package_file(package_root: Path, relative_path: str) -> Path:
    output = _resolve_package_member(package_root.resolve(), relative_path)
    if not output.is_file():
        raise FileNotFoundError(f"Package file missing: {relative_path}")
    return output


def _resolve_package_member(root: Path, relative_path: str) -> Path:
    if _is_unsafe_package_path(relative_path):
        raise ValueError(f"Unsafe package path: {relative_path}")
    parts = PurePosixPath(relative_path).parts
    output = root.joinpath(*parts).resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Package path escapes root: {relative_path}") from exc
    return output


def _is_unsafe_package_path(relative_path: str) -> bool:
    if not relative_path or "\\" in relative_path:
        return True
    posix = PurePosixPath(relative_path)
    windows = PureWindowsPath(relative_path)
    return bool(posix.is_absolute() or windows.is_absolute() or windows.drive or any(part in {"", ".", ".."} for part in posix.parts))


def _configure_texture(texture: Any, srgb: bool, compression_name: str) -> None:
    texture.set_editor_property("srgb", srgb)
    compression = getattr(unreal.TextureCompressionSettings, compression_name, unreal.TextureCompressionSettings.TC_DEFAULT)
    texture.set_editor_property("compression_settings", compression)
    texture.post_edit_change()
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    _log(f"Configured texture {texture.get_name()}: sRGB={srgb}, compression={compression_name}")


def _get_target_actors(assign_mode: str) -> list[Any]:
    subsystem = _get_editor_actor_subsystem()
    if assign_mode == "selected":
        if subsystem and hasattr(subsystem, "get_selected_level_actors"):
            return list(subsystem.get_selected_level_actors())
        return list(unreal.EditorLevelLibrary.get_selected_level_actors())

    if subsystem and hasattr(subsystem, "get_all_level_actors"):
        return list(subsystem.get_all_level_actors())
    return list(unreal.EditorLevelLibrary.get_all_level_actors())


def _get_editor_actor_subsystem() -> Optional[Any]:
    if hasattr(unreal, "EditorActorSubsystem"):
        try:
            return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        except Exception as exc:
            _warn(f"EditorActorSubsystem unavailable, using fallback: {exc}")
    return None


def _get_static_mesh_components(actor: Any) -> list[Any]:
    components: list[Any] = []
    try:
        components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception as exc:
        _warn(f"Could not read static mesh components from {_actor_label(actor)}: {exc}")
    return components


def _match_material_for_component(actor: Any, component: Any, material_specs: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    candidates = _component_match_values(actor, component)
    for material in material_specs:
        patterns = material.get("assign_patterns", [])
        if _matches_any(patterns, candidates):
            return material
    return None


def _component_match_values(actor: Any, component: Any) -> list[str]:
    values = [_actor_label(actor), actor.get_name(), component.get_name()]
    values.extend(_actor_tags(actor))

    static_mesh = _get_static_mesh(component)
    if static_mesh:
        values.append(static_mesh.get_name())
        try:
            values.append(static_mesh.get_path_name())
        except Exception:
            pass
    return [str(value) for value in values if value]


def _actor_tags(actor: Any) -> list[str]:
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def _get_static_mesh(component: Any) -> Optional[Any]:
    if hasattr(component, "get_static_mesh"):
        try:
            mesh = component.get_static_mesh()
            if mesh:
                return mesh
        except Exception:
            pass
    try:
        return component.get_editor_property("static_mesh")
    except Exception:
        return None


def _matches_any(patterns: list[str], values: list[str]) -> bool:
    normalized_values = [value.lower() for value in values]
    for pattern in patterns:
        normalized_pattern = str(pattern).lower()
        for value in normalized_values:
            if fnmatch.fnmatchcase(value, normalized_pattern):
                return True
    return False


def _get_material_slot_count(component: Any) -> int:
    try:
        count = int(component.get_num_materials())
        return max(count, 1)
    except Exception:
        return 1


def _load_asset_required(asset_path: str, label: str) -> Any:
    if not asset_path:
        raise ValueError(f"Missing {label} path in manifest")
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        raise FileNotFoundError(f"Could not load {label}: {asset_path}")
    _log(f"Loaded {label}: {asset_path}")
    return asset


def _save_directory(asset_path: str) -> None:
    try:
        unreal.EditorAssetLibrary.save_directory(asset_path, only_if_is_dirty=False, recursive=True)
    except TypeError:
        unreal.EditorAssetLibrary.save_directory(asset_path)


def _normalize_ue_folder(path: str) -> str:
    path = (path or "").replace("\\", "/").rstrip("/")
    if not path.startswith("/Game/"):
        raise ValueError(f"UE content folder must start with /Game/: {path}")
    return path


def _join_ue_path(root: str, child: str) -> str:
    return f"{root.rstrip('/')}/{_safe_asset_name(child)}"


def _safe_asset_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return cleaned or "AITexturingAsset"


def _ue_name(value: str) -> Any:
    return unreal.Name(value) if hasattr(unreal, "Name") else value


def _actor_label(actor: Any) -> str:
    if hasattr(actor, "get_actor_label"):
        try:
            return actor.get_actor_label()
        except Exception:
            pass
    return actor.get_name()


def _require_unreal() -> None:
    if unreal is None:
        raise RuntimeError("This script must run inside Unreal Editor's Python environment")


def _log(message: str) -> None:
    if unreal is not None:
        unreal.log(f"{LOG_PREFIX} {message}")
    else:
        print(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    if unreal is not None:
        unreal.log_warning(f"{LOG_PREFIX} {message}")
    else:
        print(f"{LOG_PREFIX} WARNING: {message}")


def _error(message: str) -> None:
    if unreal is not None:
        unreal.log_error(f"{LOG_PREFIX} {message}")
    else:
        print(f"{LOG_PREFIX} ERROR: {message}")


def _main() -> None:
    package_path = os.environ.get("AI_TEXTURING_PACKAGE") or PACKAGE_PATH
    assign_mode = os.environ.get("AI_TEXTURING_ASSIGN_MODE") or ASSIGN_MODE

    if len(sys.argv) > 1:
        package_path = sys.argv[1]
    if len(sys.argv) > 2:
        assign_mode = sys.argv[2]

    if not package_path:
        _warn("No package path provided. Call import_ai_materials.run(package_path, assign_mode='selected') from UE Python.")
        return

    try:
        run(package_path, assign_mode=assign_mode)
    except Exception as exc:
        _error(str(exc))
        raise


if __name__ == "__main__":
    _main()
