"""Dependency-light tests for explicit Hunyuan3D-Paint source resolution."""
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "hunyuan3d-paint-v2-1" / "hy3dpaint" / "utils" / "runtime_path_utils.py"
SPEC = importlib.util.spec_from_file_location("runtime_path_utils_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_empty_source_uses_documented_default_repo():
    assert MODULE.resolve_model_source(None, default_repo_id="org/model") == ("repo_id", "org/model")


def test_existing_parent_resolves_nested_model_directory(tmp_path):
    nested = tmp_path / "hunyuan3d-paintpbr-v2-1"
    nested.mkdir()
    (nested / "model_index.json").write_text("{}", encoding="utf-8")
    kind, path = MODULE.resolve_model_source(
        tmp_path, default_repo_id="org/model", nested_dir="hunyuan3d-paintpbr-v2-1"
    )
    assert kind == "local"
    assert Path(path) == nested.resolve()


def test_missing_absolute_path_fails_instead_of_remote_fallback(tmp_path):
    missing = tmp_path / "does-not-exist"
    try:
        MODULE.resolve_model_source(missing, default_repo_id="org/model")
    except FileNotFoundError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("missing absolute path unexpectedly resolved as a repository")


def test_hugging_face_repository_id_is_preserved():
    assert MODULE.resolve_model_source(
        "org/custom-model", default_repo_id="org/default"
    ) == ("repo_id", "org/custom-model")


def test_local_dino_checkpoint_requires_config_and_weights(tmp_path):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    try:
        MODULE.resolve_dino_model_source(tmp_path, default_repo_id="org/default")
    except FileNotFoundError as exc:
        assert "weight file" in str(exc)
    else:
        raise AssertionError("incomplete local checkpoint unexpectedly passed")
    (tmp_path / "model.safetensors").write_bytes(b"fixture")
    assert Path(MODULE.resolve_dino_model_source(tmp_path, default_repo_id="org/default")) == tmp_path.resolve()


def test_local_paint_checkpoint_requires_pipeline_manifest(tmp_path):
    try:
        MODULE.resolve_model_source(
            tmp_path, default_repo_id="org/default", nested_dir="hunyuan3d-paintpbr-v2-1"
        )
    except FileNotFoundError as exc:
        assert "model_index.json" in str(exc)
    else:
        raise AssertionError("incomplete local Paint checkpoint unexpectedly passed")
