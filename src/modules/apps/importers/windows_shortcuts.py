import configparser
import os
import sys
from dataclasses import dataclass


@dataclass
class ShortcutInfo:
    name: str
    shortcut_path: str
    target: str = ""
    arguments: str = ""
    working_directory: str = ""
    icon: str = ""
    url: str = ""
    is_valid: bool = True
    error: str = ""


def resolve_shortcut(path):
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".url":
        return resolve_url_shortcut(path)
    if suffix == ".lnk":
        return resolve_lnk_shortcut(path)
    return ShortcutInfo(
        name=_shortcut_name(path),
        shortcut_path=path,
        is_valid=False,
        error="Unsupported shortcut type.",
    )


def resolve_url_shortcut(path):
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        url = parser.get("InternetShortcut", "URL", fallback="").strip()
    except Exception as exc:
        return ShortcutInfo(name=_shortcut_name(path), shortcut_path=path, is_valid=False, error=str(exc))
    if not url:
        return ShortcutInfo(name=_shortcut_name(path), shortcut_path=path, is_valid=False, error="URL shortcut has no URL.")
    return ShortcutInfo(name=_shortcut_name(path), shortcut_path=path, target=url, url=url, is_valid=True)


def resolve_lnk_shortcut(path):
    if sys.platform.startswith("win"):
        info = _resolve_lnk_with_com(path)
        if info is not None:
            return info
    if os.path.exists(path):
        return ShortcutInfo(
            name=_shortcut_name(path),
            shortcut_path=path,
            target=path,
            is_valid=True,
            error="Shortcut target could not be resolved; using the shortcut file.",
        )
    return ShortcutInfo(name=_shortcut_name(path), shortcut_path=path, is_valid=False, error="Shortcut file not found.")


def _resolve_lnk_with_com(path):
    try:
        import win32com.client
    except Exception:
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)
        target = (shortcut.Targetpath or "").strip()
        if not target:
            return ShortcutInfo(
                name=_shortcut_name(path),
                shortcut_path=path,
                target=path,
                is_valid=True,
                error="Shortcut target was empty; using the shortcut file.",
            )
        icon = (shortcut.IconLocation or "").strip()
        return ShortcutInfo(
            name=_shortcut_name(path),
            shortcut_path=path,
            target=target,
            arguments=(shortcut.Arguments or "").strip(),
            working_directory=(shortcut.WorkingDirectory or "").strip(),
            icon=icon,
            is_valid=True,
        )
    except Exception as exc:
        return ShortcutInfo(name=_shortcut_name(path), shortcut_path=path, is_valid=False, error=str(exc))


def _shortcut_name(path):
    return os.path.splitext(os.path.basename(path))[0].strip()
