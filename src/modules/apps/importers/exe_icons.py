import hashlib
import os
import subprocess
import sys
from pathlib import Path


def get_executable_icon_value(exe_path):
    path = _clean_exe_path(exe_path)
    if not path or not path.lower().endswith(".exe") or not os.path.isfile(path):
        return ""
    icon_file = _icon_file_for_exe(path)
    if icon_file.exists():
        return _static_icon_value(icon_file)
    if not sys.platform.startswith("win"):
        return ""
    try:
        icon_file.parent.mkdir(parents=True, exist_ok=True)
        if _extract_icon_with_powershell(path, str(icon_file)):
            return _static_icon_value(icon_file)
    except Exception:
        try:
            icon_file.unlink(missing_ok=True)
        except Exception:
            pass
    return ""


def _clean_exe_path(exe_path):
    text = (exe_path or "").strip().strip('"').strip()
    if not text:
        return ""
    if "," in text and text.lower().endswith((".exe,0", ".exe,1")):
        text = text[: text.lower().rfind(".exe") + 4]
    return os.path.expandvars(os.path.expanduser(text))


def _icon_file_for_exe(exe_path):
    stat = os.stat(exe_path)
    key = f"{os.path.abspath(exe_path).lower()}|{int(stat.st_mtime)}|{stat.st_size}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    static_root = Path(__file__).resolve().parents[3] / "static" / "app_icons"
    return static_root / f"{digest}.ico"


def _static_icon_value(icon_file):
    return "/static/app_icons/" + icon_file.name


def _extract_icon_with_powershell(exe_path, icon_path):
    script = r"""
$exe = $env:LIFEPIM_ICON_EXE
$out = $env:LIFEPIM_ICON_OUT
Add-Type -AssemblyName System.Drawing
$icon = [System.Drawing.Icon]::ExtractAssociatedIcon($exe)
if ($null -eq $icon) { exit 2 }
$stream = [System.IO.File]::Open($out, [System.IO.FileMode]::Create)
try {
  $icon.Save($stream)
} finally {
  $stream.Dispose()
  $icon.Dispose()
}
"""
    env = os.environ.copy()
    env["LIFEPIM_ICON_EXE"] = exe_path
    env["LIFEPIM_ICON_OUT"] = icon_path
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        timeout=10,
        check=False,
    )
    return completed.returncode == 0 and os.path.isfile(icon_path) and os.path.getsize(icon_path) > 0
