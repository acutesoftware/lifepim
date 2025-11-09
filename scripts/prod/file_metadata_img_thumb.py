#!/usr/bin/python3
# -*- coding: utf-8 -*-
# file_metadata_img_thumb.py
"""
Create thumbnails for image files and store them as BLOBs in SQLite.
Avoids temporary disk writes by using in-memory BytesIO buffers.
"""

import os
import io
import sqlite3
from PIL import Image
from pathlib import Path
import unicodedata

import INIT_ALL_DATA as lifepim_etl

# === CONFIG ===
db_file = lifepim_etl.db_img   # separate DB for thumbnails
thumb_size = (96, 96)
commit_interval = 200  # commit every N updates



def normalize_path(p):
    # Normalize Unicode
    p = unicodedata.normalize('NFC', p)
    # Collapse multiple spaces
    p = ' '.join(p.split())
    return p


def safe_path(path):
    # Expand drive-relative paths like "W:folder" to "W:\folder"
    p = Path(path)
    if len(p.drive) == 2 and not str(p).startswith(p.drive + "\\"):
        p = Path(p.drive + "\\") / p.relative_to(p.drive)
    return str(p.resolve(strict=False))


def main():

    # === SETUP ===
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    sql = "SELECT id, path || '/' || file_name FROM c_filelist_image WHERE path NOT LIKE 'C:%' and thumbnail is null"
    cur.execute(sql)
    rows = cur.fetchall()
    total = len(rows)

    print(f"Found {total} images.")

    processed = 0
    failed = 0

    for i, (img_id, filepath) in enumerate(rows, start=1):
        filepath = filepath.replace("\\", "/")

        # fix to normalise path
        filepath = os.path.normpath(filepath)
        filepath = normalize_path(filepath)
        filepath = safe_path(filepath)
        print('Normalized path: ' + str(filepath))
        if os.path.exists(filepath):
            print('Processing ' + filepath)
        else:
            print('File not found: ' + filepath)
            failed += 1
            continue

        try:
            with Image.open(filepath) as img:
                img.thumbnail(thumb_size)
                with io.BytesIO() as buffer:
                    img.save(buffer, format='PNG', optimize=True)
                    blob_data = buffer.getvalue()
                cur.execute("UPDATE c_filelist_image SET thumbnail = ? WHERE id = ?", (blob_data, img_id))
        except Exception as ex:
            failed += 1
            print(f"Failed {i}/{total}: {filepath} — {ex}")
            continue

        processed += 1
        if processed % commit_interval == 0:
            conn.commit()
            print(f"{processed}/{total} thumbnails committed...")

    conn.commit()
    cur.close()
    conn.close()

    print(f"Done. Processed={processed}, Failed={failed}, Total={total}")

if __name__ == '__main__':
    main()
