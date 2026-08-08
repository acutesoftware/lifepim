import os
from pathlib import Path

from .base import AppImportCandidate, ImportScanResult, SOURCE_DESKTOP, STATUS_INVALID
from .windows_shortcuts import resolve_shortcut


SUPPORTED_SHORTCUTS = {".lnk", ".url"}


class DesktopAppImporter:
    source_type = SOURCE_DESKTOP

    def __init__(self, default_area_id="", desktop_paths=None, shortcut_resolver=None, icon_extractor=None):
        self.default_area_id = (default_area_id or "").strip()
        self.desktop_paths = desktop_paths
        self.shortcut_resolver = shortcut_resolver or resolve_shortcut
        self.icon_extractor = icon_extractor

    def scan(self):
        result = ImportScanResult()
        paths = self.desktop_paths if self.desktop_paths is not None else _desktop_paths()
        found_sources = 0
        for desktop_path in paths:
            folder = Path(os.path.expandvars(os.path.expanduser(str(desktop_path))))
            if not folder.exists() or not folder.is_dir():
                continue
            found_sources += 1
            try:
                entries = sorted(folder.iterdir(), key=lambda entry: entry.name.lower())
            except OSError as exc:
                result.errors.append(f"Could not read desktop folder {folder}: {exc}")
                continue
            for entry in entries:
                if not entry.is_file() or entry.suffix.lower() not in SUPPORTED_SHORTCUTS:
                    continue
                result.candidates.append(_candidate_from_shortcut(entry, self.default_area_id, self.shortcut_resolver, self.icon_extractor))
        if not found_sources:
            result.messages.append("No Desktop shortcut folders were found.")
        elif not result.candidates:
            result.messages.append("No Desktop application shortcuts were found.")
        return result


def _candidate_from_shortcut(path, default_area_id, resolver, icon_extractor):
    info = resolver(str(path))
    suffix = path.suffix.lower()
    is_url = suffix == ".url" or bool(info.url)
    kind = "Web App" if is_url else "Application"
    action_type = "OPEN_URL" if is_url else ("EXECUTABLE" if info.target.lower().endswith(".exe") else "SYSTEM_DEFAULT")
    target = info.url or info.target or str(path)
    icon = ""
    if action_type == "EXECUTABLE":
        icon = icon_extractor(target) if icon_extractor else ""
    metadata = {
        "shortcut_path": info.shortcut_path,
        "resolver_error": info.error,
        "shortcut_icon": info.icon,
        "extracted_icon": icon if icon.startswith("/static/") else "",
    }
    candidate = AppImportCandidate(
        candidate_id=f"{SOURCE_DESKTOP}:{str(path)}",
        source_type=SOURCE_DESKTOP,
        name=info.name or path.stem,
        kind=kind,
        area_id=default_area_id,
        target=target,
        arguments=info.arguments,
        working_directory=info.working_directory,
        icon=icon,
        source_path=str(path),
        metadata={key: value for key, value in metadata.items() if value},
        action_name="Open",
        action_type=action_type,
    )
    if not info.is_valid:
        candidate.status = STATUS_INVALID
        candidate.selected = False
        candidate.metadata["error"] = info.error or "Shortcut could not be resolved."
    return candidate


def _desktop_paths():
    paths = []
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        paths.append(os.path.join(user_profile, "Desktop"))
    public = os.environ.get("PUBLIC")
    if public:
        paths.append(os.path.join(public, "Desktop"))
    else:
        paths.append(r"C:\Users\Public\Desktop")
    return paths
