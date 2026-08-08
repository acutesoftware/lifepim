import configparser
import glob
import os
from pathlib import Path

from .base import AppImportCandidate, ImportScanResult, SOURCE_DEV_FOLDER


MARKER_FILES = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "build.gradle",
    "settings.gradle",
    "Cargo.toml",
)

MARKER_GLOBS = ("*.sln", "*.csproj")


class DevFolderAppImporter:
    source_type = SOURCE_DEV_FOLDER

    def __init__(self, root_folder, default_area_id="", default_kind="Development Project"):
        self.root_folder = (root_folder or "").strip().strip('"')
        self.default_area_id = (default_area_id or "").strip()
        self.default_kind = (default_kind or "Development Project").strip()

    def scan(self):
        result = ImportScanResult()
        if not self.root_folder:
            result.messages.append("Choose a root folder, then scan.")
            return result
        root = Path(os.path.expandvars(os.path.expanduser(self.root_folder)))
        if not root.exists() or not root.is_dir():
            result.messages.append("The selected development folder was not found.")
            return result

        try:
            children = sorted([entry for entry in root.iterdir() if entry.is_dir()], key=lambda entry: entry.name.lower())
        except OSError as exc:
            result.errors.append(f"Could not read development folder: {exc}")
            return result

        for child in children:
            metadata = _project_metadata(child)
            description = " / ".join(metadata.get("project_hints") or [])
            result.candidates.append(
                AppImportCandidate(
                    candidate_id=f"{self.source_type}:{str(child)}",
                    source_type=self.source_type,
                    name=child.name,
                    kind=self.default_kind,
                    area_id=self.default_area_id,
                    target=str(child),
                    working_directory=str(child),
                    source_path=str(child),
                    metadata=metadata,
                    action_name="Open Folder",
                    action_type="OPEN_FOLDER",
                    description=description,
                )
            )
        if not result.candidates:
            result.messages.append("No child folders were found.")
        return result


def _project_metadata(folder):
    hints = []
    metadata = {"project_hints": hints}
    if (folder / ".git").exists():
        hints.append("Git repository")
        metadata["is_git_repository"] = True
        remote_url = _git_remote_url(folder / ".git")
        if remote_url:
            metadata["repository_url"] = remote_url
    for marker in MARKER_FILES:
        if (folder / marker).exists():
            hints.append(_marker_label(marker))
    for pattern in MARKER_GLOBS:
        if glob.glob(str(folder / pattern)):
            hints.append(_marker_label(pattern))
    metadata["project_hints"] = _dedupe(hints)
    return metadata


def _marker_label(marker):
    return {
        "package.json": "Node project",
        "pyproject.toml": "Python project",
        "requirements.txt": "Python requirements",
        "*.sln": "Visual Studio solution",
        "*.csproj": "C# project",
        "build.gradle": "Gradle project",
        "settings.gradle": "Gradle settings",
        "Cargo.toml": "Rust project",
    }.get(marker, marker)


def _git_remote_url(git_path):
    config_path = git_path / "config"
    if not config_path.exists():
        return ""
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except Exception:
        return ""
    section = 'remote "origin"'
    if parser.has_option(section, "url"):
        return parser.get(section, "url").strip()
    for section_name in parser.sections():
        if section_name.startswith("remote ") and parser.has_option(section_name, "url"):
            return parser.get(section_name, "url").strip()
    return ""


def _dedupe(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
