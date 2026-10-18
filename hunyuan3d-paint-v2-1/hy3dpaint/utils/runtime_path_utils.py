"""Explicit model-source resolution for Hunyuan3D-Paint runtime loaders.

A missing absolute/local path is a configuration error, not a signal to download
an unrelated default checkpoint. Repository IDs are passed through unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple


def _looks_like_local_path(value: str) -> bool:
    return (
        Path(value).expanduser().is_absolute()
        or value.startswith(("./", "../", "~"))
        or value.startswith(".\\")
        or value.startswith("..\\")
        or (len(value) >= 3 and value[1] == ":" and value[2] in ("\\", "/"))
    )


def resolve_model_source(
    value: str | os.PathLike[str] | None,
    *,
    default_repo_id: str,
    nested_dir: str | None = None,
) -> Tuple[str, str]:
    """Return ('local', path) or ('repo_id', id), failing on missing local paths.

    Existing local directories are preferred even if their names contain slashes.
    A repository ID is accepted only when it does not look like an explicit local
    path. If nested_dir is supplied, a parent containing that child resolves to it.
    """
    if value is None or not str(value).strip():
        return "repo_id", default_repo_id

    raw = str(value).strip()
    expanded = Path(raw).expanduser()
    if expanded.exists():
        if not expanded.is_dir():
            raise NotADirectoryError(f"Configured model source is not a directory: {expanded}")
        candidate = expanded
        if nested_dir:
            nested = candidate / nested_dir
            if nested.is_dir():
                candidate = nested
            if not (candidate / "model_index.json").is_file():
                raise FileNotFoundError(
                    f"Local Hunyuan3D-Paint directory is missing model_index.json: {candidate}. "
                    "Point to the model directory or explicitly configure a Hugging Face repository ID."
                )
        return "local", str(candidate.resolve())

    if _looks_like_local_path(raw):
        raise FileNotFoundError(
            f"Configured local model path does not exist: {expanded}. "
            "Correct the path or explicitly configure a Hugging Face repository ID."
        )

    if raw in (".", "..") or raw.startswith(("./", "../")):
        raise FileNotFoundError(f"Configured local model path does not exist: {expanded}")

    if "/" not in raw or raw.startswith("/") or "\\" in raw:
        raise ValueError(
            f"Invalid model source {raw!r}; expected an existing local directory "
            f"or a Hugging Face repository ID such as {default_repo_id!r}."
        )
    return "repo_id", raw


def resolve_dino_model_source(
    value: str | os.PathLike[str] | None,
    *,
    default_repo_id: str,
) -> str:
    """Resolve DINOv2 source and validate local Transformers checkpoint layout."""
    kind, source = resolve_model_source(value, default_repo_id=default_repo_id)
    if kind == "repo_id":
        return source

    path = Path(source)
    if not (path / "config.json").is_file():
        raise FileNotFoundError(
            f"Local DINOv2 checkpoint is missing config.json: {path}. "
            "Automatic remote fallback is disabled for an explicit local path."
        )
    weight_patterns = ("*.safetensors", "pytorch_model*.bin", "model*.bin")
    if not any(
        item.is_file()
        for pattern in weight_patterns
        for item in path.glob(pattern)
    ):
        raise FileNotFoundError(
            f"Local DINOv2 checkpoint has no supported weight file: {path}. "
            "Expected *.safetensors, pytorch_model*.bin, or model*.bin."
        )
    return source
