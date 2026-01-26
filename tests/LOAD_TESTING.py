#!/usr/bin/python3
# coding: utf-8
# LOAD_TESTING.py

from datetime import datetime
import os
import sys

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import utils
from common.media_schema import ensure_media_schema


PROJECT_LOAD_TEST = "LoadTest"

#test_type = 'FULL'
test_type = 'Light'



if test_type == 'Light':
    FOLDER_AUDIO = r"E:\BK_fangorn\music\mixing_djm"
    FOLDER_MEDIA = r"E:\BK_fangorn\photo\__new_from_camera\2023"
    FOLDER_NOTES = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes"
    FOLDER_TASKS = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\00-META\02-Tasks"
    FOLDER_EVENTS = r"N:\duncan\LifePIM_Data\calendar"
    FOLDER_GOALS = r"N:\duncan\LifePIM_Data\goals"
    FOLDER_HOW = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO"
    FOLDER_DATA = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\SQL"
    FOLDER_FILES = r"E:\BK_fangorn\user\duncan\LifePIM_Data\index"
    FOLDER_3D = r"E:\BK_fangorn\user\duncan\C\user\docs\designs\blender"
    FOLDER_APPS = r"C:\apps\UE_5.6"
else:
    FOLDER_AUDIO = r"E:\BK_fangorn\music\Music"
    FOLDER_MEDIA = r"E:\BK_fangorn\photo"
    FOLDER_NOTES = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes"
    FOLDER_TASKS = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\00-META\02-Tasks"
    FOLDER_EVENTS = r"N:\duncan\LifePIM_Data\calendar"
    FOLDER_GOALS = r"N:\duncan\LifePIM_Data\goals"
    FOLDER_HOW = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO"
    FOLDER_DATA = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\SQL"
    FOLDER_FILES = r"E:\BK_fangorn\user\duncan\LifePIM_Data"
    FOLDER_3D = r"E:\BK_fangorn\user\duncan\C\user\docs\designs\blender"
    FOLDER_APPS = r"C:\apps"

    """
    Notes loaded: 2066
    Tasks loaded: 283
    Events loaded: 214
    Goals loaded: 0
    How entries loaded: 97
    Data entries loaded: 20
    File lists loaded: 511
    Media loaded: 9943
    Audio loaded: 17563
    3D loaded: 0
    Apps loaded: 747
    """

def _iter_files(folder_path, extensions=None):
    if not folder_path or not os.path.isdir(folder_path):
        return
    try:
        for root, _, files in os.walk(folder_path):
            for name in files:
                if extensions and not name.lower().endswith(extensions):
                    continue
                yield os.path.join(root, name)
    except OSError:
        return


def _iter_dirs(folder_path):
    if not folder_path or not os.path.isdir(folder_path):
        return
    try:
        for root, dirs, _ in os.walk(folder_path):
            for name in dirs:
                yield os.path.join(root, name)
    except OSError:
        return


def _get_tbl(route_name):
    return utils.get_table_def(route_name)


def _add_record(tbl, values_map):
    if not tbl:
        return None
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    return data.add_record(data.conn, tbl["name"], tbl["col_list"], values)


def load_notes(folder_path=FOLDER_NOTES, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("notes")
    count = 0
    print('Notes folder = ' + str(folder_path))
    for full_path in _iter_files(folder_path, extensions=(".md",)):
        info = os.stat(full_path)
        values_map = {
            "file_name": os.path.basename(full_path),
            "path": os.path.dirname(full_path),
            "size": str(info.st_size),
            "date_modified": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Notes loaded: {count}")
    return count


def load_tasks(folder_path=FOLDER_TASKS, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("tasks")
    count = 0
    for full_path in _iter_files(folder_path):
        info = os.stat(full_path)
        title = os.path.splitext(os.path.basename(full_path))[0]
        values_map = {
            "title": title,
            "content": full_path,
            "project": project,
            "start_date": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d"),
            "due_date": "",
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Tasks loaded: {count}")
    return count


def load_events(folder_path=FOLDER_EVENTS, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("calendar")
    count = 0
    for full_path in _iter_files(folder_path):
        info = os.stat(full_path)
        title = os.path.splitext(os.path.basename(full_path))[0]
        event_date = datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d")
        values_map = {
            "title": title,
            "content": full_path,
            "event_date": event_date,
            "remind_date": "",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Events loaded: {count}")
    return count


def load_goals(folder_path=FOLDER_GOALS, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("goals")
    count = 0
    for full_path in _iter_files(folder_path):
        info = os.stat(full_path)
        title = os.path.splitext(os.path.basename(full_path))[0]
        values_map = {
            "parent_goal_id": "",
            "title": title,
            "description": full_path,
            "goal_date": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d"),
            "remind_date": "",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Goals loaded: {count}")
    return count


def load_how(folder_path=FOLDER_HOW, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("how")
    count = 0
    for full_path in _iter_files(folder_path):
        title = os.path.splitext(os.path.basename(full_path))[0]
        values_map = {
            "parent_how_id": "",
            "title": title,
            "description": full_path,
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"How entries loaded: {count}")
    return count


def load_data(folder_path=FOLDER_DATA, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("data")
    count = 0
    for full_path in _iter_files(folder_path, extensions=(".db",)):
        name = os.path.splitext(os.path.basename(full_path))[0]
        values_map = {
            "name": name,
            "description": "SQLite database",
            "tbl_name": full_path,
            "col_list": "",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Data entries loaded: {count}")
    return count


def load_files(folder_path=FOLDER_FILES, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("files")
    count = 0
    for full_path in _iter_dirs(folder_path):
        values_map = {
            "filelist_name": os.path.basename(full_path),
            "path": full_path,
            "file_type": "Folder",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"File lists loaded: {count}")
    return count


def load_media(folder_path=FOLDER_MEDIA):
    conn = data._get_conn()
    ensure_media_schema(conn)
    count = 0
    image_exts = {
        "jpg",
        "jpeg",
        "png",
        "gif",
        "bmp",
        "webp",
        "tif",
        "tiff",
        "heic",
        "heif",
    }
    video_exts = {"mp4", "mov", "avi", "mkv", "webm", "mpg", "mpeg", "wmv"}
    for full_path in _iter_files(folder_path):
        info = os.stat(full_path)
        ext = os.path.splitext(full_path)[1].lower().lstrip(".")
        if ext in image_exts:
            media_type = "image"
        elif ext in video_exts:
            media_type = "video"
        else:
            continue
        filename = os.path.basename(full_path)
        mtime_utc = datetime.utcfromtimestamp(info.st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
        ctime_utc = datetime.utcfromtimestamp(info.st_ctime).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO lp_media "
                "(path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    full_path,
                    filename,
                    ext,
                    media_type,
                    int(info.st_size),
                    mtime_utc,
                    ctime_utc,
                    None,
                ),
            )
            count += 1
        except Exception:
            continue
    conn.commit()
    print(f"Media loaded: {count}")
    return count


def load_audio(folder_path=FOLDER_AUDIO, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("audio")
    count = 0
    for full_path in _iter_files(folder_path):
        info = os.stat(full_path)
        ext = os.path.splitext(full_path)[1].lower().lstrip(".")
        values_map = {
            "file_name": os.path.basename(full_path),
            "path": os.path.dirname(full_path),
            "file_type": ext,
            "size": str(info.st_size),
            "date_modified": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d"),
            "artist": "",
            "album": "",
            "song": "",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Audio loaded: {count}")
    return count


def load_3d(folder_path=FOLDER_3D, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("3d")
    count = 0
    for full_path in _iter_files(folder_path, extensions=(".blend",)):
        info = os.stat(full_path)
        values_map = {
            "file_name": os.path.basename(full_path),
            "path": os.path.dirname(full_path),
            "size": str(info.st_size),
            "date_modified": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"3D loaded: {count}")
    return count


def load_apps(folder_path=FOLDER_APPS, project=PROJECT_LOAD_TEST):
    tbl = _get_tbl("apps")
    count = 0
    for full_path in _iter_files(folder_path, extensions=(".exe",)):
        title = os.path.splitext(os.path.basename(full_path))[0]
        values_map = {
            "file_path": full_path,
            "title": title,
            "icon": "",
            "project": project,
        }
        if _add_record(tbl, values_map):
            count += 1
    print(f"Apps loaded: {count}")
    return count


def main():

    print('Run order ')
    print(' 1. init_database.py')
    print(' 2. Load sample data.  python LOAD_TESTING.py')
    print(' 3. Run ETL_MAP_FOLDERS.BAT (now also backfills folder_id).')

    load_notes()
    load_tasks()
    load_events()
    load_goals()
    load_how()
    load_data()
    load_files()
    load_media()
    load_audio()
    load_3d()
    load_apps()


if __name__ == "__main__":
    main()
