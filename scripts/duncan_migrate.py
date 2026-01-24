#!/usr/bin/python3
# coding: utf-8
# duncan_migrate.py - sample migration script

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_root = os.path.join(repo_root, "src")
if src_root not in sys.path:
    sys.path.append(src_root)

import common.import_tools as mod_tool

# CSV -> contacts (importer-backed)
mod_tool.load_csv(
    tbl="lp_contacts",
    fname="contacts.csv",
    map={
        "source_uid": "ContactID",
        "display_name": "Name",
        "email": "Email",
        "phone": "Phone",
    },
    key="source_uid",
    mode="snapshot",
    source_system="contacts_csv",
    dry_run=True,
)

# SQLite -> audio (raw table copy)
mod_tool.load_tbl(
    tbl="lp_audio",
    src_db="filelist.db",
    src_tbl="tbl_files",
    cols_to_insert=["file_name", "size"],
    select_named="select metadata_filename, metadata_file",
)
