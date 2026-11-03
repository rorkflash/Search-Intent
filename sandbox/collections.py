"""Collections on disk: one folder of config JSON files per collection.

Files are saved exactly as the editor sends them (after checking they parse),
so hand-written formatting survives and `git diff` shows only real changes.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from search_intent.config import ConfigError, load_config, validate_config
from search_intent.config.loader import CONFIG_FILES

from .file_docs import FILE_DOCS

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# The service's default SEARCH_INTENT_CONFIG_DIR points here.
PROTECTED = {"default"}


class CollectionError(ValueError):
    """A request the store refuses; carries the HTTP status to answer with."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _starter_files(name: str) -> dict[str, Any]:
    """The smallest set of required files that passes validate_config."""
    return {
        "project": {
            "name": name,
            "display_name": name,
            "version": "1.0.0",
            "default_locale": "en",
            "supported_locales": ["en"],
        },
        "extractor": {
            "version": "1.0.0",
            "extractor": {"provider": "regex"},
            "entities": {},
        },
        "intent-map": {
            "version": "1.0.0",
            "intents": {
                "global_search": {
                    "description": "General search across all searchable objects.",
                    "keywords": [],
                    "default_objects": ["item"],
                }
            },
        },
        "search-map": {
            "version": "1.0.0",
            "objects": {
                "item": {"aliases": ["item"], "entities": [], "searchable_fields": ["name"]}
            },
        },
        "api-map": {
            "version": "1.0.0",
            "api": {"base_url": "https://api.example.com", "mode": "generate_only"},
            "endpoints": {
                "search": {
                    "method": "GET",
                    "path": "/search",
                    "query": {"q": "{{ search_object.query }}"},
                }
            },
            "intent_endpoint_map": {"global_search": "search"},
        },
    }


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class CollectionStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Config root not found: {self.root}")

    # --- paths -----------------------------------------------------------
    def _dir(self, name: str, *, must_exist: bool = True) -> Path:
        if not NAME_RE.match(name):
            raise CollectionError(
                "Collection names use lowercase letters, digits, '-' and '_' "
                "(max 64 chars)."
            )
        path = self.root / name
        if must_exist and not path.is_dir():
            raise CollectionError(f"Unknown collection '{name}'", 404)
        return path

    def _file(self, name: str, stem: str) -> Path:
        if stem not in CONFIG_FILES:
            raise CollectionError(f"Unknown config file '{stem}'", 404)
        return self._dir(name) / f"{stem}.json"

    # --- reads -----------------------------------------------------------
    def names(self) -> list[str]:
        return sorted(
            p.name
            for p in self.root.iterdir()
            if p.is_dir() and NAME_RE.match(p.name) and (p / "project.json").is_file()
        )

    def summary(self, name: str) -> dict[str, Any]:
        base = self._dir(name)
        project: dict[str, Any] = {}
        try:
            project = json.loads((base / "project.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "name": name,
            "display_name": project.get("display_name") or project.get("name") or name,
            "protected": name in PROTECTED,
            "files": [
                {
                    "stem": stem,
                    "required": required,
                    "present": (base / f"{stem}.json").is_file(),
                    "doc": FILE_DOCS[stem],
                }
                for stem, required in CONFIG_FILES.items()
            ],
        }

    def read_file(self, name: str, stem: str) -> str:
        path = self._file(name, stem)
        if not path.is_file():
            raise CollectionError(f"{name}/{stem}.json does not exist", 404)
        return path.read_text(encoding="utf-8")

    def validate(self, name: str) -> dict[str, Any]:
        """Load the collection the way the service would and report problems."""
        base = self._dir(name)
        try:
            config = load_config(base)
            warnings = validate_config(config)
        except (ConfigError, FileNotFoundError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc), "warnings": []}
        return {"ok": True, "error": None, "warnings": warnings}

    # --- writes ----------------------------------------------------------
    def write_file(self, name: str, stem: str, text: str) -> None:
        path = self._file(name, stem)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CollectionError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        if not isinstance(data, dict):
            raise CollectionError("A config file must contain a JSON object")
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")

    def delete_file(self, name: str, stem: str) -> None:
        path = self._file(name, stem)
        if CONFIG_FILES[stem]:
            raise CollectionError(f"{stem}.json is required and cannot be removed")
        if path.is_file():
            path.unlink()

    def create(self, name: str, copy_from: str | None = None) -> None:
        target = self._dir(name, must_exist=False)
        if target.exists():
            raise CollectionError(f"Collection '{name}' already exists", 409)

        if copy_from:
            shutil.copytree(self._dir(copy_from), target)
            project_path = target / "project.json"
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["name"] = name
            project["display_name"] = name
            project_path.write_text(_dump(project), encoding="utf-8")
            return

        target.mkdir()
        for stem, data in _starter_files(name).items():
            (target / f"{stem}.json").write_text(_dump(data), encoding="utf-8")

    def delete(self, name: str) -> None:
        path = self._dir(name)
        if name in PROTECTED:
            raise CollectionError(f"'{name}' is the service's default and cannot be deleted")
        shutil.rmtree(path)
