import os
from pathlib import Path

from .base import AppImportCandidate, ImportScanResult, SOURCE_TASKBAR, STATUS_INVALID
from .windows_shortcuts import resolve_shortcut


class TaskbarAppImporter:
    source_type = SOURCE_TASKBAR

    def __init__(self, default_area_id="", taskbar_paths=None, shortcut_resolver=None, icon_extractor=None):
        self.default_area_id = (default_area_id or "").strip()
        self.taskbar_paths = taskbar_paths
        self.shortcut_resolver = shortcut_resolver or resolve_shortcut
        self.icon_extractor = icon_extractor

    def scan(self):
        result = ImportScanResult()
        paths = self.taskbar_paths if self.taskbar_paths is not None else _taskbar_paths()
        found_sources = 0
        for taskbar_path in paths:
            folder = Path(os.path.expandvars(os.path.expanduser(str(taskbar_path))))
            if not folder.exists() or not folder.is_dir():
                continue
            found_sources += 1
            try:
                entries = sorted(folder.glob("*.lnk"), key=lambda entry: entry.name.lower())
            except OSError as exc:
                result.errors.append(f"Could not read taskbar shortcuts {folder}: {exc}")
                continue
            for entry in entries:
                result.candidates.append(_candidate_from_shortcut(entry, self.default_area_id, self.shortcut_resolver, self.icon_extractor))
        if not found_sources:
            result.messages.append("No Taskbar shortcut folder was found.")
        elif not result.candidates:
            result.messages.append("No Taskbar applications were found.")
        return result


def _candidate_from_shortcut(path, default_area_id, resolver, icon_extractor):
    info = resolver(str(path))
    action_type = "EXECUTABLE" if (info.target or "").lower().endswith(".exe") else "SYSTEM_DEFAULT"
    icon = icon_extractor(info.target) if action_type == "EXECUTABLE" and icon_extractor else ""
    candidate = AppImportCandidate(
        candidate_id=f"{SOURCE_TASKBAR}:{str(path)}",
        source_type=SOURCE_TASKBAR,
        name=info.name or path.stem,
        kind="Application",
        area_id=default_area_id,
        target=info.target or str(path),
        arguments=info.arguments,
        working_directory=info.working_directory,
        icon=icon,
        source_path=str(path),
        metadata={
            key: value
            for key, value in {
                "shortcut_path": info.shortcut_path,
                "resolver_error": info.error,
                "shortcut_icon": info.icon,
                "extracted_icon": icon if icon.startswith("/static/") else "",
            }.items()
            if value
        },
        action_name="Open",
        action_type=action_type,
    )
    if not info.is_valid:
        candidate.status = STATUS_INVALID
        candidate.selected = False
        candidate.metadata["error"] = info.error or "Shortcut could not be resolved."
    return candidate


def _taskbar_paths():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    return [os.path.join(appdata, "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar")]
